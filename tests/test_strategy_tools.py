"""Tests for strategy management tools."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from test_helpers import (
    call_tool,
    get_structured_error,
    get_valid_slots_for_archetype,
    run_async,
)

from src.tools.errors import ErrorCode
from src.tools.strategy_tools import (
    AttachCardResponse,
    CompileStrategyResponse,
    CreateStrategyResponse,
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


def test_add_card_with_overrides(strategy_tools_mcp, schema_repository):
    """Test adding a card to a strategy with overrides (cards are automatically attached)."""
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

    # Setup: get example slots
    schema_repository.get_by_type_id("entry.trend_pullback")
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    # Run: add card to strategy with overrides
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": example_slots,
                "overrides": {"symbol": "ETH-USD"},
            },
        )
    )

    # Assert: verify response
    response = AttachCardResponse(**result)
    assert response.strategy_id == strategy_id
    assert len(response.attachments) == 1
    assert response.attachments[0]["card_id"] is not None
    assert response.attachments[0]["role"] == "entry"
    assert response.attachments[0]["overrides"] == {"symbol": "ETH-USD"}
    assert response.version == 2  # Version should increment


def test_add_card_invalid_role(strategy_tools_mcp, schema_repository):
    """Test adding a card with invalid role fails (role is inferred from type, but can be overridden)."""
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

    # Setup: get example slots
    schema_repository.get_by_type_id("entry.trend_pullback")
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    # Run: try to add card with invalid role (should fail if type doesn't match role)
    # Since role is inferred from type, this test may not be applicable anymore
    # But we can test with an invalid type that doesn't start with a valid role
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                strategy_tools_mcp,
                "add_card",
                {
                    "strategy_id": strategy_id,
                    "type": "invalid.type",
                    "slots": example_slots,
                    "role": "invalid_role",
                },
            )
        )

    # Assert: should get validation error
    assert "role" in str(exc_info.value).lower() or "archetype" in str(exc_info.value).lower()


# test_attach_card_card_not_found removed - no longer applicable since cards are created as part of add_card


# test_attach_card_duplicate removed - no longer applicable since each add_card creates a new card


def test_add_card(strategy_tools_mcp, schema_repository):
    """Test adding a card to a strategy (creates card and attaches it)."""
    # Setup: create a strategy
    schema_repository.get_by_type_id("entry.trend_pullback")
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

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

    # Run: add card to strategy (creates card and attaches)
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": example_slots,
                "overrides": {"symbol": "ETH-USD"},
            },
        )
    )

    # Assert: verify response
    response = AttachCardResponse(**result)
    assert response.strategy_id == strategy_id
    assert len(response.attachments) == 1
    assert response.attachments[0]["role"] == "entry"  # Role should be inferred from type
    assert response.attachments[0]["overrides"] == {"symbol": "ETH-USD"}
    assert response.version == 2  # Version should increment (create=1, add_card=2)

    # Verify card_id is in attachments
    card_id = response.attachments[0]["card_id"]
    assert card_id is not None
    assert len(card_id) > 0


def test_add_card_with_explicit_role(strategy_tools_mcp, schema_repository):
    """Test adding a card with explicit role."""
    # Setup: create a strategy
    schema_repository.get_by_type_id("exit.rule_trigger")
    example_slots = get_valid_slots_for_archetype(schema_repository, "exit.rule_trigger")

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

    # Run: add card with explicit role
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "exit.rule_trigger",
                "slots": example_slots,
                "role": "exit",
            },
        )
    )

    # Assert: verify response
    response = AttachCardResponse(**result)
    assert response.strategy_id == strategy_id
    assert len(response.attachments) == 1
    assert response.attachments[0]["role"] == "exit"


# test_delete_card removed - delete_card no longer takes strategy_id, it automatically removes from all strategies


# test_delete_card_not_attached removed - delete_card no longer takes strategy_id
# It now automatically removes cards from all strategies when deleted


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


def test_add_card_multiple_attachments(strategy_tools_mcp, schema_repository):
    """Test that add_card can add multiple cards with different roles."""
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

    # Setup: get example slots
    schema_repository.get_by_type_id("entry.trend_pullback")
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    # Add first card (entry role)
    result1 = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": example_slots,
            },
        )
    )
    assert len(AttachCardResponse(**result1).attachments) == 1

    # Add second card with different role (gate)
    # Note: gate.regime would be better, but using entry with explicit role override
    result2 = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": example_slots,
                "role": "gate",  # Override role
            },
        )
    )
    attachments = AttachCardResponse(**result2).attachments
    assert len(attachments) == 2
    roles = [att["role"] for att in attachments]
    assert "entry" in roles
    assert "gate" in roles


def test_add_card_follow_latest(strategy_tools_mcp, schema_repository):
    """Test add_card with follow_latest flag."""
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

    # Setup: get example slots
    schema_repository.get_by_type_id("entry.trend_pullback")
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    # Run: add card with follow_latest=true
    result1 = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": example_slots,
                "follow_latest": True,
            },
        )
    )
    att1 = AttachCardResponse(**result1).attachments[0]
    assert att1["follow_latest"] is True
    assert att1["card_revision_id"] is None

    # Run: add another card with follow_latest=false
    result2 = run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": example_slots,
                "follow_latest": False,
            },
        )
    )
    att2 = AttachCardResponse(**result2).attachments[-1]  # Get the last attachment
    assert att2["follow_latest"] is False
    assert att2["card_revision_id"] is not None  # Should be pinned to card's updated_at


def test_compile_strategy_ready(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test compiling a strategy with valid cards."""
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
    schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert schema is not None
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": example_slots,
            },
        )
    )

    # Add exit card (automatically attached)
    exit_schema = schema_repository.get_by_type_id("exit.rule_trigger")
    assert exit_schema is not None
    exit_example_slots = get_valid_slots_for_archetype(schema_repository, "exit.rule_trigger")

    run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "exit.rule_trigger",
                "slots": exit_example_slots,
            },
        )
    )

    # Run: compile strategy
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "compile_strategy",
            {
                "strategy_id": strategy_id,
            },
        )
    )

    # Assert: verify compilation
    response = CompileStrategyResponse(**result)
    assert response.status_hint == "ready"
    assert response.compiled is not None
    assert response.compiled.strategy_id == strategy_id
    assert len(response.compiled.cards) == 2
    assert len(response.compiled.data_requirements) > 0
    assert len(response.issues) == 0
    # Verify validation summary
    assert response.validation_summary["errors"] == 0
    assert response.validation_summary["cards_validated"] == 2

    # Verify compiled cards
    entry_card = next(c for c in response.compiled.cards if c.role == "entry")
    assert entry_card.card_id is not None
    assert entry_card.type == "entry.trend_pullback"
    assert "context" in entry_card.effective_slots

    exit_card = next(c for c in response.compiled.cards if c.role == "exit")
    assert exit_card.card_id is not None
    assert exit_card.type == "exit.rule_trigger"

    # Verify data requirements
    data_req = response.compiled.data_requirements[0]
    assert data_req.symbol == "BTC-USD"
    assert data_req.tf == "1h"
    assert data_req.min_bars > 0
    assert data_req.lookback_hours > 0


