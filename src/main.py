#!/usr/bin/env python3
"""Main MCP server entry point."""

import os

from mcp.server.fastmcp import FastMCP

from src.tools.math_tools import register_math_tools

# Cloud Run sets PORT environment variable (defaults to 8080)
port = int(os.getenv("PORT", "8080"))

# Create MCP server instance with port configuration
mcp = FastMCP("vibe-trade-server", port=port)

# Register tools
register_math_tools(mcp)


def main():
    """Run the MCP server."""
    print("🚀 Starting Vibe Trade MCP Server...")
    print(f"📡 Server running on port {port}")
    print(f"🔗 MCP endpoint: http://0.0.0.0:{port}/mcp")
    print("✅ Ready for agent connections")

    # Use streamable-http for Cloud Run deployment
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
