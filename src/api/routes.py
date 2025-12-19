"""API route handlers for HTTP endpoints."""

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_404_NOT_FOUND

from src.db.card_repository import CardRepository
from src.db.strategy_repository import StrategyRepository


async def get_strategy_with_cards(
    request: Request,
    strategy_repo: StrategyRepository,
    card_repo: CardRepository,
) -> JSONResponse:
    """Get a strategy with all its attached cards.

    Args:
        request: Starlette request object
        strategy_repo: Strategy repository instance
        card_repo: Card repository instance

    Returns:
        JSONResponse containing:
        - strategy: Full strategy metadata
        - cards: List of all cards with their attachment metadata (role, overrides, etc.)
        - card_count: Number of cards attached
    """
    strategy_id = request.path_params["strategy_id"]
    # Get strategy
    strategy = strategy_repo.get_by_id(strategy_id)
    if strategy is None:
        return JSONResponse(
            status_code=HTTP_404_NOT_FOUND,
            content={"error": f"Strategy not found: {strategy_id}"},
        )

    # Get all cards from attachments
    cards = []
    for attachment in strategy.attachments:
        card = card_repo.get_by_id(attachment.card_id)
        if card is not None:
            cards.append(
                {
                    "id": card.id,
                    "type": card.type,
                    "slots": card.slots,
                    "schema_etag": card.schema_etag,
                    "role": attachment.role,
                    "enabled": attachment.enabled,
                    "overrides": attachment.overrides,
                    "follow_latest": attachment.follow_latest,
                    "card_revision_id": attachment.card_revision_id,
                    "created_at": card.created_at,
                    "updated_at": card.updated_at,
                }
            )

    # Return combined response
    return JSONResponse(
        {
            "strategy": {
                "id": strategy.id,
                "owner_id": strategy.owner_id,
                "name": strategy.name,
                "status": strategy.status,
                "universe": strategy.universe,
                "version": strategy.version,
                "created_at": strategy.created_at,
                "updated_at": strategy.updated_at,
            },
            "cards": cards,
            "card_count": len(cards),
        }
    )
