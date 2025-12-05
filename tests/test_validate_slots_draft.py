"""Tests for validate_slots_draft tool."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from test_helpers import call_tool, get_structured_error, get_valid_slots_for_archetype, run_async

from src.tools.card_tools import ValidateSlotsDraftResponse
from src.tools.errors import ErrorCode


def test_validate_slots_draft_valid(card_tools_mcp, schema_repository):
    """Test validating valid slots returns success."""
    # Setup: get valid slots
    valid_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    # Run: validate slots
    result = run_async(
        call_tool(
            card_tools_mcp,
            "validate_slots_draft",
            {
                "type": "entry.trend_pullback",
                "slots": valid_slots,
            },
        )
    )

    # Assert: verify response
    response = ValidateSlotsDraftResponse(**result)
    assert response.type_id == "entry.trend_pullback"
    assert response.valid is True
    assert len(response.errors) == 0
    assert response.schema_etag is not None


def test_validate_slots_draft_invalid_range(card_tools_mcp, schema_repository):
    """Test validating slots with invalid range values returns errors."""
    # Setup: get valid slots and modify to invalid value
    valid_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")
    valid_slots["event"]["dip_band"]["mult"] = 10.0  # Max is 5.0

    # Run: validate slots
    result = run_async(
        call_tool(
            card_tools_mcp,
            "validate_slots_draft",
            {
                "type": "entry.trend_pullback",
                "slots": valid_slots,
            },
        )
    )

    # Assert: verify response indicates invalid
    response = ValidateSlotsDraftResponse(**result)
    assert response.type_id == "entry.trend_pullback"
    assert response.valid is False
    assert len(response.errors) > 0
    assert any("mult" in error.lower() or "10" in error for error in response.errors)
    assert response.schema_etag is not None


def test_validate_slots_draft_missing_required(card_tools_mcp, schema_repository):
    """Test validating slots with missing required fields returns errors."""
    # Setup: get valid slots and remove required field
    valid_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")
    del valid_slots["context"]["tf"]

    # Run: validate slots
    result = run_async(
        call_tool(
            card_tools_mcp,
            "validate_slots_draft",
            {
                "type": "entry.trend_pullback",
                "slots": valid_slots,
            },
        )
    )

    # Assert: verify response indicates invalid
    response = ValidateSlotsDraftResponse(**result)
    assert response.valid is False
    assert len(response.errors) > 0
    assert any("tf" in error.lower() or "required" in error.lower() for error in response.errors)


def test_validate_slots_draft_not_found(card_tools_mcp):
    """Test validating slots for non-existent archetype returns error."""
    # Run: try to validate for non-existent archetype
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "validate_slots_draft",
                {
                    "type": "nonexistent.archetype",
                    "slots": {},
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