def test_compile_strategy_no_entries(strategy_tools_mcp):
    """Test compiling a strategy with no entry cards."""
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

    # Run: compile strategy
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "compile_strategy",
            {
                "strategy_id": strategy_id,
            },
        )
    )

    # Assert: should have error
    response = CompileStrategyResponse(**result)
    assert response.status_hint == "fix_required"
    assert response.compiled is None
    assert len(response.issues) > 0
    assert any(issue.code == "NO_ENTRIES" for issue in response.issues)


def test_compile_strategy_no_exits(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test compiling a strategy with no exit cards (should warn)."""
    # Setup: create strategy with only entry card
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "No Exit Strategy",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = strategy_result["strategy_id"]

    schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert schema is not None
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    # Add entry card (automatically attached)
    run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": example_slots,
            },
        )
    )

    # Run: compile strategy
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "compile_strategy",
            {
                "strategy_id": strategy_id,
            },
        )
    )

    # Assert: should have warning but still be ready
    response = CompileStrategyResponse(**result)
    assert response.status_hint == "ready"  # Warnings don't block
    assert response.compiled is not None
    assert any(
        issue.code == "NO_EXITS" and issue.severity == "warning" for issue in response.issues
    )


def test_compile_strategy_not_found(strategy_tools_mcp):
    """Test compiling a non-existent strategy."""
    # Run: compile non-existent strategy
    with pytest.raises(ToolError) as exc_info:
        run_async(
            call_tool(
                strategy_tools_mcp,
                "compile_strategy",
                {
                    "strategy_id": "nonexistent",
                },
            )
        )

    # Assert: verify error
    error = get_structured_error(exc_info.value)
    assert error.error_code == ErrorCode.STRATEGY_NOT_FOUND


def test_compile_strategy_with_overrides(strategy_tools_mcp, card_tools_mcp, schema_repository):
    """Test compiling a strategy with slot overrides."""
    # Setup: create strategy and card
    # Note: universe must include the symbol that will be used after overrides
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Override Strategy",
                "universe": ["ETH-USD"],  # Match the override symbol
            },
        )
    )
    strategy_id = strategy_result["strategy_id"]

    schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert schema is not None
    example_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")

    # Add card with overrides (automatically attached)
    run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": example_slots,
                "overrides": {
                    "context": {
                        "symbol": "ETH-USD",  # Override symbol
                        "tf": "4h",  # Override timeframe
                    },
                },
            },
        )
    )

    # Run: compile strategy
    result = run_async(
        call_tool(
            strategy_tools_mcp,
            "compile_strategy",
            {
                "strategy_id": strategy_id,
            },
        )
    )

    # Assert: verify overrides are applied
    response = CompileStrategyResponse(**result)
    assert response.status_hint == "ready"
    assert response.compiled is not None
    entry_card = response.compiled.cards[0]
    assert entry_card.effective_slots["context"]["symbol"] == "ETH-USD"
    assert entry_card.effective_slots["context"]["tf"] == "4h"


def test_compile_strategy_invalid_override_range(
    strategy_tools_mcp, card_tools_mcp, schema_repository
):
    """Test compiling a strategy with overrides that violate range constraints."""
    # Setup: create strategy with valid card
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Strategy with Invalid Override",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = strategy_result["strategy_id"]

    # Add card with invalid override (mult > 5.0) - automatically attached
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
                "overrides": {
                    "event": {"dip_band": {"mult": 10.0}},  # Max is 5.0
                },
            },
        )
    )

    # Run: compile strategy
    compile_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "compile_strategy",
            {"strategy_id": strategy_id},
        )
    )

    # Assert: verify validation error
    response = CompileStrategyResponse(**compile_result)
    assert response.status_hint == "fix_required"
    assert response.compiled is None
    assert len(response.issues) > 0
    validation_issue = next((i for i in response.issues if i.code == "SLOT_VALIDATION_ERROR"), None)
    assert validation_issue is not None
    assert "mult" in validation_issue.message.lower() or "10" in validation_issue.message
    assert validation_issue.severity == "error"


def test_compile_strategy_invalid_override_required_field(
    strategy_tools_mcp, card_tools_mcp, schema_repository
):
    """Test compiling a strategy with overrides that remove required fields."""
    # Setup: create strategy with valid card
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Strategy Missing Required Field",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = strategy_result["strategy_id"]

    # Add card with override that removes required field (tf) - automatically attached
    entry_schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert entry_schema is not None
    entry_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")
    # Note: deep_merge will replace the entire context dict if we pass an empty dict
    run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": entry_slots,
                "overrides": {
                    "context": {"tf": None},  # Try to remove tf by setting to None
                },
            },
        )
    )

    # Run: compile strategy
    compile_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "compile_strategy",
            {"strategy_id": strategy_id},
        )
    )

    # Assert: verify validation error
    response = CompileStrategyResponse(**compile_result)
    assert response.status_hint == "fix_required"
    assert response.compiled is None
    assert len(response.issues) > 0
    # Should have validation error for missing required field
    validation_issue = next((i for i in response.issues if i.code == "SLOT_VALIDATION_ERROR"), None)
    assert validation_issue is not None
    assert validation_issue.severity == "error"


def test_compile_strategy_invalid_override_additional_property(
    strategy_tools_mcp, card_tools_mcp, schema_repository
):
    """Test compiling a strategy with overrides that add invalid properties."""
    # Setup: create strategy with valid card
    strategy_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "create_strategy",
            {
                "name": "Strategy with Invalid Property",
                "universe": ["BTC-USD"],
            },
        )
    )
    strategy_id = strategy_result["strategy_id"]

    # Create valid entry card
    entry_schema = schema_repository.get_by_type_id("entry.trend_pullback")
    assert entry_schema is not None
    entry_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")
    # Add card with override that adds invalid property - automatically attached
    run_async(
        call_tool(
            strategy_tools_mcp,
            "add_card",
            {
                "strategy_id": strategy_id,
                "type": "entry.trend_pullback",
                "slots": entry_slots,
                "overrides": {
                    "invalid_property": "should_not_be_allowed",
                },
            },
        )
    )

    # Run: compile strategy
    compile_result = run_async(
        call_tool(
            strategy_tools_mcp,
            "compile_strategy",
            {"strategy_id": strategy_id},
        )
    )

    # Assert: verify validation error
    response = CompileStrategyResponse(**compile_result)
    assert response.status_hint == "fix_required"
    assert response.compiled is None
    assert len(response.issues) > 0
    validation_issue = next((i for i in response.issues if i.code == "SLOT_VALIDATION_ERROR"), None)
    assert validation_issue is not None
    assert validation_issue.severity == "error"
