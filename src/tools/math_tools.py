"""Basic math tools for testing MCP functionality."""

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field


# Pydantic models for tool responses
class MathOperationResult(BaseModel):
    """Result of a math operation."""

    result: float = Field(..., description="The calculated result")
    operation: str = Field(..., description="The operation that was performed")
    inputs: dict[str, float] = Field(..., description="The input values used")


class CalculationResult(BaseModel):
    """Result of a calculation expression."""

    result: float = Field(..., description="The calculated result")
    expression: str = Field(..., description="The expression that was evaluated")
    operation: str = Field(default="calculation", description="The operation type")


def register_math_tools(mcp: FastMCP) -> None:
    """Register all math tools with the MCP server."""

    @mcp.tool()
    def add(a: float, b: float) -> MathOperationResult:
        """
        Add two numbers together.

        Args:
            a: First number
            b: Second number

        Returns:
            MathOperationResult with the calculation result
        """
        result = a + b
        return MathOperationResult(result=result, operation="addition", inputs={"a": a, "b": b})

    @mcp.tool()
    def multiply(a: float, b: float) -> MathOperationResult:
        """
        Multiply two numbers together.

        Args:
            a: First number
            b: Second number

        Returns:
            MathOperationResult with the calculation result
        """
        result = a * b
        return MathOperationResult(
            result=result, operation="multiplication", inputs={"a": a, "b": b}
        )

    @mcp.tool()
    def subtract(a: float, b: float) -> MathOperationResult:
        """
        Subtract second number from first number.

        Args:
            a: First number (minuend)
            b: Second number (subtrahend)

        Returns:
            MathOperationResult with the calculation result
        """
        result = a - b
        return MathOperationResult(result=result, operation="subtraction", inputs={"a": a, "b": b})

    @mcp.tool()
    def divide(a: float, b: float) -> MathOperationResult:
        """
        Divide first number by second number.

        Args:
            a: Dividend
            b: Divisor

        Returns:
            MathOperationResult with the calculation result

        Raises:
            ValueError: If divisor is zero
        """
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        return MathOperationResult(result=result, operation="division", inputs={"a": a, "b": b})

    @mcp.tool()
    def power(base: float, exponent: float) -> MathOperationResult:
        """
        Calculate base raised to the power of exponent.

        Args:
            base: Base number
            exponent: Exponent

        Returns:
            MathOperationResult with the calculation result
        """
        result = base**exponent
        return MathOperationResult(
            result=result, operation="power", inputs={"base": base, "exponent": exponent}
        )

    @mcp.tool()
    def calculate(expression: str) -> CalculationResult:
        """
        Evaluate a simple mathematical expression.

        Args:
            expression: Mathematical expression (e.g., "2 + 3 * 4")

        Returns:
            CalculationResult with the evaluated expression result

        Note: Only supports basic operations for safety.
        """
        # Simple safe evaluation - only allow numbers and basic operators
        allowed_chars = set("0123456789+-*/()., ")
        if not all(c in allowed_chars for c in expression):
            raise ValueError("Expression contains invalid characters")

        try:
            result = eval(expression)
            return CalculationResult(result=float(result), expression=expression)
        except Exception as e:
            raise ValueError(f"Error evaluating expression: {str(e)}") from None
