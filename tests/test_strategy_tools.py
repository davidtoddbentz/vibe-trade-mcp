"""Tests for strategy management tools."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from test_helpers import call_tool, get_structured_error, run_async

from src.tools.errors import ErrorCode
from src.tools.strategy_tools import (
    AttachCardResponse,
    CreateStrategyResponse,
    DetachCardResponse,
    GetStrategyResponse,
    ListStrategiesResponse,
    UpdateStrategyMetaResponse,
)


def test_create_strategy_valid(strategy_tools_mcp):
    """Test creating a strategy with valid parameters."""
    # Run: create strategy
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "BTC Dip Buyer",
                "universe": ["BTC-USD"],
            },
        )
    )

    # Assert: verify response
    response = CreateStrategyResponse(**result)
    assert response.strategy_id is not None
    assert response.name == "BTC Dip Buyer"
    assert response.status == "draft"
    assert response.universe == ["BTC-USD"]
    assert response.attachments == []
    assert response.version == 1
    assert response.created_at is not None


def test_get_strategy(strategy_tools_mcp):
    """Test getting a strategy by ID."""
    # Setup: create a strategy first
    create_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
            },
        )
    )
    strategy_id = CreateStrategyResponse(**create_result).strategy_id

    # Run: get strategy
    result = run_async(call_tool(strategy_tools_mcp, "get_strategy", {"strategy_id": strategy_id}))

    # Assert: verify response
    response = GetStrategyResponse(**result)
    assert response.strategy_id == strategy_id
    assert response.name == "Test Strategy"
    assert response.status == "draft"


def test_get_strategy_not_found(strategy_tools_mcp):
    """Test getting a non-existent strategy returns error."""
    # Run: try to get non-existent strategy
    with pytest.raises(ToolError) as exc_info:
        run_async(call_tool(strategy_tools_mcp, "get_strategy", {"strategy_id": "nonexistent-id"}))

    # Assert: should get error with helpful guidance
    assert "not found" in str(exc_info.value).lower()
    assert "list_strategies" in str(exc_info.value).lower()
    # Verify structured error
    structured_error = get_structured_error(exc_info.value)
    assert structured_error is not None
    assert structured_error.error_code == ErrorCode.STRATEGY_NOT_FOUND
    assert structured_error.retryable is False


def test_update_strategy_meta(strategy_tools_mcp):
    """Test updating strategy metadata."""
    # Setup: create a strategy first
    create_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Original Name",
            },
        )
    )
    strategy_id = CreateStrategyResponse(**create_result).strategy_id

    # Run: update strategy metadata
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "update_strategy_meta",
            {
                "strategy_id": strategy_id,
                "name": "Updated Name",
                "status": "ready",
                "universe": ["BTC-USD", "ETH-USD"],
            },
        )
    )

    # Assert: verify response
    response = UpdateStrategyMetaResponse(**result)
    assert response.strategy_id == strategy_id
    assert response.name == "Updated Name"
    assert response.status == "ready"
    assert response.universe == ["BTC-USD", "ETH-USD"]
    assert response.version == 2  # Version should increment
    assert response.updated_at is not None


def test_update_strategy_meta_invalid_status(strategy_tools_mcp):
    """Test updating strategy with invalid status fails."""
    # Setup: create a strategy first
    create_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
            },
        )
    )
    strategy_id = CreateStrategyResponse(**create_result).strategy_id

    # Run: try to update with invalid status
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                strategy_tools_mcp,
                "update_strategy_meta",
                {
                    "strategy_id": strategy_id,
                    "status": "invalid_status",
                },
            )
        )

    # Assert: should get validation error
    assert "status" in str(exc_info.value).lower()


def test_attach_card(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test attaching a card to a strategy."""
    # Setup: create a card and strategy
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

    create_card_result = run_async(
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
    card_id = create_card_result["card_id"]

    create_strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
            },
        )
    )
    strategy_id = CreateStrategyResponse(**create_strategy_result).strategy_id

    # Run: attach card to strategy
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "attach_card",
            {
                "strategy_id": strategy_id,
                "card_id": card_id,
                "role": "signal",
                "overrides": {"symbol": "ETH-USD"},
            },
        )
    )

    # Assert: verify response
    response = AttachCardResponse(**result)
    assert response.strategy_id == strategy_id
    assert len(response.attachments) == 1
    assert response.attachments[0]["card_id"] == card_id
    assert response.attachments[0]["role"] == "signal"
    assert response.attachments[0]["overrides"] == {"symbol": "ETH-USD"}
    assert response.attachments[0]["order"] == 1
    assert response.version == 2  # Version should increment


