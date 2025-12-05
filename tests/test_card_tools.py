"""Tests for card management tools."""

import copy

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from test_helpers import (
    call_tool,
    get_structured_error,
    get_valid_slots_for_archetype,
    run_async,
)

from src.tools.card_tools import (
    CreateCardResponse,
    DeleteCardResponse,
    GetCardResponse,
    ListCardsResponse,
    UpdateCardResponse,
)
from src.tools.errors import ErrorCode


def test_create_card_valid(card_tools_mcp, schema_repository):
    """Test creating a card with valid slots."""
    # Setup: get a valid schema and its etag
    schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert schema is not None

    # Use example slots from schema (now includes context, event, action, risk)
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    # Run: create card
    result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "entry.trend_pullback",
                "slots": example_slots,
            },
        )
    )

    # Assert: verify response
    response = CreateCardResponse(**result)
    assert response.card_id is not None
    assert response.type == "entry.trend_pullback"
    assert response.slots == example_slots
    assert response.schema_etag == schema.etag
    assert response.created_at is not None


def test_create_card_invalid_slots(card_tools_mcp, schema_repository):
    """Test creating a card with invalid slots fails validation."""
    # Setup: get a valid schema
    schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert schema is not None

    # Run: try to create card with invalid slots (missing required fields)
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "entry.trend_pullback",
                    "slots": {
                        "context": {"tf": "1h"}
                    },  # Missing required fields (event, action, risk)
                },
            )
        )

    # Assert: should get validation error with structured information
    assert "validation" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()
    # Verify structured error properties
    structured_error = get_structured_error(exc_info.value)
    assert structured_error is not None
    assert structured_error.error_code == ErrorCode.SCHEMA_VALIDATION_ERROR
    assert structured_error.retryable is False
    assert structured_error.recovery_hint is not None


def test_create_card_invalid_range_values(card_tools_mcp, schema_repository):
    """Test creating a card with values outside allowed ranges fails validation."""
    # Setup: get a valid schema and valid slots
    schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert schema is not None

    # Get valid slots and modify to test range validation
    # Test: event.dip_band.mult above maximum (5.0) - this was the old dip_threshold field
    valid_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")
    invalid_slots = copy.deepcopy(valid_slots)
    invalid_slots["event"]["dip_band"]["mult"] = 6.0  # Above maximum 5.0

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "entry.trend_pullback",
                    "slots": invalid_slots,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()
    assert "5.0" in str(exc_info.value) or "maximum" in str(exc_info.value).lower()

    # Test: risk.sl_atr above maximum (20.0)
    invalid_slots2 = copy.deepcopy(valid_slots)
    invalid_slots2["risk"]["sl_atr"] = 21.0  # Above maximum 20.0

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "entry.trend_pullback",
                    "slots": invalid_slots2,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()
    assert "20.0" in str(exc_info.value) or "maximum" in str(exc_info.value).lower()


def test_create_card_invalid_enum_values(card_tools_mcp, schema_repository):
    """Test creating a card with invalid enum values fails validation."""
    # Setup: get a valid schema and valid slots
    schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert schema is not None

    valid_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    # Test: invalid context.tf enum value
    invalid_slots = copy.deepcopy(valid_slots)
    invalid_slots["context"]["tf"] = "5m"  # Invalid: must be one of ["15m", "1h", "4h", "1d"]

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "entry.trend_pullback",
                    "slots": invalid_slots,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()
    assert "tf" in str(exc_info.value).lower() or "enum" in str(exc_info.value).lower()

    # Test: invalid action.direction enum value
    invalid_slots2 = copy.deepcopy(valid_slots)
    invalid_slots2["action"]["direction"] = "invalid"  # Invalid: must be "long", "short", or "auto"

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "entry.trend_pullback",
                    "slots": invalid_slots2,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()
    assert "direction" in str(exc_info.value).lower() or "enum" in str(exc_info.value).lower()


