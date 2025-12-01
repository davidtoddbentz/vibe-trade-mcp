"""Shared test utilities for trading tool tests."""

import asyncio
import json
from typing import Any

from mcp.server.fastmcp import FastMCP


def extract_tool_result(result: Any) -> dict:
    """Extract the actual result from FastMCP's call_tool return value.

    FastMCP returns a tuple (content, result_dict) where content is a list
    of TextContent objects and result_dict is the parsed result.

    Args:
        result: The return value from mcp.call_tool()

    Returns:
        dict: The parsed result dictionary
    """
    if isinstance(result, tuple):
        content, result_dict = result
        # If result_dict is a dict (successful result), return it
        if isinstance(result_dict, dict):
            return result_dict
        # Otherwise, extract from content (TextContent objects)
        if content and len(content) > 0:
            text = content[0].text if hasattr(content[0], "text") else str(content[0])
            # Parse JSON string to dict
            return json.loads(text)
        return {}
    # If it's already a dict, return it
    return result if isinstance(result, dict) else {}


async def call_tool(mcp: FastMCP, tool_name: str, arguments: dict) -> dict:
    """Call an MCP tool and extract the result.

    Args:
        mcp: The FastMCP server instance
        tool_name: Name of the tool to call
        arguments: Arguments to pass to the tool

    Returns:
        dict: The parsed result dictionary
    """
    result = await mcp.call_tool(tool_name, arguments)
    return extract_tool_result(result)


def run_async(coro):
    """Run an async function synchronously in tests.

    Args:
        coro: The coroutine to run

    Returns:
        The result of the coroutine
    """
    return asyncio.run(coro)