def test_attach_card_invalid_role(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test attaching a card with invalid role fails."""
    # Setup: create a card and strategy
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

    create_card_result = run_async(
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
    card_id = create_card_result["card_id"]

    create_strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
            },
        )
    )
    strategy_id = CreateStrategyResponse(**create_strategy_result).strategy_id

    # Run: try to attach with invalid role
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                strategy_tools_mcp,
                "attach_card",
                {
                    "strategy_id": strategy_id,
                    "card_id": card_id,
                    "role": "invalid_role",
                },
            )
        )

    # Assert: should get validation error with structured information
    assert "role" in str(exc_info.value).lower()
    structured_error = get_structured_error(exc_info.value)
    assert structured_error is not None
    assert structured_error.error_code == ErrorCode.INVALID_ROLE
    assert structured_error.retryable is False


def test_attach_card_card_not_found(strategy_tools_mcp):
    """Test attaching a non-existent card fails."""
    # Setup: create a strategy
    create_strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
            },
        )
    )
    strategy_id = CreateStrategyResponse(**create_strategy_result).strategy_id

    # Run: try to attach non-existent card
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                strategy_tools_mcp,
                "attach_card",
                {
                    "strategy_id": strategy_id,
                    "card_id": "nonexistent-card-id",
                    "role": "signal",
                },
            )
        )

    # Assert: should get error with helpful guidance
    assert "card" in str(exc_info.value).lower()
    assert "not found" in str(exc_info.value).lower()
    assert "list_cards" in str(exc_info.value).lower()


def test_attach_card_duplicate(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test attaching the same card twice fails."""
    # Setup: create a card and strategy
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

    create_card_result = run_async(
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
    card_id = create_card_result["card_id"]

    create_strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
            },
        )
    )
    strategy_id = CreateStrategyResponse(**create_strategy_result).strategy_id

    # Attach card first time
    run_async(
        call_tool(
            strategy_tools_mcp,
            "attach_card",
            {
                "strategy_id": strategy_id,
                "card_id": card_id,
                "role": "signal",
            },
        )
    )

    # Run: try to attach same card again
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                strategy_tools_mcp,
                "attach_card",
                {
                    "strategy_id": strategy_id,
                    "card_id": card_id,
                    "role": "signal",
                },
            )
        )

    # Assert: should get error
    assert "already attached" in str(exc_info.value).lower()


def test_detach_card(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test detaching a card from a strategy."""
    # Setup: create a card and strategy, then attach
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

    create_card_result = run_async(
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
    card_id = create_card_result["card_id"]

    create_strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
            },
        )
    )
    strategy_id = CreateStrategyResponse(**create_strategy_result).strategy_id

    # Attach card
    run_async(
        call_tool(
            strategy_tools_mcp,
            "attach_card",
            {
                "strategy_id": strategy_id,
                "card_id": card_id,
                "role": "signal",
            },
        )
    )

    # Run: detach card
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "detach_card",
            {
                "strategy_id": strategy_id,
                "card_id": card_id,
            },
        )
    )

    # Assert: verify response
    response = DetachCardResponse(**result)
    assert response.strategy_id == strategy_id
    assert len(response.attachments) == 0
    assert response.version == 3  # Version should increment (create=1, attach=2, detach=3)


def test_detach_card_not_attached(strategy_tools_mcp):
    """Test detaching a card that's not attached fails."""
    # Setup: create a strategy
    create_strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
            },
        )
    )
    strategy_id = CreateStrategyResponse(**create_strategy_result).strategy_id

    # Run: try to detach non-attached card
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                strategy_tools_mcp,
                "detach_card",
                {
                    "strategy_id": strategy_id,
                    "card_id": "some-card-id",
                },
            )
        )

    # Assert: should get error with helpful guidance
    assert "not attached" in str(exc_info.value).lower()
    assert "get_strategy" in str(exc_info.value).lower()