def test_create_card_invalid_nested_structure(card_tools_mcp, schema_repository):
    """Test creating a card with invalid nested object structures fails validation."""
    # Setup: get a valid schema and valid slots
    schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert schema is not None

    valid_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    # Test: invalid event.trend_gate structure (missing required op field)
    invalid_slots = copy.deepcopy(valid_slots)
    invalid_slots["event"]["trend_gate"] = {
        "fast": 20,
        "slow": 50,
        # Missing required: op
    }

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "entry.trend_pullback",
                    "slots": invalid_slots,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()

    # Test: invalid event.trend_gate.op enum value
    invalid_slots2 = copy.deepcopy(valid_slots)
    invalid_slots2["event"]["trend_gate"]["op"] = "invalid"  # Invalid: must be ">" or "<"

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "entry.trend_pullback",
                    "slots": invalid_slots2,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()


def test_create_card_additional_properties(card_tools_mcp, schema_repository):
    """Test creating a card with additional properties fails validation."""
    # Setup: get a valid schema and valid slots
    schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert schema is not None

    # Test: additional property at root level
    valid_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")
    invalid_slots = copy.deepcopy(valid_slots)
    invalid_slots["extra_field"] = "not allowed"

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "entry.trend_pullback",
                    "slots": invalid_slots,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()
    assert (
        "additional" in str(exc_info.value).lower() or "extra_field" in str(exc_info.value).lower()
    )


def test_update_card_invalid_range_values(card_tools_mcp, schema_repository):
    """Test updating a card with values outside allowed ranges fails validation."""
    # Setup: create a valid card first
    schema_repository.get_by_type_id("entry.trend_pullback")
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    create_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "entry.trend_pullback",
                "slots": example_slots,
            },
        )
    )
    card_id = CreateCardResponse(**create_result).card_id

    # Test: update with event.dip_band.mult above maximum (5.0)
    # This corresponds to the old dip_threshold field that had max 5.0
    updated_slots = copy.deepcopy(example_slots)
    updated_slots["event"]["dip_band"]["mult"] = 6.0  # Above maximum 5.0

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "update_card",
                {
                    "card_id": card_id,
                    "slots": updated_slots,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()
    assert "5.0" in str(exc_info.value) or "maximum" in str(exc_info.value).lower()


def test_get_card(card_tools_mcp, schema_repository):
    """Test getting a card by ID."""
    # Setup: create a card first
    schema_repository.get_by_type_id("entry.trend_pullback")
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    create_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "entry.trend_pullback",
                "slots": example_slots,
            },
        )
    )
    card_id = CreateCardResponse(**create_result).card_id

    # Run: get card
    result = run_async(call_tool(card_tools_mcp, "get_card", {"card_id": card_id}))

    # Assert: verify response
    response = GetCardResponse(**result)
    assert response.card_id == card_id
    assert response.type == "entry.trend_pullback"
    assert response.slots == example_slots


def test_get_card_not_found(card_tools_mcp):
    """Test getting a non-existent card returns error."""
    # Run: try to get non-existent card
    with pytest.raises(ToolError):
        run_async(call_tool(card_tools_mcp, "get_card", {"card_id": "non-existent-id"}))


def test_list_cards(card_tools_mcp, schema_repository):
    """Test listing all cards."""
    # Setup: create a couple of cards
    schema_repository.get_by_type_id("entry.trend_pullback")
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "entry.trend_pullback",
                "slots": example_slots,
            },
        )
    )

    # Run: list cards
    result = run_async(call_tool(card_tools_mcp, "list_cards", {}))

    # Assert: verify response
    response = ListCardsResponse(**result)
    assert response.count >= 1
    assert len(response.cards) == response.count


def test_update_card(card_tools_mcp, schema_repository):
    """Test updating a card."""
    # Setup: create a card first
    schema_repository.get_by_type_id("entry.trend_pullback")
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    create_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "entry.trend_pullback",
                "slots": example_slots,
            },
        )
    )
    card_id = CreateCardResponse(**create_result).card_id

    # Run: update card with new slots
    updated_slots = copy.deepcopy(example_slots)
    updated_slots["event"]["dip_band"]["mult"] = 2.5  # Update dip_band multiplier

    result = run_async(
        call_tool(
            card_tools_mcp,
            "update_card",
            {
                "card_id": card_id,
                "slots": updated_slots,
            },
        )
    )

    # Assert: verify response
    response = UpdateCardResponse(**result)
    assert response.card_id == card_id
    assert response.slots["event"]["dip_band"]["mult"] == 2.5
    assert response.updated_at is not None


