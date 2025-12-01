"""Pytest configuration and fixtures."""

import pytest
from mcp.server.fastmcp import FastMCP

from src.db.archetype_repository import ArchetypeRepository
from src.db.archetype_schema_repository import ArchetypeSchemaRepository
from src.tools.trading_tools import register_trading_tools


@pytest.fixture
def archetype_repository():
    """Create an ArchetypeRepository for testing (reads from JSON file)."""
    return ArchetypeRepository()


@pytest.fixture
def schema_repository():
    """Create an ArchetypeSchemaRepository for testing (reads from JSON file)."""
    return ArchetypeSchemaRepository()


@pytest.fixture
def trading_tools_mcp(archetype_repository, schema_repository):
    """Create an MCP server instance with trading tools registered.

    This fixture provides a ready-to-use MCP server with all trading tools
    registered and dependencies injected. Data is read from JSON files.
    Use this in all tool tests.
    """
    mcp = FastMCP("test-server")
    register_trading_tools(mcp, archetype_repository, schema_repository)
    return mcp