def test_list_strategies(strategy_tools_mcp):
    """Test listing all strategies."""
    # Setup: create a couple of strategies
    run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Strategy 1",
            },
        )
    )

    run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Strategy 2",
            },
        )
    )

    # Run: list strategies
    result = run_async(call_tool(strategy_tools_mcp, "list_strategies", {}))

    # Assert: verify response
    response = ListStrategiesResponse(**result)
    assert response.count >= 2
    assert len(response.strategies) == response.count
    assert all("strategy_id" in s for s in response.strategies)
    assert all("name" in s for s in response.strategies)
    # Verify all strategies have required fields
    assert all("status" in s for s in response.strategies)


def test_attach_card_auto_order(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test that attach_card auto-assigns order when not provided."""
    # Setup: create multiple cards and a strategy
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

    card1_result = run_async(
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
    card1_id = card1_result["card_id"]

    card2_result = run_async(
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
    card2_id = card2_result["card_id"]

    create_strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
            },
        )
    )
    strategy_id = CreateStrategyResponse(**create_strategy_result).strategy_id

    # Attach first card (should get order=1)
    result1 = run_async(
        call_tool(
            strategy_tools_mcp,
            "attach_card",
            {
                "strategy_id": strategy_id,
                "card_id": card1_id,
                "role": "signal",
            },
        )
    )
    assert AttachCardResponse(**result1).attachments[0]["order"] == 1

    # Attach second card without specifying order (should auto-assign order=2)
    result2 = run_async(
        call_tool(
            strategy_tools_mcp,
            "attach_card",
            {
                "strategy_id": strategy_id,
                "card_id": card2_id,
                "role": "gate",
            },
        )
    )
    attachments = AttachCardResponse(**result2).attachments
    assert len(attachments) == 2
    orders = [att["order"] for att in attachments]
    assert 1 in orders
    assert 2 in orders


def test_attach_card_follow_latest(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test attach_card with follow_latest flag."""
    # Setup: create a card and strategy
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

    create_card_result = run_async(
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
    card_id = create_card_result["card_id"]

    create_strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Test Strategy",
            },
        )
    )
    strategy_id = CreateStrategyResponse(**create_strategy_result).strategy_id

    # Run: attach with follow_latest=true
    result1 = run_async(
        call_tool(
            strategy_tools_mcp,
            "attach_card",
            {
                "strategy_id": strategy_id,
                "card_id": card_id,
                "role": "signal",
                "follow_latest": True,
            },
        )
    )
    att1 = AttachCardResponse(**result1).attachments[0]
    assert att1["follow_latest"] is True
    assert att1["card_revision_id"] is None

    # Run: attach another card with follow_latest=false
    card2_result = run_async(
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
    card2_id = card2_result["card_id"]

    result2 = run_async(
        call_tool(
            strategy_tools_mcp,
            "attach_card",
            {
                "strategy_id": strategy_id,
                "card_id": card2_id,
                "role": "gate",
                "follow_latest": False,
            },
        )
    )
    att2 = AttachCardResponse(**result2).attachments[1]
    assert att2["follow_latest"] is False
    assert att2["card_revision_id"] is not None  # Should be pinned to card's updated_at