def test_create_card_error_messages_include_guidance(card_tools_mcp, schema_repository):
    """Test that error messages include helpful guidance for agents."""
    schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert schema is not None

    # Test: schema not found error includes guidance
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "entry.nonexistent",
                    "slots": {"context": {"tf": "1h"}},
                },
            )
        )
    error_msg = str(exc_info.value)
    assert (
        "browse" in error_msg.lower()
        or "archetypes://" in error_msg.lower()
        or "valid values" in error_msg.lower()
    )
    # Verify structured error
    structured_error = get_structured_error(exc_info.value)
    assert structured_error is not None
    assert structured_error.error_code == ErrorCode.ARCHETYPE_NOT_FOUND
    assert structured_error.retryable is False
    assert structured_error.recovery_hint is not None

    # Test: validation error includes guidance to fetch schema
    valid_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")
    invalid_slots = copy.deepcopy(valid_slots)
    invalid_slots["event"]["dip_band"]["mult"] = 6.0  # Invalid: above max 5.0

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "entry.trend_pullback",
                    "slots": invalid_slots,
                },
            )
        )
    error_msg = str(exc_info.value)
    assert "browse" in error_msg.lower() or "archetype-schemas://" in error_msg.lower()
    assert "entry.trend_pullback" in error_msg
    # Verify structured error
    structured_error = get_structured_error(exc_info.value)
    assert structured_error is not None
    assert structured_error.error_code == ErrorCode.SCHEMA_VALIDATION_ERROR
    assert structured_error.retryable is False
    assert structured_error.recovery_hint is not None
    assert "type_id" in structured_error.details


def test_update_card_invalid_etag(card_tools_mcp, schema_repository):
    """Test updating a card with invalid schema_etag fails."""
    # Note: schema_etag is now internal to MCP, so we can't test invalid etag scenarios
    # The etag is automatically set to the current schema version
    pass


def test_update_card_error_messages_include_guidance(card_tools_mcp, schema_repository):
    """Test that update_card error messages include helpful guidance."""
    schema_repository.get_by_type_id("entry.trend_pullback")
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    # Create a card first
    create_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "entry.trend_pullback",
                "slots": example_slots,
            },
        )
    )
    card_id = CreateCardResponse(**create_result).card_id

    # Test: validation error includes guidance
    updated_slots = copy.deepcopy(example_slots)
    updated_slots["event"]["dip_band"]["mult"] = 6.0  # Invalid: above max 5.0

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "update_card",
                {
                    "card_id": card_id,
                    "slots": updated_slots,
                },
            )
        )
    error_msg = str(exc_info.value)
    assert "get_archetype_schema" in error_msg.lower()
    assert "entry.trend_pullback" in error_msg

    # Test: card not found error includes guidance
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "update_card",
                {
                    "card_id": "nonexistent-id",
                    "slots": example_slots,
                },
            )
        )
    error_msg = str(exc_info.value)
    assert "list_cards" in error_msg.lower()


def test_get_card_error_includes_guidance(card_tools_mcp):
    """Test that get_card error includes helpful guidance."""
    with pytest.raises(ToolError) as exc_info:
        run_async(call_tool(card_tools_mcp, "get_card", {"card_id": "nonexistent-id"}))
    error_msg = str(exc_info.value)
    assert "list_cards" in error_msg.lower()
    # Verify structured error
    structured_error = get_structured_error(exc_info.value)
    assert structured_error is not None
    assert structured_error.error_code == ErrorCode.CARD_NOT_FOUND
    assert structured_error.retryable is False
    assert structured_error.recovery_hint is not None


def test_delete_card(card_tools_mcp, schema_repository):
    """Test deleting a card."""
    # Setup: create a card first
    schema_repository.get_by_type_id("entry.trend_pullback")
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    create_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "entry.trend_pullback",
                "slots": example_slots,
            },
        )
    )
    card_id = CreateCardResponse(**create_result).card_id

    # Run: delete card
    result = run_async(call_tool(card_tools_mcp, "delete_card", {"card_id": card_id}))

    # Assert: verify response
    response = DeleteCardResponse(**result)
    assert response.card_id == card_id
    assert response.success is True

    # Assert: card should no longer exist
    with pytest.raises(ToolError):
        run_async(call_tool(card_tools_mcp, "get_card", {"card_id": card_id}))
