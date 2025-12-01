"""Tests for get_archetype_schema tool."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from test_helpers import call_tool, run_async

from src.tools.trading_tools import GetArchetypeSchemaResponse


def test_get_archetype_schema_returns_schema(trading_tools_mcp):
    """Test that get_archetype_schema returns the full schema for an archetype."""
    # Setup: use existing schema data from data/archetype_schema.json

    # Run: call the tool
    result = run_async(
        call_tool(
            trading_tools_mcp,
            "get_archetype_schema",
            {"type": "signal.trend_pullback"},
        )
    )

    # Assert: verify response structure and content
    response = GetArchetypeSchemaResponse(**result)
    assert response.type_id == "signal.trend_pullback"
    assert response.schema_version == 1
    assert response.etag is not None
    assert response.json_schema is not None
    assert isinstance(response.json_schema, dict)
    assert "required" in response.json_schema
    assert "properties" in response.json_schema
    assert "constraints" in response.model_dump()
    assert "examples" in response.model_dump()
    assert len(response.examples) > 0

    # Check that required slots are in the schema
    required = response.json_schema.get("required", [])
    assert "tf" in required
    assert "symbol" in required
    assert "direction" in required


def test_get_archetype_schema_with_etag(trading_tools_mcp):
    """Test that get_archetype_schema handles if_none_match parameter."""
    # Setup: get initial schema to obtain etag
    result1 = run_async(
        call_tool(
            trading_tools_mcp,
            "get_archetype_schema",
            {"type": "signal.trend_pullback"},
        )
    )
    response1 = GetArchetypeSchemaResponse(**result1)
    etag = response1.etag

    # Run: request with if_none_match
    result2 = run_async(
        call_tool(
            trading_tools_mcp,
            "get_archetype_schema",
            {"type": "signal.trend_pullback", "if_none_match": etag},
        )
    )

    # Assert: should still return the schema (MCP doesn't support 304)
    response2 = GetArchetypeSchemaResponse(**result2)
    assert response2.etag == etag
    assert response2.type_id == "signal.trend_pullback"


def test_get_archetype_schema_not_found(trading_tools_mcp):
    """Test that get_archetype_schema raises error for unknown archetype."""
    # Setup: use a non-existent archetype type

    # Run & Assert: should raise ToolError (FastMCP wraps ValueError)
    with pytest.raises(ToolError):
        run_async(
            call_tool(
                trading_tools_mcp,
                "get_archetype_schema",
                {"type": "signal.nonexistent"},
            )
        )


def test_get_archetype_schema_response_structure(trading_tools_mcp):
    """Test that get_archetype_schema returns properly structured response."""
    # Setup: use existing schema data

    # Run: call the tool
    result = run_async(
        call_tool(
            trading_tools_mcp,
            "get_archetype_schema",
            {"type": "signal.trend_pullback"},
        )
    )

    # Assert: verify response structure
    response = GetArchetypeSchemaResponse(**result)
    assert hasattr(response, "type_id")
    assert hasattr(response, "schema_version")
    assert hasattr(response, "etag")
    assert hasattr(response, "json_schema")
    assert hasattr(response, "constraints")
    assert hasattr(response, "slot_hints")
    assert hasattr(response, "examples")
    assert hasattr(response, "updated_at")

    # Check types
    assert isinstance(response.type_id, str)
    assert isinstance(response.schema_version, int)
    assert isinstance(response.etag, str)
    assert isinstance(response.json_schema, dict)
    assert isinstance(response.constraints, dict)
    assert isinstance(response.slot_hints, dict)
    assert isinstance(response.examples, list)
    assert isinstance(response.updated_at, str)


def test_get_archetype_schema_constraints(trading_tools_mcp):
    """Test that get_archetype_schema includes constraints."""
    # Setup: use existing schema data

    # Run: call the tool
    result = run_async(
        call_tool(
            trading_tools_mcp,
            "get_archetype_schema",
            {"type": "signal.trend_pullback"},
        )
    )

    # Assert: verify constraints are present
    response = GetArchetypeSchemaResponse(**result)
    constraints = response.constraints
    assert "min_history_bars" in constraints
    assert "pit_safe" in constraints
    assert "warmup_hint" in constraints


def test_get_archetype_schema_examples(trading_tools_mcp):
    """Test that get_archetype_schema includes examples."""
    # Setup: use existing schema data

    # Run: call the tool
    result = run_async(
        call_tool(
            trading_tools_mcp,
            "get_archetype_schema",
            {"type": "signal.trend_pullback"},
        )
    )

    # Assert: verify examples are present and structured correctly
    response = GetArchetypeSchemaResponse(**result)
    assert len(response.examples) > 0
    for example in response.examples:
        assert "human" in example
        assert "slots" in example
        assert isinstance(example["human"], str)
        assert isinstance(example["slots"], dict)
