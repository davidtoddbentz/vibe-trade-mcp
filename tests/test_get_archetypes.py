"""Tests for get_archetypes tool."""

from test_helpers import call_tool, run_async

from src.tools.trading_tools import GetArchetypesResponse


def test_get_archetypes_returns_catalog(trading_tools_mcp):
    """Test that get_archetypes returns a catalog of available archetypes."""
    # Setup: data is read from JSON file

    # Force fresh load by clearing repository cache
    import json

    from src.db.archetype_repository import ArchetypeRepository

    # Debug: Check what file the repository is using
    test_repo = ArchetypeRepository()
    print(f"DEBUG: Repository file path: {test_repo.archetypes_file}")
    print(f"DEBUG: File exists: {test_repo.archetypes_file.exists()}")
    print(f"DEBUG: Absolute path: {test_repo.archetypes_file.resolve()}")

    # Read file directly
    with open(test_repo.archetypes_file) as f:
        file_data = json.load(f)
    if file_data.get("archetypes"):
        print(f"DEBUG: File content first ID: {file_data['archetypes'][0]['id']}")

    test_repo._archetypes = None
    test_archs = test_repo.get_non_deprecated()
    if test_archs:
        print(f"DEBUG: Repository load first ID: {test_archs[0].id}")

    # Run: call the tool
    result = run_async(call_tool(trading_tools_mcp, "get_archetypes", {}))

    # Assert: verify response structure and content
    response = GetArchetypesResponse(**result)
    assert len(response.types) >= 1, f"Expected at least 1 archetype, got {len(response.types)}"
    assert response.as_of is not None

    # Verify we have real archetypes from the JSON file
    entry_ids = [arch.id for arch in response.types if arch.id.startswith("entry.")]
    assert len(entry_ids) > 0, (
        f"No entry.* archetypes found. Got archetype IDs: {[arch.id for arch in response.types[:10]]}"
    )
    assert any(arch.id.startswith("entry.") for arch in response.types)


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


def test_get_archetypes_filters_by_kind_entry(trading_tools_mcp):
    """Test that get_archetypes can filter by kind='entry'."""
    result = run_async(call_tool(trading_tools_mcp, "get_archetypes", {"kind": "entry"}))
    response = GetArchetypesResponse(**result)

    # All returned archetypes should be entries
    assert len(response.types) > 0
    assert all(arch.kind == "entry" for arch in response.types)
    assert all(arch.id.startswith("entry.") for arch in response.types)


def test_get_archetypes_filters_by_kind_exit(trading_tools_mcp):
    """Test that get_archetypes can filter by kind='exit'."""
    result = run_async(call_tool(trading_tools_mcp, "get_archetypes", {"kind": "exit"}))
    response = GetArchetypesResponse(**result)

    # All returned archetypes should be exits
    assert len(response.types) > 0
    assert all(arch.kind == "exit" for arch in response.types)
    assert all(arch.id.startswith("exit.") for arch in response.types)


def test_get_archetypes_filters_by_kind_gate(trading_tools_mcp):
    """Test that get_archetypes can filter by kind='gate'."""
    result = run_async(call_tool(trading_tools_mcp, "get_archetypes", {"kind": "gate"}))
    response = GetArchetypesResponse(**result)

    # All returned archetypes should be gates
    assert len(response.types) > 0
    assert all(arch.kind == "gate" for arch in response.types)
    assert all(arch.id.startswith("gate.") for arch in response.types)


def test_get_archetypes_filters_by_kind_overlay(trading_tools_mcp):
    """Test that get_archetypes can filter by kind='overlay'."""
    result = run_async(call_tool(trading_tools_mcp, "get_archetypes", {"kind": "overlay"}))
    response = GetArchetypesResponse(**result)

    # All returned archetypes should be overlays
    assert len(response.types) > 0
    assert all(arch.kind == "overlay" for arch in response.types)
    assert all(arch.id.startswith("overlay.") for arch in response.types)


def test_get_archetypes_invalid_kind_raises_error(trading_tools_mcp):
    """Test that get_archetypes raises validation error for invalid kind."""
    import pytest
    from mcp.server.fastmcp.exceptions import ToolError

    with pytest.raises(ToolError) as exc_info:
        run_async(call_tool(trading_tools_mcp, "get_archetypes", {"kind": "invalid"}))

    # Verify the error message contains expected content
    error_msg = str(exc_info.value).lower()
    assert "invalid" in error_msg or "valid values" in error_msg
    assert (
        "entry" in error_msg or "exit" in error_msg or "gate" in error_msg or "overlay" in error_msg
    )
