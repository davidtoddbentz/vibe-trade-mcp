"""Trading strategy tools for MCP server."""

from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.db.archetype_repository import ArchetypeRepository


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


def register_trading_tools(mcp: FastMCP) -> None:
    """Register all trading strategy tools with the MCP server."""

    # Initialize repository (data layer - Firestore)
    archetype_repo = ArchetypeRepository()

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
