"""Tests for validate_strategy tool."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from test_helpers import (
    call_tool,
    get_structured_error,
    get_valid_slots_for_archetype,
    run_async,
)

from vibe_trade_mcp.tools.errors import ErrorCode
from vibe_trade_mcp.tools.strategy_tools import CompileStrategyResponse


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

    # Add entry card (automatically attached)
    entry_schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert entry_schema is not None
    entry_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")
    run_async(
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

    # Add exit card (automatically attached)
    exit_schema = schema_repository.get_by_type_id("exit.rule_trigger")
    assert exit_schema is not None
    exit_slots = get_valid_slots_for_archetype(schema_repository, "exit.rule_trigger")
    run_async(
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

    # Add card with invalid override
    run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": entry_slots,
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
    assert "Use list_strategies" in error.recovery_hint


def test_validate_strategy_no_entries(strategy_tools_mcp):
    """Test validating a strategy with no entry cards returns fix_required."""
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
    assert any(i.code == "NO_ENTRIES" for i in response.issues)
