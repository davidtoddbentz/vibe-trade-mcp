"""Trading strategy tools for MCP server."""

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import RefResolver
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from .. db.archetype_repository import ArchetypeRepository
from .. db.archetype_schema_repository import ArchetypeSchemaRepository
from .. tools.errors import ErrorCode, StructuredToolError, not_found_error


class ArchetypeInfo(BaseModel):
    """Lightweight archetype info for MCP responses.

    This is the API contract - only includes fields needed by agents.
    """

    id: str = Field(..., description="Archetype identifier")
    version: int = Field(..., description="Archetype version number")
    title: str = Field(..., description="Human-readable title")
    summary: str = Field(..., description="Brief description")
    kind: str = Field(..., description="Archetype kind (e.g., 'entry', 'gate')")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    required_slots: list[str] = Field(..., description="List of required slot names")
    schema_etag: str = Field(..., description="Weak ETag for schema caching")
    deprecated: bool = Field(default=False, description="Whether deprecated")
    intent_phrases: list[str] = Field(
        default_factory=list, description="Example phrases that match this archetype"
    )


class GetArchetypesResponse(BaseModel):
    """Response from get_archetypes tool."""

    types: list[ArchetypeInfo] = Field(..., description="List of available archetypes")
    as_of: str = Field(..., description="ISO8601 timestamp of when this catalog was generated")


class GetArchetypeSchemaRequest(BaseModel):
    """Request for get_archetype_schema tool."""

    type: str = Field(..., description="Archetype identifier (e.g., 'signal.trend_pullback')")
    if_none_match: str | None = Field(
        None,
        description="Optional ETag for conditional requests. If provided and matches, indicates client already has this version.",
    )


class GetArchetypeSchemaResponse(BaseModel):
    """Response from get_archetype_schema tool."""

    type_id: str = Field(..., description="Archetype identifier")
    schema_version: int = Field(..., description="Schema version number")
    etag: str = Field(..., description="Weak ETag for schema caching")
    json_schema: dict = Field(..., description="JSON Schema object for validation")
    constraints: dict = Field(
        ..., description="Schema constraints (min_history_bars, pit_safe, etc.)"
    )
    slot_hints: dict = Field(default_factory=dict, description="Hints for slot values")
    examples: list[dict] = Field(default_factory=list, description="Example slot configurations")
    updated_at: str = Field(..., description="ISO8601 timestamp of last update")


class GetSchemaExampleResponse(BaseModel):
    """Response from get_schema_example tool."""

    type_id: str = Field(..., description="Archetype identifier")
    example_slots: dict = Field(..., description="Ready-to-use example slots (copy-paste ready)")
    human_description: str | None = Field(
        None, description="Human-readable description of this example"
    )
    schema_etag: str = Field(
        ..., description="Schema ETag to use when creating card with these slots"
    )


