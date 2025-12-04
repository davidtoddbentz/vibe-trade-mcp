"""Tests for get_archetypes tool."""

from test_helpers import call_tool, run_async

from src.tools.trading_tools import GetArchetypesResponse


def test_get_archetypes_returns_catalog(trading_tools_mcp):
    """Test that get_archetypes returns a catalog of available archetypes."""
    # Setup: data is read from JSON file

    # Run: call the tool
    result = run_async(call_tool(trading_tools_mcp, "get_archetypes", {}))

    # Assert: verify response structure and content
    response = GetArchetypesResponse(**result)
    assert len(response.types) >= 1
    assert response.as_of is not None

    # Verify we have real archetypes from the JSON file
    assert any(arch.id.startswith("signal.") for arch in response.types)


def test_get_archetypes_filters_deprecated(trading_tools_mcp):
    """Test that get_archetypes filters out deprecated archetypes."""
    # Setup: data is read from JSON file (should not have deprecated archetypes)

    # Run: call the tool
    result = run_async(call_tool(trading_tools_mcp, "get_archetypes", {}))

    # Assert: no deprecated archetypes should be in results
    response = GetArchetypesResponse(**result)
    deprecated = [arch for arch in response.types if arch.deprecated]
    assert len(deprecated) == 0, "No deprecated archetypes should be returned"


def test_get_archetypes_response_structure(trading_tools_mcp):
    """Test that get_archetypes returns properly structured response."""
    # Setup: data is read from JSON file

    # Run: call the tool
    result = run_async(call_tool(trading_tools_mcp, "get_archetypes", {}))

    # Assert: verify response structure
    response = GetArchetypesResponse(**result)
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


def test_get_archetypes_timestamp_format(trading_tools_mcp):
    """Test that get_archetypes returns a valid ISO8601 timestamp."""
    # Setup: data is read from JSON file

    # Run: call the tool
    result = run_async(call_tool(trading_tools_mcp, "get_archetypes", {}))

    # Assert: verify timestamp format
    response = GetArchetypesResponse(**result)
    assert response.as_of is not None
    # Should end with Z or have timezone
    assert response.as_of.endswith("Z") or "+" in response.as_of or "-" in response.as_of[-6:]


def test_get_archetypes_includes_gate_and_overlay(trading_tools_mcp):
    """Ensure catalog exposes new gate/overlay archetypes."""
    result = run_async(call_tool(trading_tools_mcp, "get_archetypes", {}))
    response = GetArchetypesResponse(**result)

    kinds = {arch.kind for arch in response.types}
    assert "gate" in kinds, "catalog should include at least one gate archetype"
    assert "overlay" in kinds, "catalog should include at least one overlay archetype"
