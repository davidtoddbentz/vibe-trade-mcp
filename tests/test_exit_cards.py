"""Tests for exit card functionality."""

from test_helpers import (
    call_tool,
    get_valid_slots_for_archetype,
    run_async,
)

from src.tools.card_tools import CreateCardResponse
from src.tools.strategy_tools import AttachCardResponse, CreateStrategyResponse


def test_create_exit_card_take_profit_stop(card_tools_mcp, schema_repository):
    """Test creating an exit card with rule_trigger for take profit/stop loss."""
    # Setup: get exit schema
    schema = schema_repository.get_by_type_id("exit.rule_trigger")
    assert schema is not None

    # Use example slots from schema
    example_slots = get_valid_slots_for_archetype(schema_repository, "exit.rule_trigger")

    # Run: create exit card
    result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "exit.rule_trigger",
                "slots": example_slots,
            },
        )
    )

    # Assert: verify response
    response = CreateCardResponse(**result)
    assert response.card_id is not None
    assert response.type == "exit.rule_trigger"
    assert response.slots == example_slots
    # Verify exit-specific structure
    assert "event" in response.slots
    assert "condition" in response.slots["event"]
    assert "action" in response.slots
    assert response.slots["action"]["mode"] in ["close", "reduce", "reverse"]


def test_create_exit_card_trailing_stop(card_tools_mcp, schema_repository):
    """Test creating an exit card with trailing_stop archetype."""
    # Setup: get exit schema
    schema = schema_repository.get_by_type_id("exit.trailing_stop")
    assert schema is not None

    example_slots = get_valid_slots_for_archetype(schema_repository, "exit.trailing_stop")

    # Run: create exit card
    result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "exit.trailing_stop",
                "slots": example_slots,
            },
        )
    )

    # Assert: verify response
    response = CreateCardResponse(**result)
    assert response.type == "exit.trailing_stop"
    assert "event" in response.slots
    assert "trail_band" in response.slots["event"]
    assert "trail_trigger" in response.slots["event"]


def test_create_exit_card_time_stop(card_tools_mcp, schema_repository):
    """Test creating an exit card with rule_trigger for time-based exit."""
    # Setup: get exit schema
    schema = schema_repository.get_by_type_id("exit.rule_trigger")
    assert schema is not None

    # Create slots for time-based exit using rule_trigger
    example_slots = {
        "context": {"tf": "1h", "symbol": "BTC-USD"},
        "event": {
            "condition": {
                "type": "regime",
                "regime": {
                    "metric": "ret_pct",
                    "tf": "1h",
                    "op": ">",
                    "value": 0,
                    "lookback_bars": 24,
                },
            }
        },
        "action": {"mode": "close"},
    }

    # Run: create exit card
    result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "exit.rule_trigger",
                "slots": example_slots,
            },
        )
    )

    # Assert: verify response
    response = CreateCardResponse(**result)
    assert response.type == "exit.rule_trigger"
    assert "event" in response.slots
    assert "condition" in response.slots["event"]


