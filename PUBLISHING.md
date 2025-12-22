# Publishing vibe-trade-mcp to PyPI

This guide explains how to publish `vibe-trade-mcp` as a Python package so other projects (like `vibe-trade-api`) can install it as a dependency.

## Prerequisites

1. **PyPI Account**: Create an account at https://pypi.org/account/register/
2. **API Token**: Generate a token at https://pypi.org/manage/account/token/
   - For production: Use a project-scoped token
   - For testing: Use TestPyPI at https://test.pypi.org/manage/account/token/

## Publishing Steps

### 1. Build the Package

```bash
make build-package
# or
uv build
```

This creates distribution files in `dist/`:
- `vibe_trade_mcp-0.1.0.tar.gz` (source distribution)
- `vibe_trade_mcp-0.1.0-py3-none-any.whl` (wheel)

### 2. Test on TestPyPI (Recommended First)

```bash
# Set your TestPyPI token
export TESTPYPI_TOKEN="pypi-..."

# Build and publish to TestPyPI
make publish-test
```

### 3. Install from TestPyPI to Verify

```bash
pip install -i https://test.pypi.org/simple/ vibe-trade-mcp
python -c "from vibe_trade_mcp.db.firestore_client import FirestoreClient; print('✅ Import works!')"
```

### 4. Publish to Production PyPI

```bash
# Set your PyPI token
export PYPI_TOKEN="pypi-..."

# Build and publish to PyPI
make publish
```

### 5. Install from PyPI

```bash
pip install vibe-trade-mcp
```

## Version Management

Before publishing a new version:

1. **Update version** in `pyproject.toml`:
   ```toml
   version = "0.1.1"  # Increment as needed
   ```

2. **Build and test locally**:
   ```bash
   make build-package
   pip install dist/vibe_trade_mcp-*.whl  # Test installation
   python -c "from vibe_trade_mcp.db.firestore_client import FirestoreClient; print('✅ Works!')"
   ```

3. **Publish**:
   ```bash
   make publish
   ```

## Using in Other Projects

Once published, other projects can install it:

```toml
# In pyproject.toml
dependencies = [
    "vibe-trade-mcp>=0.1.0",
]
```

Then install:
```bash
uv sync
# or
pip install vibe-trade-mcp
```

Import in code:
```python
from vibe_trade_mcp.db.firestore_client import FirestoreClient
from vibe_trade_mcp.db.strategy_repository import StrategyRepository
from vibe_trade_mcp.db.card_repository import CardRepository
```

## Package Structure

When installed, the package structure is:
```
vibe_trade_mcp/
  ├── __init__.py
  ├── api/
  ├── db/
  │   ├── firestore_client.py
  │   ├── strategy_repository.py
  │   └── ...
  ├── models/
  └── tools/
```

**Note**: MCP's internal code uses `from src.` imports, which is fine for MCP as a standalone server. The package mapping (`package-dir`) ensures that when installed, other projects can import using `from vibe_trade_mcp.`.
