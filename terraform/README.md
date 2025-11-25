# Terraform Infrastructure

This directory contains Terraform configuration for deploying the Vibe Trade MCP server to Google Cloud Run.

## Security Model

**By default, the Cloud Run service requires authentication** - it's not publicly accessible. Access is controlled via IAM:

- No public access (`--no-allow-unauthenticated`)
- Only users/service accounts in `allowed_invokers` can invoke the service
- Easy to add/remove access by updating the list

## Prerequisites

1. **GCP Project**: `vibe-trade-475704` (already created with billing enabled)
2. **gcloud CLI**: Authenticated and configured
3. **Terraform**: Installed locally

```bash
# Install Terraform (macOS)
brew install terraform

# Authenticate with GCP
gcloud auth application-default login
gcloud config set project vibe-trade-475704
```

## Setup

1. **Copy the example variables file:**
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

2. **Edit `terraform.tfvars`** and add your email to `allowed_invokers`:
   ```hcl
   allowed_invokers = [
     "user:your-email@gmail.com",
   ]
   ```

3. **Initialize Terraform:**
   ```bash
   cd terraform
   terraform init
   ```

4. **Review the plan:**
   ```bash
   terraform plan
   ```

5. **Apply the infrastructure:**
   ```bash
   terraform apply
   ```
   
   **Note**: The Cloud Run service will be created but won't be ready until you build and push the Docker image (see "Building and Deploying" below).

## What Gets Created

- **Artifact Registry**: Docker repository for container images
- **Service Account**: For the Cloud Run service to run as
- **Cloud Run Service**: The MCP server (scales to 0, max 10 instances)
- **IAM Bindings**: Access control (only `allowed_invokers` can access)

## Building and Deploying

After infrastructure is created, build and push the Docker image:

```bash
# Get the Artifact Registry URL from terraform output
cd terraform
terraform output artifact_registry_url

# Authenticate Docker with Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build and push the image (from project root)
cd ..
gcloud builds submit --tag us-central1-docker.pkg.dev/vibe-trade-475704/vibe-trade-mcp/vibe-trade-mcp:latest

# Or use Docker directly:
docker build -t us-central1-docker.pkg.dev/vibe-trade-475704/vibe-trade-mcp/vibe-trade-mcp:latest .
docker push us-central1-docker.pkg.dev/vibe-trade-475704/vibe-trade-mcp/vibe-trade-mcp:latest
```

## Accessing the Service

Once deployed, get the service URL:

```bash
terraform output mcp_endpoint
```

To invoke the service, you need to authenticate and use the correct headers:

```bash
# Get an identity token
gcloud auth print-identity-token

# Use it in requests (MCP uses Server-Sent Events)
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
     -H "Accept: text/event-stream" \
     https://vibe-trade-mcp-xxxxx.run.app/mcp
```

**Note**: The MCP endpoint uses Server-Sent Events (SSE), so you must include `Accept: text/event-stream` header. For actual MCP client connections, use an MCP client library that handles SSE properly.

## Adding More Users

To grant access to additional users or service accounts:

1. Edit `terraform.tfvars`:
   ```hcl
   allowed_invokers = [
     "user:user1@gmail.com",
     "user:user2@gmail.com",
     "serviceAccount:sa@project.iam.gserviceaccount.com",
   ]
   ```

2. Apply the changes:
   ```bash
   terraform apply
   ```

## Outputs

```bash
# Get all outputs
terraform output

# Get specific output
terraform output mcp_endpoint
terraform output service_url
```

## Destroying

To tear down all infrastructure:

```bash
terraform destroy
```

**Note**: This will delete the Cloud Run service, Artifact Registry, and all associated resources.

