#!/usr/bin/env python3
"""Main MCP server entry point."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from src.db.archetype_repository import ArchetypeRepository
from src.db.archetype_schema_repository import ArchetypeSchemaRepository
from src.db.card_repository import CardRepository
from src.db.firestore_client import FirestoreClient
from src.db.strategy_repository import StrategyRepository
from src.tools.card_tools import register_card_tools
from src.tools.strategy_tools import register_strategy_tools
from src.tools.trading_tools import register_trading_tools

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

# Create MCP server instance with port configuration
# For Cloud Run, we need to bind to 0.0.0.0 to accept external connections
mcp = FastMCP("vibe-trade-server", port=port, host="0.0.0.0")

# Register tools with injected repositories
register_trading_tools(mcp, archetype_repo, schema_repo)
register_card_tools(mcp, card_repo, schema_repo)
register_strategy_tools(mcp, strategy_repo, card_repo)


def main():
    """Run the MCP server."""
    print("🚀 Starting Vibe Trade MCP Server...", file=sys.stderr, flush=True)
    print(f"📡 Server running on port {port}", file=sys.stderr, flush=True)
    print(f"🔗 MCP endpoint: http://0.0.0.0:{port}/mcp", file=sys.stderr, flush=True)
    print("✅ Ready for agent connections", file=sys.stderr, flush=True)

    # Use streamable-http for Cloud Run deployment
    try:
        mcp.run(transport="streamable-http")
    except Exception as e:
        print(f"❌ Error starting server: {e}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
