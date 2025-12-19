"""Tests for HTTP API endpoints."""

import pytest
from starlette.testclient import TestClient
from test_helpers import get_valid_slots_for_archetype, run_async

from src.tools.card_tools import register_card_tools
from src.tools.resource_tools import register_archetype_resources
from src.tools.strategy_tools import register_strategy_tools
from src.tools.trading_tools import register_trading_tools


@pytest.fixture
def api_mcp(
    firestore_client,
    archetype_repository,
    schema_repository,
    card_repository,
    strategy_repository,
):
    """Create an MCP server instance with all tools and API endpoints registered."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("test-server", port=0, host="127.0.0.1", stateless_http=True)

    # Register all tools
    register_trading_tools(mcp, archetype_repository, schema_repository)
    register_card_tools(mcp, card_repository, schema_repository, strategy_repository)
    register_strategy_tools(mcp, strategy_repository, card_repository, schema_repository)
    register_archetype_resources(mcp, archetype_repository, schema_repository)

    # Wrap the app to add API endpoints (similar to main.py)
    original_streamable_http_app = mcp.streamable_http_app

    def wrapped_streamable_http_app():
        """Wrap streamable_http_app to add API endpoints."""
        from starlette.requests import Request

        from src.api import get_strategy_with_cards

        app = original_streamable_http_app()

        async def strategy_with_cards_handler(request: Request):
            """Route handler wrapper that injects repositories."""
            return await get_strategy_with_cards(request, strategy_repository, card_repository)

        app.add_route("/api/strategies/{strategy_id}", strategy_with_cards_handler, methods=["GET"])

        return app

    mcp.streamable_http_app = wrapped_streamable_http_app

    return mcp


def test_get_strategy_with_cards_success(api_mcp, schema_repository):
    """Test getting a strategy with all its cards via API endpoint."""
    # Setup: create a strategy with cards
    from test_helpers import call_tool

    # Create strategy
    create_strategy_result = run_async(
        call_tool(api_mcp, "create_strategy", {"name": "Test Strategy", "universe": ["BTC-USD"]})
    )
    strategy_id = create_strategy_result["strategy_id"]

    # Create entry card
    entry_slots = get_valid_slots_for_archetype(schema_repository, "entry.trend_pullback")
    create_entry_result = run_async(
        call_tool(
            api_mcp,
            "create_card",
            {"type": "entry.trend_pullback", "slots": entry_slots},
        )
    )
    entry_card_id = create_entry_result["card_id"]

    # Create exit card
    exit_slots = get_valid_slots_for_archetype(schema_repository, "exit.rule_trigger")
    create_exit_result = run_async(
        call_tool(
            api_mcp,
            "create_card",
            {"type": "exit.rule_trigger", "slots": exit_slots},
        )
    )
    exit_card_id = create_exit_result["card_id"]

    # Attach cards to strategy
    run_async(
        call_tool(
            api_mcp,
            "attach_card",
            {"strategy_id": strategy_id, "card_id": entry_card_id, "role": "entry"},
        )
    )
    run_async(
        call_tool(
            api_mcp,
            "attach_card",
            {"strategy_id": strategy_id, "card_id": exit_card_id, "role": "exit"},
        )
    )

    # Run: call API endpoint
    app = api_mcp.streamable_http_app()
    client = TestClient(app)
    response = client.get(f"/api/strategies/{strategy_id}")

    # Assert: verify response
    assert response.status_code == 200
    data = response.json()
    assert "strategy" in data
    assert "cards" in data
    assert "card_count" in data

    # Verify strategy data
    strategy = data["strategy"]
    assert strategy["id"] == strategy_id
    assert strategy["name"] == "Test Strategy"
    assert strategy["universe"] == ["BTC-USD"]
    assert strategy["status"] == "draft"

    # Verify cards data
    assert data["card_count"] == 2
    assert len(data["cards"]) == 2

    # Check that cards have attachment metadata
    card_ids = {card["id"] for card in data["cards"]}
    assert entry_card_id in card_ids
    assert exit_card_id in card_ids

    # Verify each card has role and other attachment fields
    for card in data["cards"]:
        assert "role" in card
        assert card["role"] in ["entry", "exit"]
        assert "enabled" in card
        assert "overrides" in card
        assert "type" in card
        assert "slots" in card


def test_get_strategy_with_cards_not_found(api_mcp):
    """Test getting a non-existent strategy returns 404."""
    # Run: call API endpoint with non-existent ID
    app = api_mcp.streamable_http_app()
    client = TestClient(app)
    response = client.get("/api/strategies/nonexistent-id")

    # Assert: verify 404 response
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "nonexistent-id" in data["error"]


def test_get_strategy_with_no_cards(api_mcp):
    """Test getting a strategy with no cards attached."""
    # Setup: create a strategy without cards
    from test_helpers import call_tool

    create_strategy_result = run_async(
        call_tool(api_mcp, "create_strategy", {"name": "Empty Strategy"})
    )
    strategy_id = create_strategy_result["strategy_id"]

    # Run: call API endpoint
    app = api_mcp.streamable_http_app()
    client = TestClient(app)
    response = client.get(f"/api/strategies/{strategy_id}")

    # Assert: verify response
    assert response.status_code == 200
    data = response.json()
    assert data["card_count"] == 0
    assert data["cards"] == []
    assert data["strategy"]["id"] == strategy_id
