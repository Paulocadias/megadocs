# Deployment Guide - Google Cloud Run

## Overview

MegaDoc is designed for serverless deployment on Google Cloud Run, providing auto-scaling, zero-downtime deployments, and cost-effective hosting.

## Prerequisites

- Google Cloud Platform account
- `gcloud` CLI installed and configured
- Docker installed locally
- Project with billing enabled

## Quick Start

### 1. Build and Push Docker Image

```bash
# Set your project ID
export PROJECT_ID=your-gcp-project-id
export SERVICE_NAME=megadoc
export REGION=us-central1

# Build the Docker image
docker build -t gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest .

# Push to Google Container Registry
docker push gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest
```

### 2. Deploy to Cloud Run

```bash
# Deploy the service
gcloud run deploy ${SERVICE_NAME} \
  --image gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --set-env-vars "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  --set-env-vars "OPENROUTER_API_KEY=your_key_here"
```

### 3. Using Cloud Build (Recommended)

Create `cloudbuild.yaml` in your project root:

```yaml
steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/megadoc:$SHORT_SHA', '.']
  
  # Push the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/megadoc:$SHORT_SHA']
  
  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'megadoc'
      - '--image'
      - 'gcr.io/$PROJECT_ID/megadoc:$SHORT_SHA'
      - '--region'
      - 'us-central1'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'
      - '--memory'
      - '2Gi'
      - '--cpu'
      - '2'
      - '--timeout'
      - '300'
      - '--max-instances'
      - '10'

images:
  - 'gcr.io/$PROJECT_ID/megadoc:$SHORT_SHA'
```

Deploy with:

```bash
gcloud builds submit --config cloudbuild.yaml
```

## Environment Variables

Set via Cloud Run console or CLI:

```bash
gcloud run services update megadoc \
  --update-env-vars "SECRET_KEY=your_secret_key,OPENROUTER_API_KEY=your_key"
```

**Required:**
- `SECRET_KEY` - Flask secret key (generate with `secrets.token_hex(32)`)

**Optional:**
- `OPENROUTER_API_KEY` - For chat features
- `OPENROUTER_HTTP_REFERER` - Your domain URL
- `MAX_FILE_SIZE` - Max file size in bytes (default: 52428800 = 50MB)
- `RATE_LIMIT_REQUESTS` - Requests per window (default: 20)
- `RATE_LIMIT_WINDOW` - Time window in seconds (default: 60)

## Custom Domain

### 1. Map Custom Domain

```bash
gcloud run domain-mappings create \
  --service megadoc \
  --domain megadocs.paulocadias.com \
  --region us-central1
```

### 2. Update DNS

Add the CNAME record provided by Cloud Run to your DNS provider.

## Monitoring & Logging

### View Logs

```bash
# Stream logs
gcloud run services logs read megadoc --region us-central1 --follow

# View recent logs
gcloud run services logs read megadoc --region us-central1 --limit 50
```

### Metrics

- **CPU Utilization**: Monitor in Cloud Console
- **Request Count**: Track in Cloud Run metrics
- **Error Rate**: Set up alerts for 5xx errors
- **Latency**: P50, P95, P99 percentiles

## Scaling Configuration

### Auto-scaling

Cloud Run automatically scales based on:
- Request rate
- CPU utilization
- Memory usage

### Limits

```bash
# Set min/max instances
gcloud run services update megadoc \
  --min-instances 0 \
  --max-instances 10 \
  --concurrency 80 \
  --cpu 2 \
  --memory 2Gi
```

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - id: 'auth'
        uses: 'google-github-actions/auth@v1'
        with:
          credentials_json: '${{ secrets.GCP_SA_KEY }}'
      
      - name: 'Set up Cloud SDK'
        uses: 'google-github-actions/setup-gcloud@v1'
      
      - name: 'Build and Deploy'
        run: |
          gcloud builds submit --config cloudbuild.yaml
```

## Troubleshooting

### Service Won't Start

1. Check logs: `gcloud run services logs read megadoc`
2. Verify environment variables are set
3. Check Dockerfile builds successfully locally

### High Latency

1. Increase CPU allocation: `--cpu 2` or `--cpu 4`
2. Increase memory: `--memory 4Gi`
3. Check for cold starts (use min-instances)

### Out of Memory

1. Increase memory limit: `--memory 4Gi`
2. Check for memory leaks in application
3. Review file size limits

### 429 Rate Limits

1. Increase `RATE_LIMIT_REQUESTS` in environment
2. Adjust `RATE_LIMIT_WINDOW` if needed
3. Consider increasing max instances

## Cost Optimization

### Free Tier

- **2 million requests/month** free
- **400,000 GB-seconds** compute time
- **200,000 GiB-seconds** memory

### Cost Estimates

- **Low traffic** (< 1M requests/month): Free tier
- **Medium traffic** (1-10M requests/month): ~$10-50/month
- **High traffic** (> 10M requests/month): ~$50-200/month

### Tips

1. Use min-instances=0 for cost savings
2. Optimize Docker image size
3. Use Cloud CDN for static assets
4. Monitor and set budget alerts

## Security Best Practices

1. **Secrets Management**: Use Secret Manager for API keys
2. **HTTPS Only**: Cloud Run enforces HTTPS
3. **IAM**: Use service accounts with minimal permissions
4. **VPC**: Connect to VPC for private resources if needed
5. **CORS**: Configure CORS headers appropriately

## Updating the Service

```bash
# Rebuild and redeploy
gcloud builds submit --config cloudbuild.yaml

# Or update environment variables only
gcloud run services update megadoc \
  --update-env-vars "NEW_VAR=value"
```

## Rollback

```bash
# List revisions
gcloud run revisions list --service megadoc

# Rollback to previous revision
gcloud run services update-traffic megadoc \
  --to-revisions PREVIOUS_REVISION=100
```
