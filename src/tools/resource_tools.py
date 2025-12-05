"""MCP resources for archetype data.

This module exposes archetype catalog and schema data as MCP resources,
making it easier for agents to discover and browse available archetypes
without needing to call tools first.
"""

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.db.archetype_repository import ArchetypeRepository
from src.db.archetype_schema_repository import ArchetypeSchemaRepository
from src.tools.trading_tools import _resolve_schema_references


def register_archetype_resources(
    mcp: FastMCP,
    archetype_repo: ArchetypeRepository,
    schema_repo: ArchetypeSchemaRepository,
) -> None:
    """Register archetype data as MCP resources.

    This exposes archetype catalogs and schemas as resources that agents
    can browse and load for context. Resources are organized by kind:
    - archetypes://entry - Entry archetypes catalog
    - archetypes://exit - Exit archetypes catalog
    - archetypes://gate - Gate archetypes catalog
    - archetypes://overlay - Overlay archetypes catalog
    - archetypes://all - All archetypes catalog
    - archetype-schemas://entry - Entry archetype schemas
    - archetype-schemas://exit - Exit archetype schemas
    - archetype-schemas://gate - Gate archetype schemas
    - archetype-schemas://overlay - Overlay archetype schemas
    - archetype-schemas://all - All archetype schemas

    Args:
        mcp: FastMCP server instance
        archetype_repo: Repository for archetype data
        schema_repo: Repository for archetype schema data
    """
    # Register archetype catalog resources
    for kind in ["entry", "exit", "gate", "overlay", "all"]:
        # Register read handler for this resource (capture kind in closure)
        # Using @mcp.resource decorator which handles Resource creation correctly
        def make_archetypes_handler(k: str):
            @mcp.resource(
                uri=f"archetypes://{k}",
                name=f"Archetypes ({k})",
                description=f"Catalog of {k} trading strategy archetypes with metadata, tags, and summaries",
                mime_type="application/json",
            )
            def read_archetypes_resource() -> str:
                """Read archetype catalog resource."""
                return _get_archetypes_json(archetype_repo, k)

            return read_archetypes_resource

        make_archetypes_handler(kind)

    # Register schema resources
    for kind in ["entry", "exit", "gate", "overlay", "all"]:
        # Register read handler for this resource (capture kind in closure)
        # Using @mcp.resource decorator which handles Resource creation correctly
        def make_schemas_handler(k: str):
            @mcp.resource(
                uri=f"archetype-schemas://{k}",
                name=f"Archetype Schemas ({k})",
                description=f"JSON schemas for {k} archetypes with slot definitions and validation rules",
                mime_type="application/json",
            )
            def read_schemas_resource() -> str:
                """Read archetype schema resource."""
                return _get_schemas_json(schema_repo, k)

            return read_schemas_resource

        make_schemas_handler(kind)

    # Register AGENT_GUIDE.md as a resource
    @mcp.resource(
        uri="agent-guide://readme",
        name="Agent Guide",
        description="Comprehensive guide for AI agents on using trading strategy archetypes (entries, exits, gates, overlays) with usage patterns and examples",
        mime_type="text/markdown",
    )
    def read_agent_guide() -> str:
        """Read AGENT_GUIDE.md resource."""
        project_root = Path(__file__).parent.parent.parent
        guide_path = project_root / "AGENT_GUIDE.md"
        try:
            with open(guide_path) as f:
                return f.read()
        except FileNotFoundError:
            return "# Agent Guide\n\nGuide not found. Please check the repository."


def _get_archetypes_json(repo: ArchetypeRepository, kind: str) -> str:
    """Get archetypes as JSON string, filtered by kind.

    Args:
        repo: Archetype repository
        kind: Kind filter ('entry', 'exit', 'gate', 'overlay', or 'all')

    Returns:
        JSON string with archetypes array
    """
    all_archetypes = repo.get_non_deprecated()

    # Filter by kind if not 'all'
    if kind == "all":
        archetypes = all_archetypes
    else:
        archetypes = [arch for arch in all_archetypes if arch.kind == kind]

    # Convert to dict format for JSON serialization using Pydantic's model_dump
    archetypes_data = [arch.model_dump() for arch in archetypes]

    # Return as JSON with same structure as data files
    return json.dumps({"archetypes": archetypes_data}, indent=2)


def _schema_to_dict(schema: Any, resolve_refs: bool = True) -> dict[str, Any]:
    """Convert an ArchetypeSchema model to a dictionary.

    This is shared logic used by both get_archetype_schema tool and resource handlers.
    Optionally resolves $ref references to make schemas self-contained for agents.

    Args:
        schema: ArchetypeSchema domain model
        resolve_refs: If True, resolve $ref references in json_schema (default: True)

    Returns:
        Dictionary representation of the schema, matching the original JSON structure
    """
    schema_dict = schema.model_dump()

    # Extract kind from type_id and add it to match original JSON structure
    schema_kind = schema.type_id.split(".", 1)[0]
    schema_dict["kind"] = schema_kind

    # Resolve $ref references if requested (makes schema self-contained for agents)
    if resolve_refs:
        schema_dict["json_schema"] = _resolve_schema_references(schema.json_schema)

    return schema_dict


def _get_schemas_json(repo: ArchetypeSchemaRepository, kind: str) -> str:
    """Get archetype schemas as JSON string, filtered by kind.

    Uses shared _schema_to_dict function to convert schemas consistently with
    the get_archetype_schema tool.

    Args:
        repo: Schema repository
        kind: Kind filter ('entry', 'exit', 'gate', 'overlay', or 'all')

    Returns:
        JSON string with schemas array
    """
    all_schemas = repo.get_all()

    # Filter by kind if not 'all'
    # Extract kind from type_id (e.g., "entry.trend_pullback" -> "entry")
    if kind == "all":
        schemas = all_schemas
    else:
        schemas = [schema for schema in all_schemas if schema.type_id.split(".", 1)[0] == kind]

    # Convert to dict format using shared function (resolves $ref references)
    schemas_data = [_schema_to_dict(schema) for schema in schemas]

    # Return as JSON with same structure as data files
    return json.dumps({"schemas": schemas_data}, indent=2)