def _resolve_schema_references(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve all $ref references in a JSON Schema to their actual definitions.

    This function loads common_defs.json and resolves all external references
    like "common_defs.schema.json#/$defs/ContextSpec" to their actual schema definitions.
    This makes the schema self-contained and easier for agents to understand.

    Args:
        schema: JSON Schema dictionary that may contain $ref references

    Returns:
        A new schema dictionary with all $ref references resolved
    """
    # Load common_defs.json to resolve external $ref references
    project_root = Path(__file__).parent.parent.parent
    common_defs_path = project_root / "data" / "common_defs.json"

    try:
        with open(common_defs_path) as f:
            common_defs = json.load(f)
    except FileNotFoundError:
        # If common_defs.json doesn't exist, return schema as-is
        return deepcopy(schema)

    # Create a resolver that can resolve references to common_defs
    # Also add common_defs to the store with its $id so internal refs can be resolved
    store = {"common_defs.schema.json": common_defs}
    # Create a base schema for the resolver (can be empty, just needs the store)
    base_schema = {"$id": schema.get("$id", "./schema.json")}
    resolver = RefResolver.from_schema(base_schema, store=store)

    def resolve_refs(obj: Any, base_uri: str = "") -> Any:
        """Recursively resolve all $ref references in the schema.

        Args:
            obj: The object to resolve references in
            base_uri: Base URI for resolving relative references (used for internal refs)
        """
        if isinstance(obj, dict):
            # If this is a $ref, resolve it
            if "$ref" in obj and len(obj) == 1:
                # Pure $ref object - resolve it
                ref_value = obj["$ref"]
                try:
                    # Handle relative references (starting with #)
                    # If we have a base_uri from common_defs, resolve relative to it
                    if ref_value.startswith("#") and base_uri and "common_defs" in base_uri:
                        # Resolve relative to common_defs base URI
                        full_ref = base_uri.split("#")[0] + ref_value
                        resolved = resolver.resolve(full_ref)
                    else:
                        # External reference or absolute reference
                        resolved = resolver.resolve(ref_value)
                    # Resolve any nested references in the resolved value
                    # Track the URI of the resolved schema for nested refs
                    resolved_uri, resolved_schema = resolved
                    # Use the resolved URI as base for nested refs if it's from common_defs
                    nested_base = resolved_uri if "common_defs" in resolved_uri else base_uri
                    return resolve_refs(resolved_schema, nested_base)
                except Exception:
                    # If resolution fails, return as-is
                    return obj
            elif "$ref" in obj:
                # Object with $ref and other properties (like allOf)
                # For allOf, we need to handle it specially
                if "allOf" in obj:
                    resolved_allof = []
                    for item in obj["allOf"]:
                        if isinstance(item, dict) and "$ref" in item:
                            try:
                                ref_value = item["$ref"]
                                # Handle relative references
                                if (
                                    ref_value.startswith("#")
                                    and base_uri
                                    and "common_defs" in base_uri
                                ):
                                    full_ref = base_uri.split("#")[0] + ref_value
                                    resolved = resolver.resolve(full_ref)
                                else:
                                    resolved = resolver.resolve(ref_value)
                                resolved_uri, resolved_schema = resolved
                                nested_base = (
                                    resolved_uri if "common_defs" in resolved_uri else base_uri
                                )
                                resolved_allof.append(resolve_refs(resolved_schema, nested_base))
                            except Exception:
                                resolved_allof.append(resolve_refs(item, base_uri))
                        else:
                            resolved_allof.append(resolve_refs(item, base_uri))
                    # Merge allOf items into the parent object
                    result = {k: v for k, v in obj.items() if k not in ("allOf", "$ref")}
                    for item in resolved_allof:
                        if isinstance(item, dict):
                            result.update(item)
                    return result
                else:
                    # Other $ref cases - try to resolve but keep other properties
                    new_obj = {}
                    for key, value in obj.items():
                        if key == "$ref":
                            try:
                                ref_value = value
                                # Handle relative references
                                if (
                                    ref_value.startswith("#")
                                    and base_uri
                                    and "common_defs" in base_uri
                                ):
                                    full_ref = base_uri.split("#")[0] + ref_value
                                    resolved = resolver.resolve(full_ref)
                                else:
                                    resolved = resolver.resolve(ref_value)
                                resolved_uri, resolved_schema = resolved
                                nested_base = (
                                    resolved_uri if "common_defs" in resolved_uri else base_uri
                                )
                                resolved_schema = resolve_refs(resolved_schema, nested_base)
                                if isinstance(resolved_schema, dict):
                                    new_obj.update(resolved_schema)
                            except Exception:
                                new_obj[key] = value
                        else:
                            new_obj[key] = resolve_refs(value, base_uri)
                    return new_obj
            else:
                # Regular dict - recurse into all values
                return {key: resolve_refs(value, base_uri) for key, value in obj.items()}
        elif isinstance(obj, list):
            # List - recurse into all items
            return [resolve_refs(item, base_uri) for item in obj]
        else:
            # Primitive value - return as-is
            return obj

    # Create a deep copy to avoid mutating the original
    resolved_schema = deepcopy(schema)
    return resolve_refs(resolved_schema)


def register_trading_tools(
    mcp: FastMCP,
    archetype_repo: ArchetypeRepository,
    schema_repo: ArchetypeSchemaRepository,
) -> None:
    """Register all trading strategy tools with the MCP server.

    Dependencies are injected so tests and callers can control which
    repositories (and therefore which databases/backends) are used.
    """

    # Note: Also available as archetypes://{kind} resources for browsing
    @mcp.tool()
    def get_archetypes(
        kind: str | None = Field(
            None,
            description="Optional filter by archetype kind. Valid values: 'entry', 'exit', 'gate', 'overlay'. If not provided, returns all archetypes.",
        ),
    ) -> GetArchetypesResponse:
        """
        Fetch the catalog of available trading strategy archetypes.

        This lightweight catalog allows an agent to choose an archetype for building
        trading strategies. There are 4 types of archetypes:

        - entry: Entry signals for opening positions (REQUIRED - every strategy needs at least one)
                 Examples: trend pullback, breakout, momentum
        - exit: Exit rules for closing positions (RECOMMENDED - most strategies need at least one)
                Examples: take profit, stop loss, trailing stop, time stop
        - gate: Conditional filters that allow/block other cards (OPTIONAL - use when you need conditional logic)
                Examples: regime gates, event risk windows
                Note: Gates execute before entries/exits and can block their execution
        - overlay: Modifiers that scale risk/size of other cards (OPTIONAL - use when you need dynamic sizing)
                  Examples: regime scalers
                  Note: Overlays execute after entries/exits and modify position sizing

        Usage tips:
        - Start with entries and exits (most strategies only need these)
        - Use gates only when you need conditional filtering (e.g., only trade in favorable regimes)
        - Use overlays only when you need dynamic risk scaling (e.g., reduce size in high volatility)
        - See AGENT_GUIDE.md for detailed usage patterns and examples

        **Agent behavior:**
        - When the user describes an informal strategy (e.g., "fade parabolic moves in BTC on the 1h"),
          map their intent to one or more archetype kinds first.
        - If you're unsure, default to listing common `entry` and `exit` archetypes and ask the user
          which fits best.
        - Prefer a small shortlist of plausible archetypes (2-4) instead of dumping all.

        **Terminology:**
        - **kind**: broad archetype category (`entry`, `exit`, `gate`, `overlay`).
        - **type**: specific archetype identifier (e.g. `entry.trend_pullback`).
        - **role**: how a card is attached in a strategy; for now identical to `kind` (`entry`, `exit`, `gate`, `overlay`).

        Args:
            kind: Optional filter to return only archetypes of a specific kind.
                  Valid values: 'entry', 'exit', 'gate', 'overlay'.
                  If not provided, returns all archetypes.

        Returns:
            GetArchetypesResponse containing a list of archetypes with metadata
        """
        # 1. Fetch domain models from repository (repository handles DB conversion)
        archetypes = archetype_repo.get_non_deprecated()

        # 2. Filter by kind if provided
        if kind is not None:
            valid_kinds = {"entry", "exit", "gate", "overlay"}
            if kind not in valid_kinds:
                from src.tools.errors import validation_error

                raise validation_error(
                    message=f"Invalid kind '{kind}'. Valid values are: {', '.join(sorted(valid_kinds))}",
                    recovery_hint=f"Browse archetypes://all resource to see all archetypes, or use one of: {', '.join(sorted(valid_kinds))}",
                )
            archetypes = [arch for arch in archetypes if arch.kind == kind]

        # 3. Convert to API response models (only expose what's needed)
        archetype_infos = [
            ArchetypeInfo(
                id=arch.id,
                version=arch.version,
                title=arch.title,
                summary=arch.summary,
                kind=arch.kind,
                tags=arch.tags,
                required_slots=arch.required_slots,
                schema_etag=arch.schema_etag,
                deprecated=arch.deprecated,
                intent_phrases=[],  # Could be added to Firestore documents later
            )
            for arch in archetypes
        ]

        return GetArchetypesResponse(
            types=archetype_infos,
            as_of=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

    # Note: Also available as archetype-schemas://{kind} resources for browsing
    @mcp.tool()
    def get_archetype_schema(
        type: str = Field(..., description="Archetype identifier (e.g., 'entry.trend_pullback')"),
        if_none_match: str | None = Field(
            None,
            description="Optional ETag for conditional requests. If provided and matches, indicates client already has this version.",
        ),
    ) -> GetArchetypeSchemaResponse:
        """
        Fetch the authoritative JSON Schema for a given archetype.

        This provides the full schema definition including:
        - JSON Schema for validation
        - Constraints (min_history_bars, pit_safe, etc.)
        - Slot hints (ranges, units, defaults)
        - Examples of valid slot configurations

        The schema can be used to validate and construct cards for this archetype.
        Use the etag for caching - if you already have the schema with this etag,
        you can skip fetching it again.

        Args:
            type: Archetype identifier
            if_none_match: Optional ETag for conditional requests

        Returns:
            GetArchetypeSchemaResponse containing the full schema definition

        Raises:
            StructuredToolError: With error code SCHEMA_NOT_FOUND if archetype schema not found

        Error Handling:
            Errors include structured information with error_code,
            recovery_hint, and details for agentic decision-making.
        """
        # Fetch schema from repository
        schema = schema_repo.get_by_type_id(type)

        if schema is None:
            raise StructuredToolError(
                message=f"Archetype schema not found: {type}",
                error_code=ErrorCode.ARCHETYPE_NOT_FOUND,
                recovery_hint="Use get_archetypes to see available archetypes.",
                details={"type_id": type},
            )

        # Check if client already has this version (ETag matching)
        # Note: For MVP, we just return the schema. In the future, we could return
        # a 304 Not Modified response if if_none_match matches the etag.
        if if_none_match and if_none_match == schema.etag:
            # Client already has this version - could return 304 in HTTP context
            # For MCP, we still return the schema but the client can check the etag
            pass

        # Resolve all $ref references to make schema self-contained for agents
        resolved_schema = _resolve_schema_references(schema.json_schema)

        # Convert domain model to API response
        # Note: We manually construct the response to match GetArchetypeSchemaResponse structure
        # (which doesn't include 'kind' field, unlike the resource JSON format)
        return GetArchetypeSchemaResponse(
            type_id=schema.type_id,
            schema_version=schema.schema_version,
            etag=schema.etag,
            json_schema=resolved_schema,
            constraints={
                "min_history_bars": schema.constraints.min_history_bars,
                "pit_safe": schema.constraints.pit_safe,
                "warmup_hint": schema.constraints.warmup_hint,
            },
            slot_hints=schema.slot_hints,
            examples=[
                {
                    "human": ex.human,
                    "slots": ex.slots,
                }
                for ex in schema.examples
            ],
            updated_at=schema.updated_at,
        )

    @mcp.tool()
    def get_schema_example(
        type: str = Field(..., description="Archetype identifier (e.g., 'entry.trend_pullback')"),
        example_index: int = Field(
            0, description="Index of example to return (default: 0 for first example)"
        ),
    ) -> GetSchemaExampleResponse:
        """
        Get a ready-to-use example slot configuration for an archetype.

        This tool returns a complete, valid slot configuration that can be directly
        used when creating a card. It's designed to reduce friction when
        constructing slots manually.

        IMPORTANT: Before using this tool, you MUST first browse resources to discover
        available archetypes. Do NOT use this tool without first checking resources.

        Required workflow:
        1. FIRST: Browse archetypes://{kind} or archetypes://all resources to discover available archetypes
        2. Browse archetype-schemas://{kind} resources to see full schema details and available examples
        3. Only then use get_schema_example(type) to get a ready-to-use example for a specific archetype
        4. Optionally modify the example slots to fit your needs
        5. Use add_card with the slots to create and add the card to a strategy

        **Agent behavior:**
        - Use this to propose a concrete starting configuration to the user.
        - Present key slots (like timeframe, stop distance, position size rules) in plain language
          and confirm or adjust with the user before creating a card.
        - If the user is vague ("I like trend pullbacks"), ask targeted questions about timeframe,
          risk per trade, and instruments, then adjust the example slots.

        Args:
            type: Archetype identifier (must be discovered from resources first)
            example_index: Index of example to return (0-based, defaults to 0)

        Returns:
            GetSchemaExampleResponse with ready-to-use example slots

        Raises:
            StructuredToolError: With error code ARCHETYPE_NOT_FOUND if archetype schema not found
            StructuredToolError: With error code SCHEMA_VALIDATION_ERROR if example_index is out of range

        Error Handling:
            Errors include structured information with error_code,
            recovery_hint, and details for agentic decision-making.
        """
        # Fetch schema from repository
        schema = schema_repo.get_by_type_id(type)

        if schema is None:
            raise not_found_error(
                resource_type="Archetype",
                resource_id=type,
                recovery_hint="Browse archetypes://all resource to see available archetypes.",
            )

        # Check if example_index is valid
        if example_index < 0 or example_index >= len(schema.examples):
            from src.tools.errors import schema_validation_error

            raise schema_validation_error(
                type_id=type,
                errors=[
                    f"Example index {example_index} is out of range. Schema has {len(schema.examples)} example(s)."
                ],
                recovery_hint=f"Browse archetype-schemas://{type.split('.', 1)[0]} resource to see all available examples, or use index 0-{len(schema.examples) - 1}.",
            )

        # Get the requested example
        example = schema.examples[example_index]

        return GetSchemaExampleResponse(
            type_id=schema.type_id,
            example_slots=example.slots,
            human_description=example.human,
            schema_etag=schema.etag,
        )
