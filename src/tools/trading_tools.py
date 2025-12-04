"""Trading strategy tools for MCP server."""

from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.db.archetype_repository import ArchetypeRepository
from src.db.archetype_schema_repository import ArchetypeSchemaRepository
from src.tools.errors import not_found_error


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


def register_trading_tools(
    mcp: FastMCP,
    archetype_repo: ArchetypeRepository,
    schema_repo: ArchetypeSchemaRepository,
) -> None:
    """Register all trading strategy tools with the MCP server.

    Dependencies are injected so tests and callers can control which
    repositories (and therefore which databases/backends) are used.
    """

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
        - entry: Entry signals for opening positions (e.g., trend pullback, breakout)
        - exit: Exit rules for closing positions (e.g., take profit, stop loss, trailing stop)
        - gate: Conditional filters that allow/block other cards (e.g., regime gates, event risk windows)
        - overlay: Modifiers that scale risk/size of other cards (e.g., regime scalers)

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
                    recovery_hint=f"Use get_archetypes() without kind parameter to see all archetypes, or use one of: {', '.join(sorted(valid_kinds))}",
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
            StructuredToolError: With error code SCHEMA_NOT_FOUND if archetype schema not found (non-retryable)

        Error Handling:
            Errors include structured information with error_code, retryable flag,
            recovery_hint, and details for agentic decision-making.
        """
        # Fetch schema from repository
        schema = schema_repo.get_by_type_id(type)

        if schema is None:
            raise not_found_error(
                resource_type="Schema",
                resource_id=type,
                recovery_hint="Use get_archetypes to see available archetypes.",
            )

        # Check if client already has this version (ETag matching)
        # Note: For MVP, we just return the schema. In the future, we could return
        # a 304 Not Modified response if if_none_match matches the etag.
        if if_none_match and if_none_match == schema.etag:
            # Client already has this version - could return 304 in HTTP context
            # For MCP, we still return the schema but the client can check the etag
            pass

        # Convert domain model to API response
        return GetArchetypeSchemaResponse(
            type_id=schema.type_id,
            schema_version=schema.schema_version,
            etag=schema.etag,
            json_schema=schema.json_schema,
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

        Recommended workflow:
        1. Use get_archetypes to find available archetypes
        2. Use get_schema_example(type) to get a ready-to-use example
        3. Optionally modify the example slots to fit your needs
        4. Use create_card with the slots and schema_etag from this response

        Args:
            type: Archetype identifier
            example_index: Index of example to return (0-based, defaults to 0)

        Returns:
            GetSchemaExampleResponse with ready-to-use example slots

        Raises:
            StructuredToolError: With error code SCHEMA_NOT_FOUND if archetype schema not found (non-retryable)
            StructuredToolError: With error code VALIDATION_ERROR if example_index is out of range (non-retryable)

        Error Handling:
            Errors include structured information with error_code, retryable flag,
            recovery_hint, and details for agentic decision-making.
        """
        # Fetch schema from repository
        schema = schema_repo.get_by_type_id(type)

        if schema is None:
            raise not_found_error(
                resource_type="Schema",
                resource_id=type,
                recovery_hint="Use get_archetypes to see available archetypes.",
            )

        # Check if example_index is valid
        if example_index < 0 or example_index >= len(schema.examples):
            from src.tools.errors import ErrorCode, validation_error

            raise validation_error(
                error_code=ErrorCode.VALIDATION_ERROR,
                message=f"Example index {example_index} is out of range. Schema has {len(schema.examples)} example(s).",
                recovery_hint=f"Use get_archetype_schema('{type}') to see all available examples, or use index 0-{len(schema.examples) - 1}.",
            )

        # Get the requested example
        example = schema.examples[example_index]

        return GetSchemaExampleResponse(
            type_id=schema.type_id,
            example_slots=example.slots,
            human_description=example.human,
            schema_etag=schema.etag,
        )
