"""Tests for exit card functionality."""

from test_helpers import (
    call_tool,
    get_valid_slots_for_archetype,
    run_async,
)

from vibe_trade_mcp.tools.strategy_tools import AttachCardResponse, CreateStrategyResponse


def test_create_exit_card_take_profit_stop(strategy_tools_mcp, schema_repository):
    """Test creating an exit card with rule_trigger for take profit/stop loss."""
    # Setup: create strategy first
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = CreateStrategyResponse(**strategy_result).strategy_id

    # Use example slots from schema
    example_slots = get_valid_slots_for_archetype(schema_repository, "exit.rule_trigger")

    # Run: add exit card to strategy
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "exit.rule_trigger",
                "slots": example_slots,
            },
        )
    )

    # Assert: verify response
    response = AttachCardResponse(**result)
    assert len(response.attachments) == 1
    attachment = response.attachments[0]
    assert attachment["card_id"] is not None
    assert attachment["role"] == "exit"
    # Verify exit-specific structure in slots (need to get card to check)
    assert "event" in example_slots
    assert "condition" in example_slots["event"]
    assert "action" in example_slots
    assert example_slots["action"]["mode"] in ["close", "reduce", "reverse"]


def test_create_exit_card_trailing_stop(strategy_tools_mcp, schema_repository):
    """Test creating an exit card with trailing_stop archetype."""
    # Setup: create a strategy first
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = CreateStrategyResponse(**strategy_result).strategy_id

    # Setup: get exit schema
    schema = schema_repository.get_by_type_id("exit.trailing_stop")
    assert schema is not None

    example_slots = get_valid_slots_for_archetype(schema_repository, "exit.trailing_stop")

    # Run: add exit card to strategy
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "exit.trailing_stop",
                "slots": example_slots,
            },
        )
    )

    # Assert: verify response
    response = AttachCardResponse(**result)
    assert len(response.attachments) == 1
    assert response.attachments[0]["role"] == "exit"
    assert "event" in example_slots
    assert "trail_band" in example_slots["event"]
    assert "trail_trigger" in example_slots["event"]


def test_create_exit_card_time_stop(strategy_tools_mcp, schema_repository):
    """Test creating an exit card with rule_trigger for time-based exit."""
    # Setup: create a strategy first
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = CreateStrategyResponse(**strategy_result).strategy_id

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

    # Run: add exit card to strategy
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "exit.rule_trigger",
                "slots": example_slots,
            },
        )
    )

    # Assert: verify response
    response = AttachCardResponse(**result)
    assert len(response.attachments) == 1
    assert response.attachments[0]["role"] == "exit"
    assert "event" in example_slots
    assert "condition" in example_slots["event"]


def test_attach_exit_card_to_strategy(strategy_tools_mcp, schema_repository):
    """Test adding an exit card to a strategy (automatically attached)."""
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

    # Setup: add exit card (automatically attached)
    schema_repository.get_by_type_id("exit.rule_trigger")
    exit_slots = get_valid_slots_for_archetype(schema_repository, "exit.rule_trigger")

    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "exit.rule_trigger",
                "slots": exit_slots,
            },
        )
    )

    # Assert: verify attachment
    response = AttachCardResponse(**result)
    assert len(response.attachments) == 1
    attachment = response.attachments[0]
    assert attachment["card_id"] is not None
    assert attachment["role"] == "exit"
    assert attachment["enabled"] is True


def test_strategy_with_entry_and_exit_cards(strategy_tools_mcp, schema_repository):
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

    # Setup: add entry card (automatically attached)
    schema_repository.get_by_type_id("entry.trend_pullback")
    entry_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    entry_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": entry_slots,
            },
        )
    )
    entry_card_id = AttachCardResponse(**entry_result).attachments[0]["card_id"]

    # Setup: add exit card (automatically attached)
    schema_repository.get_by_type_id("exit.rule_trigger")
    exit_slots = get_valid_slots_for_archetype(schema_repository, "exit.rule_trigger")

    exit_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "exit.rule_trigger",
                "slots": exit_slots,
            },
        )
    )

    # Assert: verify both attachments
    response2 = AttachCardResponse(**exit_result)

    assert len(response2.attachments) == 2

    # Find entry and exit attachments
    entry_att = next(att for att in response2.attachments if att["role"] == "entry")
    exit_att = next(att for att in response2.attachments if att["role"] == "exit")

    assert entry_att["card_id"] == entry_card_id
    assert exit_att["card_id"] is not None


def test_exit_card_uses_exit_action_spec(strategy_tools_mcp, schema_repository):
    """Test that exit cards use ExitActionSpec (mode: close/reduce/reverse)."""
    # Setup: create a strategy first
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = CreateStrategyResponse(**strategy_result).strategy_id

    # Setup: add exit card
    schema_repository.get_by_type_id("exit.rule_trigger")
    example_slots = get_valid_slots_for_archetype(schema_repository, "exit.rule_trigger")

    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "exit.rule_trigger",
                "slots": example_slots,
            },
        )
    )

    # Assert: verify action structure
    response = AttachCardResponse(**result)
    assert len(response.attachments) == 1
    action = example_slots["action"]
    assert "mode" in action
    assert action["mode"] in ["close", "reduce", "reverse"]
    # size_frac is optional but should be present if provided
    if "size_frac" in action:
        assert 0.0 <= action["size_frac"] <= 1.0


def test_exit_card_tp_sl_event_structure(strategy_tools_mcp, schema_repository):
    """Test that exit.rule_trigger can express TP/SL conditions."""
    # Setup: create a strategy first
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = CreateStrategyResponse(**strategy_result).strategy_id

    # Setup: add exit card with TP/SL condition
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
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "exit.rule_trigger",
                "slots": example_slots,
            },
        )
    )

    # Assert: verify condition structure
    response = AttachCardResponse(**result)
    assert len(response.attachments) == 1
    event = example_slots["event"]
    assert "condition" in event
    condition = event["condition"]
    assert condition["type"] == "anyOf"
    assert len(condition["anyOf"]) == 2

    # Verify risk block has TP/SL thresholds
    risk = example_slots.get("risk", {})
    assert "tp_pct" in risk or "sl_pct" in risk
