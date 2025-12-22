# Publishing vibe-trade-mcp to GCP Artifact Registry

This guide explains how to publish `vibe-trade-mcp` as a Python package to GCP Artifact Registry so other projects (like `vibe-trade-api`) can install it as a dependency.

## Prerequisites

1. **GCP Project**: Ensure you have access to the GCP project
2. **Artifact Registry Repository**: The Python repository must be created in Terraform (see `vibe-trade-terraform`)
3. **gcloud CLI**: Authenticated with `gcloud auth login` and `gcloud auth application-default login`
4. **twine**: Will be installed automatically if not present

## Publishing Steps

### 1. Ensure Python Repository Exists

The Python package repository is created via Terraform:

```bash
cd vibe-trade-terraform
terraform apply  # Creates vibe-trade-python repository
```

### 2. Build the Package

```bash
make build-package
# or
uv build
```

This creates distribution files in `dist/`:
- `vibe_trade_mcp-0.1.0.tar.gz` (source distribution)
- `vibe_trade_mcp-0.1.0-py3-none-any.whl` (wheel)

### 3. Publish to GCP Artifact Registry

```bash
# With defaults (us-central1, vibe-trade-475704, vibe-trade-python)
make publish

# Or with custom settings
REGION=us-central1 PROJECT_ID=your-project PYTHON_REPO=vibe-trade-python make publish
```

The command will:
1. Build the package
2. Authenticate with GCP using `gcloud auth configure-docker`
3. Upload to Artifact Registry using `twine`

### 4. Install from GCP Artifact Registry

```bash
# Get the repository URL from Terraform
cd vibe-trade-terraform
terraform output python_package_repo_url

# Install using the URL
pip install --index-url https://us-central1-python.pkg.dev/vibe-trade-475704/vibe-trade-python/simple/ vibe-trade-mcp
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

Once published, other projects can install it by configuring the GCP Artifact Registry index:

```toml
# In pyproject.toml
dependencies = [
    "vibe-trade-mcp>=0.1.0",
]

[[tool.uv.index]]
name = "gcp-artifact-registry"
url = "https://us-central1-python.pkg.dev/vibe-trade-475704/vibe-trade-python/simple/"
explicit = false
```

Then install:
```bash
uv sync
# or with pip
pip install --index-url https://us-central1-python.pkg.dev/vibe-trade-475704/vibe-trade-python/simple/ vibe-trade-mcp
```

**For Cloud Run/Docker**: Authentication is automatic via service account credentials.

**For local development**: Authenticate with:
```bash
gcloud auth application-default login
gcloud auth configure-docker us-central1-python.pkg.dev
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
