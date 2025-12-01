# Vibe Trade MCP Server

MCP server for creating and managing trading strategies.

## Setup

### Prerequisites

1. **Install uv** (if not already installed):
   ```bash
   brew install uv  # or pip install uv
   ```

2. **Install gcloud CLI** (for Firestore emulator):
   ```bash
   brew install google-cloud-sdk  # or follow https://cloud.google.com/sdk/docs/install
   ```

### Local Development

Local development uses the **Firestore Emulator** - no connection to production GCP.

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Choose your Firestore setup**:

   **Option A: Use Emulator** (Docker-based, no Java/Xcode needed):
   ```bash
   # Start emulator (runs in background, requires Docker)
   make emulator
   
   # Stop emulator
   make emulator-stop
   ```
   
   **Option B: Use Real Firestore** (simpler, no Java needed):
   ```bash
   # Authenticate with GCP
   gcloud auth application-default login
   gcloud config set project vibe-trade-475704
   ```
   Then skip step 3 and just set `GOOGLE_CLOUD_PROJECT` in `.env`

3. **Set environment variables** (recommended: use `.env` file):
   
   Create a `.env` file in the project root (automatically loaded):
   
   **For Emulator:**
   ```bash
   # .env (not committed to git)
   FIRESTORE_EMULATOR_HOST=localhost:8081
   GOOGLE_CLOUD_PROJECT=demo-project
   FIRESTORE_DATABASE=(default)  # Required - emulator only supports "(default)"
   ```
   
   **For Real Firestore:**
   ```bash
   # .env (not committed to git)
   GOOGLE_CLOUD_PROJECT=vibe-trade-475704
   FIRESTORE_DATABASE=strategy  # Required
   # (no FIRESTORE_EMULATOR_HOST)
   ```

   Or export them manually:
   ```bash
   export FIRESTORE_EMULATOR_HOST=localhost:8081
   export GOOGLE_CLOUD_PROJECT=demo-project
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

5. **Seed the database** (optional):
   ```bash
   # Seed local emulator
   make seed

   # Or see what would be done first
   make seed-dry-run
   ```

**Note**: 
- **With Emulator**: Starts with empty database. Seed it with `make seed`.
- **With Real Firestore**: Uses your actual Firestore database. Be careful with `make seed` - it will write to your real database!

## Development Commands

Use the Makefile for common tasks:

```bash
# Install dependencies
make install

# Start Firestore emulator (in separate terminal)
make emulator

# Seed database with archetypes
make seed              # Seed local emulator
make seed-dry-run      # See what would be done
make seed-prod         # Seed production (requires GOOGLE_CLOUD_PROJECT)

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

## Project Structure

```
vibe-trade-mcp/
├── pyproject.toml          # Project config
├── README.md               # This file
├── data/
│   └── archetypes.json     # Seed data for archetypes
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
│   │   ├── __init__.py
│   │   └── seed_archetypes.py      # Script to seed Firestore
│   └── tools/
│       ├── __init__.py
│       └── trading_tools.py        # Trading strategy tools
└── tests/
    ├── conftest.py                 # Pytest fixtures for Firestore
    ├── test_main.py
    └── test_trading_tools.py       # Tests for trading tools
```

## Architecture

- **FastMCP**: MCP server framework
- **Pydantic**: Type-safe models for tool inputs/outputs
- **HTTP Transport**: Ready for Cloud Run deployment
- **Firestore**: NoSQL database for strategy data (local and production)
- **Type Safety**: Strong typing throughout with Pydantic models

### Local vs Production

- **Local**: Uses Firestore Emulator (no GCP connection needed). Set `FIRESTORE_EMULATOR_HOST=localhost:8081`
- **Production**: Uses Cloud Run service account credentials (automatically configured)
- Both environments use the "strategy" database - emulator for local, real Firestore for production
- The code is identical - environment variables control which backend is used

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
