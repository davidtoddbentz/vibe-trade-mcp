# Deployment Guide

This guide explains how to deploy code changes and infrastructure changes separately.

## Two Types of Deployments

### 1. Code Deployments (Most Common)

When you change application code, you only need to:
- Build and push a new Docker image
- Force Cloud Run to use the new image

**No terraform needed!**

```bash
# From vibe-trade-mcp directory
make deploy
```

This will:
1. Build the Docker image
2. Push it to Artifact Registry
3. Force Cloud Run to create a new revision with the latest image

**Why force-revision?** Cloud Run doesn't automatically pick up new `:latest` images. You need to explicitly tell it to use the new image, which creates a new revision.

### 2. Infrastructure Deployments (Rare)

When you change infrastructure (Cloud Run config, environment variables, resources, etc.), you need terraform:

```bash
# From vibe-trade-terraform directory
terraform plan   # Review changes
terraform apply   # Apply changes
```

**When to use terraform:**
- Changing Cloud Run resource limits (CPU, memory)
- Adding/removing environment variables
- Changing scaling settings
- Updating authentication token
- Any changes to `main.tf`, `variables.tf`, etc.

## Deployment Workflows

### Quick Code Deployment

```bash
cd vibe-trade-mcp
make deploy
```

### Code Deployment with Custom Values

```bash
cd vibe-trade-mcp
# Optionally set environment variables if defaults don't match
export ARTIFACT_REGISTRY_URL="us-central1-docker.pkg.dev/vibe-trade-475704/vibe-trade-mcp"
export SERVICE_NAME="vibe-trade-mcp"
export REGION="us-central1"
export PROJECT_ID="vibe-trade-475704"

make deploy
```

### Infrastructure Deployment

```bash
cd vibe-trade-terraform
terraform plan
terraform apply
```

### Full Deployment (Code + Infrastructure)

If you changed both code and infrastructure:

```bash
# 1. Deploy code
cd vibe-trade-mcp
make deploy

# 2. Deploy infrastructure changes
cd ../vibe-trade-terraform
terraform apply
```

## Getting Service Information

```bash
# From vibe-trade-terraform directory
cd vibe-trade-terraform
terraform output mcp_endpoint
terraform output service_url
terraform output artifact_registry_url
```

## Common Scenarios

### Scenario 1: I just changed Python code
```bash
cd vibe-trade-mcp
make deploy
```
✅ Done! No terraform needed.

### Scenario 2: I changed the MCP_AUTH_TOKEN
```bash
# 1. Update terraform.tfvars
cd vibe-trade-terraform
# Edit terraform.tfvars with new token

# 2. Apply terraform
terraform apply
```
✅ Done! Terraform updates the Cloud Run service with the new token.

### Scenario 3: I changed Cloud Run memory/CPU
```bash
# 1. Update main.tf
cd vibe-trade-terraform
# Edit main.tf resources section

# 2. Apply terraform
terraform plan
terraform apply
```
✅ Done! Terraform updates the Cloud Run service configuration.

### Scenario 4: I changed code AND infrastructure
```bash
# 1. Deploy code first
cd vibe-trade-mcp
make deploy

# 2. Then deploy infrastructure
cd ../vibe-trade-terraform
terraform apply
```
✅ Done! Both are updated.

## Troubleshooting

### Cloud Run not picking up new image?
- Make sure you ran `make force-revision` or `make deploy` (which includes force-revision)
- Check that the image was pushed: `docker images | grep vibe-trade-mcp`
- Verify the image exists in Artifact Registry

### Terraform wants to recreate resources?
- This usually means the state is out of sync
- Run `terraform plan` first to see what it wants to change
- If it's trying to recreate something that exists, you may need to import it

### Getting "image not found" errors?
- Make sure you authenticated Docker: `gcloud auth configure-docker us-central1-docker.pkg.dev`
- Check the Artifact Registry URL matches: `terraform output artifact_registry_url`

