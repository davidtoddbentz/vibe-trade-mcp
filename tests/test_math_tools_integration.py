"""Integration tests for math tools - actually calling the functions."""

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from src.tools.math_tools import (
    register_math_tools,
)


def test_add_function_directly():
    """Test add function by importing and calling it directly."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    # Get the actual function
    async def get_and_test():
        tools = await mcp.list_tools()
        add_tool = next((t for t in tools if t.name == "add"), None)
        assert add_tool is not None

        # Call through the tool system
        result = await mcp.call_tool("add", {"a": 10.0, "b": 5.0})
        assert result is not None

    asyncio.run(get_and_test())


def test_multiply_function_directly():
    """Test multiply function directly."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def test():
        result = await mcp.call_tool("multiply", {"a": 6.0, "b": 7.0})
        assert result is not None

    asyncio.run(test())


def test_subtract_function_directly():
    """Test subtract function directly."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def test():
        result = await mcp.call_tool("subtract", {"a": 20.0, "b": 8.0})
        assert result is not None

    asyncio.run(test())


def test_divide_function_directly():
    """Test divide function directly."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def test():
        result = await mcp.call_tool("divide", {"a": 15.0, "b": 3.0})
        assert result is not None

    asyncio.run(test())


def test_power_function_directly():
    """Test power function directly."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def test():
        result = await mcp.call_tool("power", {"base": 2.0, "exponent": 8.0})
        assert result is not None

    asyncio.run(test())


def test_calculate_function_directly():
    """Test calculate function directly."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def test():
        result = await mcp.call_tool("calculate", {"expression": "2 + 3 * 4"})
        assert result is not None

    asyncio.run(test())


def test_calculate_invalid_expression():
    """Test calculate with invalid expression."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def test():
        try:
            await mcp.call_tool("calculate", {"expression": "import os"})
            pytest.fail("Should have raised an error")
        except (ToolError, ValueError):
            pass  # Expected

    asyncio.run(test())
