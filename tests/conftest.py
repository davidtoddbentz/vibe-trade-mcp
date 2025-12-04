"""Pytest configuration and fixtures."""

import os
import socket

import pytest
from mcp.server.fastmcp import FastMCP

from src.db.archetype_repository import ArchetypeRepository
from src.db.archetype_schema_repository import ArchetypeSchemaRepository
from src.db.card_repository import CardRepository
from src.db.firestore_client import FirestoreClient
from src.db.strategy_repository import StrategyRepository
from src.tools.card_tools import register_card_tools
from src.tools.strategy_tools import register_strategy_tools
from src.tools.trading_tools import register_trading_tools


@pytest.fixture
def archetype_repository():
    """Create an ArchetypeRepository for testing (reads from JSON file)."""
    repo = ArchetypeRepository()
    # Force fresh load by clearing cache
    repo._archetypes = None
    return repo


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


@pytest.fixture
def firestore_client(monkeypatch):
    """Create a Firestore client for testing (uses emulator).

    This fixture:
    1. Sets up environment variables to point to the emulator
    2. Fast-fails if emulator is not accessible
    3. Resets the FirestoreClient singleton between tests
    """
    # Set environment variables for emulator
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8081")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("FIRESTORE_DATABASE", "(default)")

    # Fast-fail check: verify emulator is accessible
    emulator_host = os.getenv("FIRESTORE_EMULATOR_HOST", "localhost:8081")
    host, port = emulator_host.split(":")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, int(port)))
        sock.close()
        if result != 0:
            pytest.fail(
                f"Firestore emulator not accessible at {emulator_host}. "
                "Start it with: make emulator"
            )
    except Exception as e:
        pytest.fail(f"Could not check Firestore emulator accessibility: {e}")

    # Get client (database=None for emulator default)
    client = FirestoreClient.get_client(project="test-project", database=None)

    yield client


@pytest.fixture
def card_repository(firestore_client):
    """Create a CardRepository for testing."""
    return CardRepository(client=firestore_client)


@pytest.fixture
def card_tools_mcp(card_repository, schema_repository):
    """Create an MCP server instance with card tools registered."""
    mcp = FastMCP("test-server")
    register_card_tools(mcp, card_repository, schema_repository)
    return mcp


@pytest.fixture
def strategy_repository(firestore_client):
    """Create a StrategyRepository for testing."""
    return StrategyRepository(client=firestore_client)


@pytest.fixture
def strategy_tools_mcp(strategy_repository, card_repository, schema_repository):
    """Create an MCP server instance with strategy tools registered."""
    mcp = FastMCP("test-server")
    register_strategy_tools(mcp, strategy_repository, card_repository, schema_repository)
    return mcp
