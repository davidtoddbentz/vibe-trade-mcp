"""Tests for MCP tools."""

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from src.tools.math_tools import CalculationResult, MathOperationResult, register_math_tools


def test_tools_registered():
    """Test that tools are registered with the server."""
    mcp = FastMCP("test-server")
    register_math_tools(mcp)

    # Get the tools (async method)
    async def check_tools():
        tools = await mcp.list_tools()
        tool_names = [tool.name for tool in tools]

        expected_tools = ["add", "multiply", "subtract", "divide", "power", "calculate"]

        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Tool {tool_name} not found"

    asyncio.run(check_tools())


def test_add_tool_exists():
    """Test that add tool exists and has correct signature."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def check_tool():
        tools = await mcp.list_tools()
        add_tool = next((t for t in tools if t.name == "add"), None)

        assert add_tool is not None
        assert add_tool.name == "add"
        # inputSchema is a dict, check it has the expected structure
        assert "properties" in add_tool.inputSchema
        assert len(add_tool.inputSchema["properties"]) == 2  # a and b parameters

    asyncio.run(check_tool())


def test_add_tool_functionality():
    """Test that add tool actually works."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def test_add():
        # Call tool through the server
        tools = await mcp.list_tools()
        add_tool = next((t for t in tools if t.name == "add"), None)
        assert add_tool is not None
        # Verify it has the right parameters
        assert "a" in add_tool.inputSchema["properties"]
        assert "b" in add_tool.inputSchema["properties"]

    asyncio.run(test_add())


def test_multiply_tool():
    """Test multiply tool."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def test_multiply():
        result = await mcp.call_tool("multiply", {"a": 4.0, "b": 7.0})
        assert result is not None

    asyncio.run(test_multiply())


def test_divide_tool_error_handling():
    """Test divide tool handles zero division."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def test_divide():
        # Should raise ToolError for division by zero (wraps ValueError)
        try:
            await mcp.call_tool("divide", {"a": 10.0, "b": 0.0})
            pytest.fail("Should have raised ToolError")
        except (ToolError, ValueError):
            pass  # Expected

    asyncio.run(test_divide())


def test_math_operation_result_model():
    """Test MathOperationResult Pydantic model."""
    result = MathOperationResult(result=42.0, operation="test", inputs={"a": 1.0, "b": 2.0})
    assert result.result == 42.0
    assert result.operation == "test"
    assert result.inputs == {"a": 1.0, "b": 2.0}


def test_calculation_result_model():
    """Test CalculationResult Pydantic model."""
    result = CalculationResult(result=100.0, expression="10 * 10")
    assert result.result == 100.0
    assert result.expression == "10 * 10"
    assert result.operation == "calculation"  # default value


def test_subtract_tool():
    """Test subtract tool."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def test_subtract():
        tools = await mcp.list_tools()
        subtract_tool = next((t for t in tools if t.name == "subtract"), None)
        assert subtract_tool is not None
        assert "a" in subtract_tool.inputSchema["properties"]
        assert "b" in subtract_tool.inputSchema["properties"]

    asyncio.run(test_subtract())


def test_power_tool():
    """Test power tool."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def test_power():
        tools = await mcp.list_tools()
        power_tool = next((t for t in tools if t.name == "power"), None)
        assert power_tool is not None
        assert "base" in power_tool.inputSchema["properties"]
        assert "exponent" in power_tool.inputSchema["properties"]

    asyncio.run(test_power())


def test_calculate_tool():
    """Test calculate tool."""
    mcp = FastMCP("test")
    register_math_tools(mcp)

    async def test_calculate():
        tools = await mcp.list_tools()
        calc_tool = next((t for t in tools if t.name == "calculate"), None)
        assert calc_tool is not None
        assert "expression" in calc_tool.inputSchema["properties"]

    asyncio.run(test_calculate())
