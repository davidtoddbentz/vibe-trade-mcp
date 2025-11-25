#!/usr/bin/env python3
"""Main MCP server entry point."""

import os

from mcp.server.fastmcp import FastMCP

from src.tools.math_tools import register_math_tools

# Cloud Run sets PORT environment variable (defaults to 8080)
port = int(os.getenv("PORT", "8080"))

# Create MCP server instance with port configuration
# For Cloud Run, we need to bind to 0.0.0.0 to accept external connections
mcp = FastMCP("vibe-trade-server", port=port, host="0.0.0.0")

# Register tools
register_math_tools(mcp)


def main():
    """Run the MCP server."""
    import sys

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
