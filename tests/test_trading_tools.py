"""Tests for trading strategy MCP tools."""

import asyncio
import json
from pathlib import Path

import pytest
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from src.tools.trading_tools import (
    ArchetypeInfo,
    GetArchetypesResponse,
    register_trading_tools,
)

# Load .env file if it exists (for local development)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


def extract_tool_result(result):
    """Extract the actual result from FastMCP's call_tool return value.

    FastMCP returns a tuple (content, result_dict) where content is a list
    of TextContent objects and result_dict is the parsed result.
    """
    if isinstance(result, tuple):
        content, result_dict = result
        # If result_dict is a dict (successful result), return it
        if isinstance(result_dict, dict):
            return result_dict
        # Otherwise, extract from content (TextContent objects)
        if content and len(content) > 0:
            text = content[0].text if hasattr(content[0], "text") else str(content[0])
            # Parse JSON string to dict
            return json.loads(text)
        return {}
    # If it's already a dict, return it
    return result if isinstance(result, dict) else {}


def test_trading_tools_registered():
    """Test that trading tools are registered with the server."""
    mcp = FastMCP("test-server")
    register_trading_tools(mcp)

    async def check_tools():
        tools = await mcp.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "get_archetypes" in tool_names, "Tool get_archetypes not found"

    asyncio.run(check_tools())


def test_get_archetypes_tool_exists():
    """Test that get_archetypes tool exists and has correct signature."""
    mcp = FastMCP("test")
    register_trading_tools(mcp)

    async def check_tool():
        tools = await mcp.list_tools()
        tool = next((t for t in tools if t.name == "get_archetypes"), None)

        assert tool is not None
        assert tool.name == "get_archetypes"
        # Should have no required parameters
        assert "properties" in tool.inputSchema
        assert len(tool.inputSchema.get("properties", {})) == 0

    asyncio.run(check_tool())


def test_get_archetypes_response_model():
    """Test GetArchetypesResponse Pydantic model."""
    archetype_info = ArchetypeInfo(
        id="signal.test",
        version=1,
        title="Test Archetype",
        summary="A test archetype",
        kind="signal",
        tags=["test"],
        required_slots=["tf", "symbol"],
        schema_etag='W/"test.v1"',
        deprecated=False,
        intent_phrases=[],
    )

    response = GetArchetypesResponse(
        types=[archetype_info],
        as_of="2025-01-01T00:00:00Z",
    )

    assert len(response.types) == 1
    assert response.types[0].id == "signal.test"
    assert response.as_of == "2025-01-01T00:00:00Z"


def test_get_archetypes_tool_functionality(archetype_repository, sample_archetype):
    """Test that get_archetypes tool actually works with real data."""
    mcp = FastMCP("test")
    register_trading_tools(mcp)

    async def test_get_archetypes():
        result = await mcp.call_tool("get_archetypes", {})
        assert result is not None

        # Extract the actual result from FastMCP's tuple return
        result_dict = extract_tool_result(result)

        # Parse the response
        response = GetArchetypesResponse(**result_dict)

        # Should have at least one archetype (our test one)
        assert len(response.types) >= 1

        # Check that our test archetype is in the results
        test_archetype = next(
            (arch for arch in response.types if arch.id == "signal.test_archetype"), None
        )
        assert test_archetype is not None
        assert test_archetype.title == "Test Archetype"
        assert test_archetype.kind == "signal"
        assert "tf" in test_archetype.required_slots
        assert "symbol" in test_archetype.required_slots

        # Check as_of is a valid ISO8601 timestamp
        assert response.as_of is not None
        # Should end with Z or have timezone
        assert response.as_of.endswith("Z") or "+" in response.as_of or "-" in response.as_of[-6:]

    asyncio.run(test_get_archetypes())


def test_get_archetypes_filters_deprecated(archetype_repository):
    """Test that get_archetypes filters out deprecated archetypes."""
    mcp = FastMCP("test")
    register_trading_tools(mcp)

    # Create a deprecated archetype
    deprecated_data = {
        "version": 1,
        "title": "Deprecated Archetype",
        "summary": "This is deprecated",
        "kind": "signal",
        "tags": ["test"],
        "required_slots": ["tf"],
        "schema_etag": 'W/"deprecated.v1"',
        "deprecated": True,  # This should be filtered out
        "hints": {},
        "updated_at": "2025-01-01T00:00:00Z",
    }
    archetype_repository.create_or_update("signal.deprecated", deprecated_data)

    async def test_filtering():
        result = await mcp.call_tool("get_archetypes", {})
        result_dict = extract_tool_result(result)
        response = GetArchetypesResponse(**result_dict)

        # Deprecated archetype should not be in results
        deprecated = next((arch for arch in response.types if arch.id == "signal.deprecated"), None)
        assert deprecated is None, "Deprecated archetype should be filtered out"

    asyncio.run(test_filtering())

    # Cleanup
    archetype_repository.delete("signal.deprecated")


def test_get_archetypes_empty_database(archetype_repository):
    """Test that get_archetypes works with empty database."""
    mcp = FastMCP("test")
    register_trading_tools(mcp)

    # Delete all archetypes
    archetype_repository.delete_all()

    async def test_empty():
        result = await mcp.call_tool("get_archetypes", {})
        result_dict = extract_tool_result(result)
        response = GetArchetypesResponse(**result_dict)

        # Should return empty list, not error
        assert response.types == []
        assert response.as_of is not None

    asyncio.run(test_empty())


def test_archetype_info_model_validation():
    """Test ArchetypeInfo model validation."""
    # Valid archetype
    valid = ArchetypeInfo(
        id="signal.test",
        version=1,
        title="Test",
        summary="Test summary",
        kind="signal",
        tags=[],
        required_slots=["tf"],
        schema_etag='W/"test.v1"',
        deprecated=False,
        intent_phrases=[],
    )
    assert valid.id == "signal.test"

    # Missing required field should raise error
    from pydantic import ValidationError

    with pytest.raises(ValidationError):  # Pydantic validation error
        ArchetypeInfo(
            version=1,
            title="Test",
            summary="Test summary",
            kind="signal",
            required_slots=["tf"],
            schema_etag='W/"test.v1"',
        )


def test_get_archetypes_response_structure(archetype_repository, sample_archetype):
    """Test that get_archetypes returns properly structured response."""
    mcp = FastMCP("test")
    register_trading_tools(mcp)

    async def test_structure():
        result = await mcp.call_tool("get_archetypes", {})
        result_dict = extract_tool_result(result)
        response = GetArchetypesResponse(**result_dict)

        # Check structure
        assert hasattr(response, "types")
        assert hasattr(response, "as_of")
        assert isinstance(response.types, list)
        assert isinstance(response.as_of, str)

        # Check each archetype has required fields
        for arch in response.types:
            assert hasattr(arch, "id")
            assert hasattr(arch, "version")
            assert hasattr(arch, "title")
            assert hasattr(arch, "summary")
            assert hasattr(arch, "kind")
            assert hasattr(arch, "required_slots")
            assert hasattr(arch, "schema_etag")
            assert hasattr(arch, "deprecated")
            assert hasattr(arch, "intent_phrases")

            # Check types
            assert isinstance(arch.id, str)
            assert isinstance(arch.version, int)
            assert isinstance(arch.title, str)
            assert isinstance(arch.summary, str)
            assert isinstance(arch.kind, str)
            assert isinstance(arch.required_slots, list)
            assert isinstance(arch.schema_etag, str)
            assert isinstance(arch.deprecated, bool)
            assert isinstance(arch.intent_phrases, list)

    asyncio.run(test_structure())
