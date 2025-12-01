#!/usr/bin/env python3
"""Main MCP server entry point."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from src.db.firestore_client import FirestoreClient
from src.tools.trading_tools import register_trading_tools

# Load .env file if it exists (for local development)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Initialize Firestore client with project from environment
project = os.getenv("GOOGLE_CLOUD_PROJECT")
if not project:
    raise ValueError(
        "GOOGLE_CLOUD_PROJECT environment variable must be set. "
        "For local dev: export GOOGLE_CLOUD_PROJECT=demo-project"
    )
FirestoreClient.get_client(project=project)

# Cloud Run sets PORT environment variable (defaults to 8080)
port = int(os.getenv("PORT", "8080"))

# Create MCP server instance with port configuration
# For Cloud Run, we need to bind to 0.0.0.0 to accept external connections
mcp = FastMCP("vibe-trade-server", port=port, host="0.0.0.0")

# Register tools
register_trading_tools(mcp)


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
