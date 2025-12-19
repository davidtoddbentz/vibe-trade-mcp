"""API endpoints and middleware for the MCP server."""

from src.api.middleware import create_auth_middleware
from src.api.routes import get_strategy_with_cards

__all__ = ["create_auth_middleware", "get_strategy_with_cards"]
