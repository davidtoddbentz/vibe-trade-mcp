# Vibe Trade MCP Server

MCP server for creating and managing trading strategies.

## Setup

### Prerequisites

1. **Install uv** (if not already installed):
   ```bash
   brew install uv  # or pip install uv
   ```

2. **Install Docker** (for running Firestore emulator locally):
   ```bash
   brew install docker # or follow https://docs.docker.com/get-docker/
   ```

### Local Development

Local development uses the **Firestore Emulator** via Docker - no connection to production GCP needed.

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Start Firestore Emulator** (in a separate terminal):
   ```bash
   make emulator
   ```
   This will start the Docker-based emulator in the background.

3. **Set environment variables** (recommended: use `.env` file):
   
   Create a `.env` file in the project root (automatically loaded):
   ```bash
   # .env (not committed to git)
   FIRESTORE_EMULATOR_HOST=localhost:8081
   GOOGLE_CLOUD_PROJECT=demo-project
   FIRESTORE_DATABASE=(default)  # Required - emulator only supports "(default)"
   ```

   Or export them manually:
   ```bash
   export FIRESTORE_EMULATOR_HOST=localhost:8081
   export GOOGLE_CLOUD_PROJECT=demo-project
   export FIRESTORE_DATABASE=(default)
   ```

   **Note**: The `.env` file is automatically loaded by `python-dotenv` - no code changes needed!

4. **Run the server**:
   ```bash
   # Option 1: Using Makefile
   make run

   # Option 2: Direct command
   uv run main
   ```

   The server will start on `http://localhost:8080` and expose the MCP endpoint at `http://localhost:8080/mcp`

6. **Stop the emulator** (when done):
   ```bash
   make emulator-stop
   ```


## Development Commands

Use the Makefile for common tasks:

```bash
# Install dependencies
make install

# Start Firestore emulator (in separate terminal)
make emulator

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

### Current Tools

- `get_archetypes` - Fetch the catalog of available trading strategy archetypes
- `get_archetype_schema` - Fetch the JSON Schema for a specific archetype

## Project Structure

```
vibe-trade-mcp/
├── pyproject.toml          # Project config
├── README.md               # This file
├── data/
│   ├── archetypes.json          # Archetype definitions
│   └── archetype_schema.json   # Archetype JSON schemas
├── src/
│   ├── __init__.py
│   ├── main.py             # MCP server entry point
│   ├── db/
│   │   ├── __init__.py
│   │   ├── archetype_repository.py # Repository for Archetype data
│   │   └── firestore_client.py     # Singleton Firestore client
│   ├── models/
│   │   ├── __init__.py
│   │   └── archetype.py            # Pydantic models for Archetype
│   ├── scripts/
│   │   └── __init__.py
│   └── tools/
│       ├── __init__.py
│       └── trading_tools.py        # Trading strategy tools
└── tests/
    ├── conftest.py                      # Pytest fixtures
    ├── test_helpers.py                  # Shared test utilities
    ├── test_main.py
    ├── test_get_archetypes.py           # Tests for get_archetypes tool
    └── test_get_archetype_schema.py     # Tests for get_archetype_schema tool
```

## Architecture

- **FastMCP**: MCP server framework
- **Pydantic**: Type-safe models for tool inputs/outputs
- **HTTP Transport**: Ready for Cloud Run deployment
- **File-based Data**: Archetypes and schemas read from JSON files (no seeding required)
- **Firestore**: Available for future use (infrastructure ready)
- **Type Safety**: Strong typing throughout with Pydantic models

### Local vs Production

- **Archetypes & Schemas**: Read directly from JSON files in `data/` directory (no database needed)
- **Firestore**: Available for future use - infrastructure ready when needed
- **Local Development**: No Firestore emulator needed for archetypes/schemas (but available for future features)
- **Production**: Uses Cloud Run service account credentials (automatically configured)

## Deployment

Terraform infrastructure is now in a separate repository: [vibe-trade-terraform](../vibe-trade-terraform/).

See the terraform repository for Cloud Run deployment instructions.

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
