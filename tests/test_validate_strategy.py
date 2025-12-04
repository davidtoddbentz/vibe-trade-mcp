"""Tests for validate_strategy tool."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from test_helpers import (
    call_tool,
    get_structured_error,
    get_valid_slots_for_archetype,
    run_async,
)

from src.tools.errors import ErrorCode
from src.tools.strategy_tools import CompileStrategyResponse


def test_validate_strategy_ready(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test validating a strategy with valid cards returns ready."""
    # Setup: create strategy with entry and exit cards
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
    strategy_id = strategy_result["strategy_id"]

    # Create entry card
    entry_schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert entry_schema is not None
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
    entry_card_id = entry_card_result["card_id"]

    # Create exit card
    exit_schema = schema_repository.get_by_type_id("exit.take_profit_stop")
    assert exit_schema is not None
    exit_slots = get_valid_slots_for_archetype(schema_repository, "exit.take_profit_stop")
    exit_card_result = run_async(
        call_tool(
            card_tools_mcp,
            "create_card",
            {
                "type": "exit.take_profit_stop",
                "slots": exit_slots,
            },
        )
    )
    exit_card_id = exit_card_result["card_id"]

    # Attach cards
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
    run_async(
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

    # Run: validate strategy
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "validate_strategy",
            {"strategy_id": strategy_id},
        )
    )

    # Assert: verify response
    response = CompileStrategyResponse(**result)
    assert response.status_hint == "ready"
    assert response.compiled is None  # Validation-only, no compiled plan
    assert response.validation_summary["errors"] == 0
    assert response.validation_summary["cards_validated"] == 2
    assert len(response.issues) == 0 or all(i.severity == "warning" for i in response.issues)


def test_validate_strategy_fix_required(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test validating a strategy with invalid overrides returns fix_required."""
    # Setup: create strategy with card
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy Invalid",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = strategy_result["strategy_id"]

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
    entry_card_id = entry_card_result["card_id"]

    # Attach with invalid override
    run_async(
        call_tool(
            strategy_tools_mcp,
            "attach_card",
            {
                "strategy_id": strategy_id,
                "card_id": entry_card_id,
                "role": "entry",
                "overrides": {
                    "event": {"dip_band": {"mult": 10.0}},  # Max is 5.0
                },
            },
        )
    )

    # Run: validate strategy
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "validate_strategy",
            {"strategy_id": strategy_id},
        )
    )

    # Assert: verify response indicates fix required
    response = CompileStrategyResponse(**result)
    assert response.status_hint == "fix_required"
    assert response.compiled is None
    assert response.validation_summary["errors"] > 0
    assert any(i.code == "SLOT_VALIDATION_ERROR" for i in response.issues)


def test_validate_strategy_not_found(strategy_tools_mcp):
    """Test validating a non-existent strategy returns error."""
    # Run: try to validate non-existent strategy
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                strategy_tools_mcp,
                "validate_strategy",
                {"strategy_id": "non_existent_id"},
            )
        )

    # Assert: verify error
    error = get_structured_error(exc_info.value)
    assert error is not None
    assert error.error_code == ErrorCode.STRATEGY_NOT_FOUND
    assert error.retryable is False
    assert "Use list_strategies" in error.recovery_hint


def test_validate_strategy_no_signals(strategy_tools_mcp):
    """Test validating a strategy with no signals returns fix_required."""
    # Setup: create empty strategy
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Empty Strategy",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = strategy_result["strategy_id"]

    # Run: validate strategy
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "validate_strategy",
            {"strategy_id": strategy_id},
        )
    )

    # Assert: verify response indicates fix required
    response = CompileStrategyResponse(**result)
    assert response.status_hint == "fix_required"
    assert response.compiled is None
    assert response.validation_summary["errors"] > 0
    assert any(i.code == "NO_SIGNALS" for i in response.issues)
