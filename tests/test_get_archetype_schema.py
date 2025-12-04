"""Tests for get_archetype_schema tool."""

from typing import Any

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from test_helpers import call_tool, get_structured_error, run_async

from src.tools.errors import ErrorCode
from src.tools.trading_tools import GetArchetypeSchemaResponse


def test_get_archetype_schema_returns_schema(trading_tools_mcp):
    """Test that get_archetype_schema returns the full schema for an archetype."""
    # Setup: use existing schema data from data/archetype_schema.json

    # Run: call the tool
    result = run_async(
        call_tool(
            trading_tools_mcp,
            "get_archetype_schema",
            {"type": "entry.trend_pullback"},
        )
    )

    # Assert: verify response structure and content
    response = GetArchetypeSchemaResponse(**result)
    assert response.type_id == "entry.trend_pullback"
    assert response.schema_version == 1
    assert response.etag is not None
    assert response.json_schema is not None
    assert isinstance(response.json_schema, dict)
    assert "required" in response.json_schema
    assert "properties" in response.json_schema
    assert "constraints" in response.model_dump()
    assert "examples" in response.model_dump()
    assert len(response.examples) > 0

    # Check that required slots are in the schema (new structure: context, event, action, risk)
    required = response.json_schema.get("required", [])
    assert "context" in required
    assert "event" in required
    assert "action" in required
    assert "risk" in required


def test_get_archetype_schema_with_etag(trading_tools_mcp):
    """Test that get_archetype_schema handles if_none_match parameter."""
    # Setup: get initial schema to obtain etag
    result1 = run_async(
        call_tool(
            trading_tools_mcp,
            "get_archetype_schema",
            {"type": "entry.trend_pullback"},
        )
    )
    response1 = GetArchetypeSchemaResponse(**result1)
    etag = response1.etag

    # Run: request with if_none_match
    result2 = run_async(
        call_tool(
            trading_tools_mcp,
            "get_archetype_schema",
            {"type": "entry.trend_pullback", "if_none_match": etag},
        )
    )

    # Assert: should still return the schema (MCP doesn't support 304)
    response2 = GetArchetypeSchemaResponse(**result2)
    assert response2.etag == etag
    assert response2.type_id == "entry.trend_pullback"


def test_get_archetype_schema_not_found(trading_tools_mcp):
    """Test that get_archetype_schema raises error for unknown archetype."""
    # Setup: use a non-existent archetype type

    # Run & Assert: should raise ToolError (FastMCP wraps StructuredToolError)
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                trading_tools_mcp,
                "get_archetype_schema",
                {"type": "entry.nonexistent"},
            )
        )
    # Verify structured error
    structured_error = get_structured_error(exc_info.value)
    assert structured_error is not None
    assert structured_error.error_code == ErrorCode.SCHEMA_NOT_FOUND
    assert structured_error.retryable is False


def test_get_archetype_schema_response_structure(trading_tools_mcp):
    """Test that get_archetype_schema returns properly structured response."""
    # Setup: use existing schema data

    # Run: call the tool
    result = run_async(
        call_tool(
            trading_tools_mcp,
            "get_archetype_schema",
            {"type": "entry.trend_pullback"},
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
            {"type": "entry.trend_pullback"},
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
            {"type": "entry.trend_pullback"},
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


def test_get_archetype_schema_resolves_refs(trading_tools_mcp):
    """Test that get_archetype_schema resolves all $ref references to common_defs.

    This ensures the schema is self-contained and agents don't see confusing $ref strings.
    """
    # Run: call the tool
    result = run_async(
        call_tool(
            trading_tools_mcp,
            "get_archetype_schema",
            {"type": "entry.trend_pullback"},
        )
    )

    # Assert: verify that $ref references to common_defs are resolved
    response = GetArchetypeSchemaResponse(**result)
    json_schema = response.json_schema

    # Helper function to recursively check for unresolved external $ref
    def has_unresolved_external_ref(obj: Any) -> bool:
        """Check if there are any unresolved external $ref references."""
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_value = obj["$ref"]
                # Check if it's an external reference to common_defs
                if isinstance(ref_value, str) and "common_defs.schema.json" in ref_value:
                    return True
            # Recurse into all values
            return any(has_unresolved_external_ref(v) for v in obj.values())
        elif isinstance(obj, list):
            return any(has_unresolved_external_ref(item) for item in obj)
        return False

    # Verify no unresolved external references exist
    assert not has_unresolved_external_ref(json_schema), (
        "Schema should not contain unresolved $ref references to common_defs.schema.json. "
        "All references should be resolved to their actual definitions."
    )

    # Verify that context property is resolved (should have type/properties, not $ref)
    context_prop = json_schema["properties"]["context"]
    assert "$ref" not in context_prop or "common_defs.schema.json" not in str(context_prop.get("$ref", "")), (
        "Context property should be resolved (no external $ref)"
    )


def test_get_archetype_schema_gate_regime_structure(trading_tools_mcp):
    """Gate schemas should omit risk slot and use new specs.

    Note: $ref references are now resolved to their full definitions,
    so we check for the resolved schema structure instead of $ref strings.
    """
    result = run_async(
        call_tool(
            trading_tools_mcp,
            "get_archetype_schema",
            {"type": "gate.regime"},
        )
    )

    response = GetArchetypeSchemaResponse(**result)
    assert response.type_id == "gate.regime"

    json_schema = response.json_schema
    required_slots = set(json_schema.get("required", []))
    assert required_slots == {"context", "event", "action"}

    # After resolution, $ref should be replaced with actual schema definitions
    # Check that action property exists and has been resolved (no $ref)
    action_prop = json_schema["properties"]["action"]
    assert "$ref" not in action_prop, "Action $ref should be resolved"
    assert "type" in action_prop or "properties" in action_prop, "Action should have resolved schema"

    # Check that regime property exists and has been resolved
    regime_prop = json_schema["properties"]["event"]["properties"]["regime"]
    assert "$ref" not in regime_prop, "Regime $ref should be resolved"
    assert "type" in regime_prop or "properties" in regime_prop, "Regime should have resolved schema"
