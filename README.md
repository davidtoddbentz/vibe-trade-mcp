# Vibe Trade MCP Server

MCP server for creating and managing trading strategies.

## Setup

```bash
# Install uv (if not already installed)
brew install uv  # or pip install uv

# Install dependencies
uv sync

# Run the server
uv run main
```

## Development Commands

Use the Makefile for common tasks:

```bash
# Install dependencies
make install

# Run tests
make test

# Run tests with coverage (requires 60%)
make test-cov

# Lint code
make lint

# Auto-fix linting issues
make lint-fix

# Format code
make format

# Check formatting
make format-check

# Run all CI checks locally
make ci

# Clean build artifacts
make clean
```

Or use `uv run` directly:
```bash
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format .
```

## Development

The server uses FastMCP from the `mcp` package. Tools are defined in `src/tools/`.

### Adding New Tools

1. Create a new file in `src/tools/` (e.g., `trading_tools.py`)
2. Define Pydantic models for request/response types
3. Register tools with the `@mcp.tool()` decorator
4. Import and register in `src/main.py`

Example:
```python
# src/tools/trading_tools.py
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

class TradeResult(BaseModel):
    success: bool
    message: str

def register_trading_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_strategy(name: str) -> TradeResult:
        """Create a new trading strategy."""
        return TradeResult(success=True, message=f"Strategy {name} created")
```

### Current Tools (Example/Demo)

- `add` - Add two numbers
- `multiply` - Multiply two numbers
- `subtract` - Subtract two numbers
- `divide` - Divide two numbers
- `power` - Calculate power
- `calculate` - Evaluate mathematical expression

## Project Structure

```
vibe-trade-mcp/
├── pyproject.toml          # Project config
├── README.md               # This file
├── src/
│   ├── __init__.py
│   ├── main.py             # MCP server entry point
│   └── tools/
│       ├── __init__.py
│       └── math_tools.py  # Math tools (for testing)
└── tests/
    └── test_tools.py       # Tests
```

## Architecture

- **FastMCP**: MCP server framework
- **Pydantic**: Type-safe models for tool inputs/outputs
- **HTTP Transport**: Ready for Cloud Run deployment
- **Type Safety**: Strong typing throughout with Pydantic models

## Deployment

See [terraform/README.md](terraform/README.md) for Cloud Run deployment instructions.

The server automatically:
- Uses HTTP transport for Cloud Run (reads `PORT` env var)
- Exposes tools at `/mcp` endpoint
- Validates all inputs/outputs with Pydantic

## Authentication

See [AUTHENTICATION.md](AUTHENTICATION.md) for detailed authentication instructions.

**Quick auth:**
```bash
# Get identity token
gcloud auth print-identity-token

# Use in MCP client with header:
# Authorization: Bearer <token>
```
