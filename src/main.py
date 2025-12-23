#!/usr/bin/env python3
"""Main MCP server entry point."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .. api import create_auth_middleware, get_strategy_with_cards
from .. db.archetype_repository import ArchetypeRepository
from .. db.archetype_schema_repository import ArchetypeSchemaRepository
from .. db.card_repository import CardRepository
from .. db.firestore_client import FirestoreClient
from .. db.strategy_repository import StrategyRepository
from .. tools.card_tools import register_card_tools
from .. tools.resource_tools import register_archetype_resources
from .. tools.strategy_tools import register_strategy_tools
from .. tools.trading_tools import register_trading_tools

# Load .env file if it exists (for local development)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Initialize repositories
archetype_repo = ArchetypeRepository()
schema_repo = ArchetypeSchemaRepository()

# Initialize card repository (requires Firestore)
# Read Firestore configuration from environment
project = os.getenv("GOOGLE_CLOUD_PROJECT")
if not project:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable must be set")

database = os.getenv("FIRESTORE_DATABASE")
if not database:
    raise ValueError(
        "FIRESTORE_DATABASE environment variable must be set. "
        "For emulator: FIRESTORE_DATABASE=(default) "
        "For production: FIRESTORE_DATABASE=strategy"
    )
# Use None for "(default)" database (emulator limitation)
database = None if database == "(default)" else database

firestore_client = FirestoreClient.get_client(project=project, database=database)
card_repo = CardRepository(client=firestore_client)
strategy_repo = StrategyRepository(client=firestore_client)

# Cloud Run sets PORT environment variable (defaults to 8080)
port = int(os.getenv("PORT", "8080"))

# Authentication token (optional - if not set, no auth required)
# Set MCP_AUTH_TOKEN environment variable to enable authentication
auth_token = os.getenv("MCP_AUTH_TOKEN")

# Create MCP server instance with port configuration
# For Cloud Run, we need to bind to 0.0.0.0 to accept external connections
# stateless_http=True enables compatibility with OpenAI's Responses API
# which sends GET requests without establishing a session first
mcp = FastMCP("vibe-trade-server", port=port, host="0.0.0.0", stateless_http=True)

# Wrap streamable_http_app to add custom endpoints and optional auth middleware
# We need to wrap streamable_http_app() because it creates a new app each time
original_streamable_http_app = mcp.streamable_http_app


def wrapped_streamable_http_app():
    """Wrap streamable_http_app to add custom endpoints and auth middleware."""
    from starlette.requests import Request

    app = original_streamable_http_app()

    # Create route handler with repositories injected
    async def strategy_with_cards_handler(request: Request):
        """Route handler wrapper that injects repositories."""
        return await get_strategy_with_cards(request, strategy_repo, card_repo)

    app.add_route("/api/strategies/{strategy_id}", strategy_with_cards_handler, methods=["GET"])

    # Add authentication middleware if token is configured
    if auth_token:
        auth_middleware_func = create_auth_middleware(auth_token)
        app.middleware("http")(auth_middleware_func)

    return app


# Replace the method with our wrapped version
mcp.streamable_http_app = wrapped_streamable_http_app

# Register tools with injected repositories
register_trading_tools(mcp, archetype_repo, schema_repo)
register_card_tools(mcp, card_repo, schema_repo, strategy_repo)
register_strategy_tools(mcp, strategy_repo, card_repo, schema_repo)

# Register resources for archetype data (makes it easier for agents to discover archetypes)
register_archetype_resources(mcp, archetype_repo, schema_repo)


def main():
    """Run the MCP server."""
    print("🚀 Starting Vibe Trade MCP Server...", file=sys.stderr, flush=True)
    print(f"📡 Server running on port {port}", file=sys.stderr, flush=True)
    print(f"🔗 MCP endpoint: http://0.0.0.0:{port}/mcp", file=sys.stderr, flush=True)
    print(
        f"📋 API endpoint: http://0.0.0.0:{port}/api/strategies/{{strategy_id}}",
        file=sys.stderr,
        flush=True,
    )
    if auth_token:
        print("🔒 Authentication enabled (static token)", file=sys.stderr, flush=True)
    else:
        print("⚠️  Authentication disabled (no MCP_AUTH_TOKEN set)", file=sys.stderr, flush=True)
    print("✅ Ready for agent connections", file=sys.stderr, flush=True)

    # Use streamable-http for Cloud Run deployment
    try:
        mcp.run(transport="streamable-http")
    except Exception as e:
        print(f"❌ Error starting server: {e}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