def test_attach_exit_card_to_strategy(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test attaching an exit card to a strategy."""
    # Setup: create strategy
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy with Exit",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = CreateStrategyResponse(**strategy_result).strategy_id

    # Setup: create exit card
    schema_repository.get_by_type_id("exit.rule_trigger")
    exit_slots = get_valid_slots_for_archetype(schema_repository, "exit.rule_trigger")

    exit_card_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "exit.rule_trigger",
                "slots": exit_slots,
            },
        )
    )
    exit_card_id = CreateCardResponse(**exit_card_result).card_id

    # Run: attach exit card with "exit" role
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "attach_card",
            {
                "strategy_id": strategy_id,
                "card_id": exit_card_id,
                "role": "exit",
            },
        )
    )

    # Assert: verify attachment
    response = AttachCardResponse(**result)
    assert len(response.attachments) == 1
    attachment = response.attachments[0]
    assert attachment["card_id"] == exit_card_id
    assert attachment["role"] == "exit"
    assert attachment["enabled"] is True


def test_strategy_with_entry_and_exit_cards(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test that a strategy can have both entry (signal) and exit cards."""
    # Setup: create strategy
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Complete Strategy",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = CreateStrategyResponse(**strategy_result).strategy_id

    # Setup: create entry card (signal)
    schema_repository.get_by_type_id("entry.trend_pullback")
    entry_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    entry_card_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "entry.trend_pullback",
                "slots": entry_slots,
            },
        )
    )
    entry_card_id = CreateCardResponse(**entry_card_result).card_id

    # Setup: create exit card
    schema_repository.get_by_type_id("exit.rule_trigger")
    exit_slots = get_valid_slots_for_archetype(schema_repository, "exit.rule_trigger")

    exit_card_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "exit.rule_trigger",
                "slots": exit_slots,
            },
        )
    )
    exit_card_id = CreateCardResponse(**exit_card_result).card_id

    # Run: attach entry card as "entry"
    run_async(
        call_tool(
            strategy_tools_mcp,
            "attach_card",
            {
                "strategy_id": strategy_id,
                "card_id": entry_card_id,
                "role": "entry",
            },
        )
    )

    # Run: attach exit card as "exit"
    result2 = run_async(
        call_tool(
            strategy_tools_mcp,
            "attach_card",
            {
                "strategy_id": strategy_id,
                "card_id": exit_card_id,
                "role": "exit",
            },
        )
    )

    # Assert: verify both attachments
    response2 = AttachCardResponse(**result2)

    assert len(response2.attachments) == 2

    # Find entry and exit attachments
    entry_att = next(att for att in response2.attachments if att["role"] == "entry")
    exit_att = next(att for att in response2.attachments if att["role"] == "exit")

    assert entry_att["card_id"] == entry_card_id
    assert exit_att["card_id"] == exit_card_id


def test_exit_card_uses_exit_action_spec(card_tools_mcp, schema_repository):
    """Test that exit cards use ExitActionSpec (mode: close/reduce/reverse)."""
    # Setup: create exit card
    schema_repository.get_by_type_id("exit.rule_trigger")
    example_slots = get_valid_slots_for_archetype(schema_repository, "exit.rule_trigger")

    result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "exit.rule_trigger",
                "slots": example_slots,
            },
        )
    )

    # Assert: verify action structure
    response = CreateCardResponse(**result)
    action = response.slots["action"]
    assert "mode" in action
    assert action["mode"] in ["close", "reduce", "reverse"]
    # size_frac is optional but should be present if provided
    if "size_frac" in action:
        assert 0.0 <= action["size_frac"] <= 1.0


def test_exit_card_tp_sl_event_structure(card_tools_mcp, schema_repository):
    """Test that exit.rule_trigger can express TP/SL conditions."""
    # Setup: create exit card with TP/SL condition
    example_slots = {
        "context": {"tf": "1h", "symbol": "BTC-USD"},
        "event": {
            "condition": {
                "type": "anyOf",
                "anyOf": [
                    {
                        "type": "regime",
                        "regime": {
                            "metric": "ret_pct",
                            "tf": "1h",
                            "op": ">=",
                            "value": 3.0,
                            "lookback_bars": 1,
                        },
                    },
                    {
                        "type": "regime",
                        "regime": {
                            "metric": "ret_pct",
                            "tf": "1h",
                            "op": "<=",
                            "value": -2.0,
                            "lookback_bars": 1,
                        },
                    },
                ],
            }
        },
        "action": {"mode": "close"},
        "risk": {"tp_pct": 3.0, "sl_pct": 2.0},
    }

    result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "exit.rule_trigger",
                "slots": example_slots,
            },
        )
    )

    # Assert: verify condition structure
    response = CreateCardResponse(**result)
    event = response.slots["event"]
    assert "condition" in event
    condition = event["condition"]
    assert condition["type"] == "anyOf"
    assert len(condition["anyOf"]) == 2

    # Verify risk block has TP/SL thresholds
    risk = response.slots.get("risk", {})
    assert "tp_pct" in risk or "sl_pct" in risk
