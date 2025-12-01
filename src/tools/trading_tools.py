"""Trading strategy tools for MCP server."""

from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.db.archetype_repository import ArchetypeRepository
from src.db.archetype_schema_repository import ArchetypeSchemaRepository


class ArchetypeInfo(BaseModel):
    """Lightweight archetype info for MCP responses.

    This is the API contract - only includes fields needed by agents.
    """

    id: str = Field(..., description="Archetype identifier")
    version: int = Field(..., description="Archetype version number")
    title: str = Field(..., description="Human-readable title")
    summary: str = Field(..., description="Brief description")
    kind: str = Field(..., description="Archetype kind (e.g., 'signal', 'gate')")
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
    def get_archetypes() -> GetArchetypesResponse:
        """
        Fetch the catalog of available trading strategy archetypes.

        This lightweight catalog allows an agent to choose an archetype for building
        trading strategies. Each archetype represents a type of trading signal, risk
        management rule, or execution strategy.

        Returns:
            GetArchetypesResponse containing a list of archetypes with metadata
        """
        # 1. Fetch domain models from repository (repository handles DB conversion)
        archetypes = archetype_repo.get_non_deprecated()

        # 2. Convert to API response models (only expose what's needed)
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
    def get_archetype_schema(request: GetArchetypeSchemaRequest) -> GetArchetypeSchemaResponse:
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
            request: GetArchetypeSchemaRequest with type (required) and optional if_none_match

        Returns:
            GetArchetypeSchemaResponse containing the full schema definition
        """
        # Fetch schema from repository
        schema = schema_repo.get_by_type_id(request.type)

        if schema is None:
            raise ValueError(f"Archetype schema not found: {request.type}")

        # Check if client already has this version (ETag matching)
        # Note: For MVP, we just return the schema. In the future, we could return
        # a 304 Not Modified response if if_none_match matches the etag.
        if request.if_none_match and request.if_none_match == schema.etag:
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
