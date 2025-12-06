"""Tests for get_schema_example tool."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from test_helpers import call_tool, get_structured_error, run_async

from src.tools.errors import ErrorCode
from src.tools.trading_tools import GetSchemaExampleResponse


def test_get_schema_example_returns_example(trading_tools_mcp):
    """Test getting a schema example returns ready-to-use slots."""
    # Run: get schema example
    result = run_async(
        call_tool(
            trading_tools_mcp,
            "get_schema_example",
            {
                "type": "entry.trend_pullback",
            },
        )
    )

    # Assert: verify response
    response = GetSchemaExampleResponse(**result)
    assert response.type_id == "entry.trend_pullback"
    assert response.example_slots is not None
    assert isinstance(response.example_slots, dict)
    assert "context" in response.example_slots
    assert "event" in response.example_slots
    assert "action" in response.example_slots
    assert "risk" in response.example_slots
    assert response.schema_etag is not None
    assert response.human_description is not None


def test_get_schema_example_specific_index(trading_tools_mcp):
    """Test getting a specific example by index."""
    # Run: get schema example with index
    result = run_async(
        call_tool(
            trading_tools_mcp,
            "get_schema_example",
            {
                "type": "entry.trend_pullback",
                "example_index": 0,
            },
        )
    )

    # Assert: verify response
    response = GetSchemaExampleResponse(**result)
    assert response.type_id == "entry.trend_pullback"
    assert response.example_slots is not None


def test_get_schema_example_not_found(trading_tools_mcp):
    """Test getting example for non-existent archetype returns error."""
    # Run: try to get example for non-existent archetype
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                trading_tools_mcp,
                "get_schema_example",
                {
                    "type": "nonexistent.archetype",
                },
            )
        )

    # Assert: should get error with helpful guidance
    structured_error = get_structured_error(exc_info.value)
    assert structured_error is not None
    assert structured_error.error_code == ErrorCode.ARCHETYPE_NOT_FOUND
    assert structured_error.retryable is False
    assert (
        "browse" in structured_error.recovery_hint.lower()
        or "archetypes://" in structured_error.recovery_hint.lower()
    )


def test_get_schema_example_invalid_index(trading_tools_mcp):
    """Test getting example with invalid index returns error."""
    # Run: try to get example with out-of-range index
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                trading_tools_mcp,
                "get_schema_example",
                {
                    "type": "entry.trend_pullback",
                    "example_index": 999,
                },
            )
        )

    # Assert: should get validation error
    # The error might be wrapped differently, so check the message
    error_message = str(exc_info.value).lower()
    assert "index" in error_message or "range" in error_message or "validation" in error_message
    # Try to get structured error, but it's okay if it's None (FastMCP might wrap it differently)
    structured_error = get_structured_error(exc_info.value)
    if structured_error is not None:
        assert structured_error.error_code == ErrorCode.SCHEMA_VALIDATION_ERROR
        assert structured_error.retryable is False


def test_get_schema_example_can_create_card(trading_tools_mcp, card_tools_mcp):
    """Test that example slots can be used directly to create a card."""
    # Setup: get example
    example_result = run_async(
        call_tool(
            trading_tools_mcp,
            "get_schema_example",
            {
                "type": "entry.trend_pullback",
            },
        )
    )
    example = GetSchemaExampleResponse(**example_result)

    # Run: create card with example slots (schema_etag is now internal)
    card_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": example.type_id,
                "slots": example.example_slots,
            },
        )
    )

    # Assert: card created successfully
    assert card_result["card_id"] is not None
    assert card_result["type"] == "entry.trend_pullback"
