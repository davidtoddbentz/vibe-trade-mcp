# Authentication Guide

The Vibe Trade MCP server requires authentication to access. Here's how to authenticate:

## Quick Start

### 1. Get an Identity Token

```bash
# Authenticate with Google Cloud
gcloud auth application-default login

# Get an identity token (valid for 1 hour)
gcloud auth print-identity-token
```

### 2. Use with MCP Clients

The identity token needs to be included in requests. Here are common methods:

#### Option A: Environment Variable (Recommended)

```bash
export MCP_AUTH_TOKEN=$(gcloud auth print-identity-token)
```

Then configure your MCP client to use this token in the `Authorization: Bearer` header.

#### Option B: Direct in Client Configuration

Most MCP clients support authentication headers. Configure your client with:

```
Authorization: Bearer <token>
```

Where `<token>` is the output of `gcloud auth print-identity-token`.

## MCP Client Configuration

### For MCP Clients (e.g., Claude Desktop, Cursor)

When configuring the MCP server in your client, you'll need:

1. **Server URL**: `https://vibe-trade-mcp-kff5sbwvca-uc.a.run.app/mcp`
2. **Authentication**: Use the identity token in the Authorization header

Example configuration format (varies by client):

```json
{
  "mcpServers": {
    "vibe-trade": {
      "url": "https://vibe-trade-mcp-kff5sbwvca-uc.a.run.app/mcp",
      "headers": {
        "Authorization": "Bearer <your-identity-token>"
      }
    }
  }
}
```

**Note**: Identity tokens expire after 1 hour. You may need to refresh them periodically.

## Service Account Authentication (For Production)

For automated/production use, create a service account:

```bash
# Create service account
gcloud iam service-accounts create vibe-trade-mcp-client \
  --display-name="Vibe Trade MCP Client"

# Grant access to the Cloud Run service
gcloud run services add-iam-policy-binding vibe-trade-mcp \
  --region=us-central1 \
  --member="serviceAccount:vibe-trade-mcp-client@vibe-trade-475704.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

# Get token for service account
gcloud auth activate-service-account \
  vibe-trade-mcp-client@vibe-trade-475704.iam.gserviceaccount.com \
  --key-file=path/to/key.json

gcloud auth print-identity-token
```

## Testing Authentication

Test that authentication works:

```bash
# Get token
TOKEN=$(gcloud auth print-identity-token)

# Test endpoint (should get MCP protocol response, not 403)
curl -H "Authorization: Bearer $TOKEN" \
     -H "Accept: text/event-stream" \
     https://vibe-trade-mcp-kff5sbwvca-uc.a.run.app/mcp
```

If you get a 403 Forbidden, check:
1. Your email is in `terraform.tfvars` `allowed_invokers`
2. Terraform has been applied: `make terraform-apply-auto`
3. You're using the correct identity token

## Adding More Users

To grant access to additional users:

1. Edit `terraform/terraform.tfvars`:
   ```hcl
   allowed_invokers = [
     "user:user1@gmail.com",
     "user:user2@gmail.com",
   ]
   ```

2. Apply changes:
   ```bash
   make terraform-apply-auto
   ```

## Troubleshooting

### "403 Forbidden"
- Your email is not in `allowed_invokers`
- Token has expired (get a new one with `gcloud auth print-identity-token`)
- Wrong token being used

### "401 Unauthorized"
- Token is missing or malformed
- Check that `Authorization: Bearer <token>` header is set correctly

### Token Expiration
Identity tokens expire after 1 hour. For long-running clients, consider:
- Using a service account with a longer-lived token
- Implementing token refresh logic in your client
- Using OAuth2 flow for user authentication

