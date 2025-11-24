# Deploying to Google Cloud Run

This guide shows how to deploy your MCP server to Google Cloud Run so agents can connect remotely.

## Prerequisites

1. Google Cloud account with billing enabled
2. `gcloud` CLI installed and authenticated
3. Docker installed (for local testing)

## Quick Deploy

### Option 1: Using gcloud (Recommended)

```bash
# Build and deploy in one command
gcloud run deploy vibe-trade-mcp \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080
```

### Option 2: Using Docker

```bash
# Build the image
docker build -t vibe-trade-mcp .

# Test locally
docker run -p 8080:8080 vibe-trade-mcp

# Tag for GCR
docker tag vibe-trade-mcp gcr.io/YOUR_PROJECT_ID/vibe-trade-mcp

# Push to GCR
docker push gcr.io/YOUR_PROJECT_ID/vibe-trade-mcp

# Deploy to Cloud Run
gcloud run deploy vibe-trade-mcp \
  --image gcr.io/YOUR_PROJECT_ID/vibe-trade-mcp \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080
```

## Configuration

### Environment Variables

Set environment variables in Cloud Run:

```bash
gcloud run services update vibe-trade-mcp \
  --set-env-vars "ENV_VAR_NAME=value" \
  --region us-central1
```

### Port Configuration

Cloud Run automatically sets the `PORT` environment variable. The server reads this and binds to the correct port.

## Connecting Agents

Once deployed, agents can connect via HTTP using the MCP client library. The server exposes tools at the `/mcp` endpoint.

Your Cloud Run service URL will be: `https://vibe-trade-mcp-xxxxx.run.app/mcp`

## Testing Deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe vibe-trade-mcp \
  --region us-central1 \
  --format 'value(status.url)')

# Test the endpoint
curl $SERVICE_URL/mcp
```

## Monitoring

View logs:
```bash
gcloud run services logs read vibe-trade-mcp --region us-central1
```

## Cost Optimization

- Set min instances to 0 for cost savings
- Use Cloud Run's automatic scaling
- Monitor usage in Cloud Console

