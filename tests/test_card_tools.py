"""Tests for card management tools."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from test_helpers import call_tool, run_async

from src.tools.card_tools import (
    CreateCardResponse,
    DeleteCardResponse,
    GetCardResponse,
    ListCardsResponse,
    UpdateCardResponse,
)


def test_create_card_valid(card_tools_mcp, schema_repository):
    """Test creating a card with valid slots."""
    # Setup: get a valid schema and its etag
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    assert schema is not None

    # Use example slots from schema
    example_slots = (
        schema.examples[0].slots
        if schema.examples
        else {
            "tf": "1h",
            "symbol": "BTC-USD",
            "direction": "long",
            "dip_trigger": "keltner",
            "dip_threshold": 1.5,
            "trend_gate": {"mode": "hard", "gate": {"kind": "preset", "name": "uptrend_basic"}},
        }
    )

    # Run: create card
    result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "signal.trend_pullback",
                "slots": example_slots,
                "schema_etag": schema.etag,
            },
        )
    )

    # Assert: verify response
    response = CreateCardResponse(**result)
    assert response.card_id is not None
    assert response.type == "signal.trend_pullback"
    assert response.slots == example_slots
    assert response.schema_etag == schema.etag
    assert response.created_at is not None


def test_create_card_invalid_slots(card_tools_mcp, schema_repository):
    """Test creating a card with invalid slots fails validation."""
    # Setup: get a valid schema
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    assert schema is not None

    # Run: try to create card with invalid slots (missing required field)
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "signal.trend_pullback",
                    "slots": {"tf": "1h"},  # Missing required fields
                    "schema_etag": schema.etag,
                },
            )
        )

    # Assert: should get validation error
    assert "validation" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()


def test_create_card_invalid_range_values(card_tools_mcp, schema_repository):
    """Test creating a card with values outside allowed ranges fails validation."""
    # Setup: get a valid schema
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    assert schema is not None

    # Test: dip_threshold below minimum (0.2)
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "signal.trend_pullback",
                    "slots": {
                        "tf": "1h",
                        "symbol": "BTC-USD",
                        "direction": "long",
                        "dip_trigger": "keltner",
                        "dip_threshold": 0.1,  # Below minimum 0.2
                    },
                    "schema_etag": schema.etag,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()
    assert "0.2" in str(exc_info.value) or "minimum" in str(exc_info.value).lower()

    # Test: dip_threshold above maximum (5.0)
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "signal.trend_pullback",
                    "slots": {
                        "tf": "1h",
                        "symbol": "BTC-USD",
                        "direction": "long",
                        "dip_trigger": "keltner",
                        "dip_threshold": 6.0,  # Above maximum 5.0
                    },
                    "schema_etag": schema.etag,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()
    assert "5.0" in str(exc_info.value) or "maximum" in str(exc_info.value).lower()


def test_create_card_invalid_enum_values(card_tools_mcp, schema_repository):
    """Test creating a card with invalid enum values fails validation."""
    # Setup: get a valid schema
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    assert schema is not None

    # Test: invalid tf enum value
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "signal.trend_pullback",
                    "slots": {
                        "tf": "5m",  # Invalid: must be one of ["15m", "1h", "4h", "1d"]
                        "symbol": "BTC-USD",
                        "direction": "long",
                        "dip_trigger": "keltner",
                        "dip_threshold": 1.5,
                    },
                    "schema_etag": schema.etag,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()
    assert "tf" in str(exc_info.value).lower() or "enum" in str(exc_info.value).lower()

    # Test: invalid direction enum value
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "signal.trend_pullback",
                    "slots": {
                        "tf": "1h",
                        "symbol": "BTC-USD",
                        "direction": "invalid",  # Invalid: must be "long" or "short"
                        "dip_trigger": "keltner",
                        "dip_threshold": 1.5,
                    },
                    "schema_etag": schema.etag,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()
    assert "direction" in str(exc_info.value).lower() or "enum" in str(exc_info.value).lower()

    # Test: invalid dip_trigger enum value
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "signal.trend_pullback",
                    "slots": {
                        "tf": "1h",
                        "symbol": "BTC-USD",
                        "direction": "long",
                        "dip_trigger": "invalid",  # Invalid: must be one of ["keltner", "bollinger", "ema_z"]
                        "dip_threshold": 1.5,
                    },
                    "schema_etag": schema.etag,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()
    assert "dip_trigger" in str(exc_info.value).lower() or "enum" in str(exc_info.value).lower()


def test_create_card_invalid_nested_structure(card_tools_mcp, schema_repository):
    """Test creating a card with invalid nested object structures fails validation."""
    # Setup: get a valid schema
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    assert schema is not None

    # Test: invalid trend_gate structure (wrong mode)
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "signal.trend_pullback",
                    "slots": {
                        "tf": "1h",
                        "symbol": "BTC-USD",
                        "direction": "long",
                        "dip_trigger": "keltner",
                        "dip_threshold": 1.5,
                        "trend_gate": {
                            "mode": "invalid",  # Invalid: must be "hard" or "ma_rel"
                            "gate": {"kind": "preset", "name": "uptrend_basic"},
                        },
                    },
                    "schema_etag": schema.etag,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()

    # Test: invalid trend_gate structure (missing required fields for ma_rel mode)
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "signal.trend_pullback",
                    "slots": {
                        "tf": "1h",
                        "symbol": "BTC-USD",
                        "direction": "long",
                        "dip_trigger": "keltner",
                        "dip_threshold": 1.5,
                        "trend_gate": {
                            "mode": "ma_rel",
                            # Missing required: fast, slow, op
                        },
                    },
                    "schema_etag": schema.etag,
                },
            )
        )
    # Note: oneOf validation may report error from first option, but validation should still fail
    assert "validation" in str(exc_info.value).lower()


def test_create_card_additional_properties(card_tools_mcp, schema_repository):
    """Test creating a card with additional properties fails validation."""
    # Setup: get a valid schema
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    assert schema is not None

    # Test: additional property at root level
    valid_slots = {
        "tf": "1h",
        "symbol": "BTC-USD",
        "direction": "long",
        "dip_trigger": "keltner",
        "dip_threshold": 1.5,
    }
    invalid_slots = {**valid_slots, "extra_field": "not allowed"}

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "signal.trend_pullback",
                    "slots": invalid_slots,
                    "schema_etag": schema.etag,
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
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    example_slots = (
        schema.examples[0].slots
        if schema.examples
        else {
            "tf": "1h",
            "symbol": "BTC-USD",
            "direction": "long",
            "dip_trigger": "keltner",
            "dip_threshold": 1.5,
            "trend_gate": {"mode": "hard", "gate": {"kind": "preset", "name": "uptrend_basic"}},
        }
    )

    create_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "signal.trend_pullback",
                "slots": example_slots,
                "schema_etag": schema.etag,
            },
        )
    )
    card_id = CreateCardResponse(**create_result).card_id

    # Test: update with dip_threshold above maximum
    updated_slots = example_slots.copy()
    updated_slots["dip_threshold"] = 10.0  # Above maximum 5.0

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "update_card",
                {
                    "card_id": card_id,
                    "slots": updated_slots,
                    "schema_etag": schema.etag,
                },
            )
        )
    assert "validation" in str(exc_info.value).lower()
    assert "5.0" in str(exc_info.value) or "maximum" in str(exc_info.value).lower()


def test_create_card_invalid_etag(card_tools_mcp):
    """Test creating a card with invalid schema_etag fails."""
    # Run: try to create card with wrong etag
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "signal.trend_pullback",
                    "slots": {"tf": "1h", "symbol": "BTC-USD"},
                    "schema_etag": "invalid-etag",
                },
            )
        )

    # Assert: should get etag mismatch error
    assert "etag" in str(exc_info.value).lower() or "mismatch" in str(exc_info.value).lower()


def test_get_card(card_tools_mcp, schema_repository):
    """Test getting a card by ID."""
    # Setup: create a card first
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    example_slots = (
        schema.examples[0].slots
        if schema.examples
        else {
            "tf": "1h",
            "symbol": "BTC-USD",
            "direction": "long",
            "dip_trigger": "keltner",
            "dip_threshold": 1.5,
            "trend_gate": {"mode": "hard", "gate": {"kind": "preset", "name": "uptrend_basic"}},
        }
    )

    create_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "signal.trend_pullback",
                "slots": example_slots,
                "schema_etag": schema.etag,
            },
        )
    )
    card_id = CreateCardResponse(**create_result).card_id

    # Run: get card
    result = run_async(call_tool(card_tools_mcp, "get_card", {"card_id": card_id}))

    # Assert: verify response
    response = GetCardResponse(**result)
    assert response.card_id == card_id
    assert response.type == "signal.trend_pullback"
    assert response.slots == example_slots


def test_get_card_not_found(card_tools_mcp):
    """Test getting a non-existent card returns error."""
    # Run: try to get non-existent card
    with pytest.raises(ToolError):
        run_async(call_tool(card_tools_mcp, "get_card", {"card_id": "non-existent-id"}))


def test_list_cards(card_tools_mcp, schema_repository):
    """Test listing all cards."""
    # Setup: create a couple of cards
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    example_slots = (
        schema.examples[0].slots
        if schema.examples
        else {
            "tf": "1h",
            "symbol": "BTC-USD",
            "direction": "long",
            "dip_trigger": "keltner",
            "dip_threshold": 1.5,
            "trend_gate": {"mode": "hard", "gate": {"kind": "preset", "name": "uptrend_basic"}},
        }
    )

    run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "signal.trend_pullback",
                "slots": example_slots,
                "schema_etag": schema.etag,
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
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    example_slots = (
        schema.examples[0].slots
        if schema.examples
        else {
            "tf": "1h",
            "symbol": "BTC-USD",
            "direction": "long",
            "dip_trigger": "keltner",
            "dip_threshold": 1.5,
            "trend_gate": {"mode": "hard", "gate": {"kind": "preset", "name": "uptrend_basic"}},
        }
    )

    create_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "signal.trend_pullback",
                "slots": example_slots,
                "schema_etag": schema.etag,
            },
        )
    )
    card_id = CreateCardResponse(**create_result).card_id

    # Run: update card with new slots
    updated_slots = example_slots.copy()
    updated_slots["dip_threshold"] = 2.0

    result = run_async(
        call_tool(
            card_tools_mcp,
            "update_card",
            {
                "card_id": card_id,
                "slots": updated_slots,
                "schema_etag": schema.etag,
            },
        )
    )

    # Assert: verify response
    response = UpdateCardResponse(**result)
    assert response.card_id == card_id
    assert response.slots["dip_threshold"] == 2.0
    assert response.updated_at is not None


def test_create_card_error_messages_include_guidance(card_tools_mcp, schema_repository):
    """Test that error messages include helpful guidance for agents."""
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    assert schema is not None

    # Test: schema not found error includes guidance
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "signal.nonexistent",
                    "slots": {"tf": "1h"},
                    "schema_etag": "invalid",
                },
            )
        )
    error_msg = str(exc_info.value)
    assert "get_archetypes" in error_msg.lower()

    # Test: validation error includes guidance to fetch schema
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "create_card",
                {
                    "type": "signal.trend_pullback",
                    "slots": {
                        "tf": "1h",
                        "symbol": "BTC-USD",
                        "direction": "long",
                        "dip_trigger": "keltner",
                        "dip_threshold": 6.0,  # Invalid: above max
                    },
                    "schema_etag": schema.etag,
                },
            )
        )
    error_msg = str(exc_info.value)
    assert "get_archetype_schema" in error_msg.lower()
    assert "signal.trend_pullback" in error_msg


def test_update_card_error_messages_include_guidance(card_tools_mcp, schema_repository):
    """Test that update_card error messages include helpful guidance."""
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    example_slots = (
        schema.examples[0].slots
        if schema.examples
        else {
            "tf": "1h",
            "symbol": "BTC-USD",
            "direction": "long",
            "dip_trigger": "keltner",
            "dip_threshold": 1.5,
            "trend_gate": {"mode": "hard", "gate": {"kind": "preset", "name": "uptrend_basic"}},
        }
    )

    # Create a card first
    create_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "signal.trend_pullback",
                "slots": example_slots,
                "schema_etag": schema.etag,
            },
        )
    )
    card_id = CreateCardResponse(**create_result).card_id

    # Test: validation error includes guidance
    updated_slots = example_slots.copy()
    updated_slots["dip_threshold"] = 10.0  # Invalid

    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "update_card",
                {
                    "card_id": card_id,
                    "slots": updated_slots,
                    "schema_etag": schema.etag,
                },
            )
        )
    error_msg = str(exc_info.value)
    assert "get_archetype_schema" in error_msg.lower()
    assert "signal.trend_pullback" in error_msg

    # Test: card not found error includes guidance
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                card_tools_mcp,
                "update_card",
                {
                    "card_id": "nonexistent-id",
                    "slots": example_slots,
                    "schema_etag": schema.etag,
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


def test_delete_card(card_tools_mcp, schema_repository):
    """Test deleting a card."""
    # Setup: create a card first
    schema = schema_repository.get_by_type_id("signal.trend_pullback")
    example_slots = (
        schema.examples[0].slots
        if schema.examples
        else {
            "tf": "1h",
            "symbol": "BTC-USD",
            "direction": "long",
            "dip_trigger": "keltner",
            "dip_threshold": 1.5,
            "trend_gate": {"mode": "hard", "gate": {"kind": "preset", "name": "uptrend_basic"}},
        }
    )

    create_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "signal.trend_pullback",
                "slots": example_slots,
                "schema_etag": schema.etag,
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
