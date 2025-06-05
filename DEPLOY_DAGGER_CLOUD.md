# Deploying AI News Summarizer to Dagger Cloud

This guide walks you through deploying the AI News Summarizer to Dagger Cloud for automated, scheduled runs.

## Prerequisites

1. Dagger CLI installed (`./bin/dagger` or globally)
2. Dagger Cloud account ([sign up here](https://dagger.cloud))
3. API keys ready (Anthropic, GitHub if needed)

## Step 1: Login to Dagger Cloud

```bash
# Using local dagger binary
./bin/dagger login

# Or if installed globally
dagger login
```

This will open your browser to authenticate with Dagger Cloud.

## Step 2: Initialize Dagger Module

```bash
cd ai-news-summarizer

# Initialize the module
./bin/dagger init --name=ai-news-summarizer --sdk=python
```

## Step 3: Set Secrets in Dagger Cloud

Set your API keys as secrets in Dagger Cloud:

```bash
# Set Anthropic API key
./bin/dagger secret set anthropic-key --value="your-anthropic-api-key"

# Optional: Set GitHub token for publishing
./bin/dagger secret set github-token --value="your-github-token"

# Optional: Set Twitter API keys
./bin/dagger secret set twitter-keys --value='{"consumer_key":"...","consumer_secret":"..."}'
```

## Step 4: Test the Module Locally

Test individual functions:

```bash
# Test scraping
./bin/dagger call scrape-articles --niche="AI" --max-articles=5

# Test full pipeline (with secrets)
./bin/dagger call run-pipeline \
  --anthropic-key=env:ANTHROPIC_API_KEY \
  --niche="AI" \
  --max-articles=10
```

## Step 5: Deploy to Dagger Cloud

### Option A: Manual Runs

Run the pipeline manually from Dagger Cloud:

```bash
# Deploy the module
./bin/dagger publish

# Run in cloud
./bin/dagger call run-pipeline \
  --anthropic-key=secret:anthropic-key \
  --niche="AI" \
  --max-articles=20 \
  --publish-to-github=true \
  --github-token=secret:github-token
```

### Option B: Scheduled Runs with GitHub Actions

Create `.github/workflows/daily-newsletter.yml`:

```yaml
name: Daily AI Newsletter

on:
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM UTC
  workflow_dispatch:  # Manual trigger

jobs:
  generate-newsletter:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Dagger
        run: |
          cd /usr/local
          curl -L https://dl.dagger.io/dagger/install.sh | sh
          
      - name: Run Newsletter Pipeline
        env:
          DAGGER_CLOUD_TOKEN: ${{ secrets.DAGGER_CLOUD_TOKEN }}
        run: |
          dagger call run-pipeline \
            --anthropic-key=secret:anthropic-key \
            --niche="AI" \
            --max-articles=20 \
            --publish-to-github=true \
            --github-token=secret:github-token
```

### Option C: Dagger Cloud Scheduled Runs

Use Dagger Cloud's built-in scheduling (when available):

```bash
# Configure scheduled run
./bin/dagger call scheduled-run \
  --anthropic-key=secret:anthropic-key \
  --schedule="0 9 * * *" \
  --niche="AI"
```

## Step 6: Monitor Your Pipelines

View pipeline runs in Dagger Cloud:

1. Go to [dagger.cloud](https://dagger.cloud)
2. Navigate to your project
3. View pipeline executions, logs, and metrics

## Advanced Configuration

### Custom Sources

Modify `src/dagger_module.py` to add custom RSS feeds:

```python
feeds = [
    {
        'url': 'https://your-source.com/feed',
        'name': 'Your Source',
        'max_articles': 10
    }
]
```

### Multiple Niches

Run multiple pipelines for different topics:

```bash
# AI Newsletter
./bin/dagger call run-pipeline --niche="AI" --anthropic-key=secret:anthropic-key

# Crypto Newsletter  
./bin/dagger call run-pipeline --niche="Crypto" --anthropic-key=secret:anthropic-key

# Music Newsletter
./bin/dagger call run-pipeline --niche="Music" --anthropic-key=secret:anthropic-key
```

### Custom Templates

Mount custom templates:

```bash
./bin/dagger call generate-newsletter \
  --summaries-json="..." \
  --niche="AI" \
  --template-dir=./custom-templates
```

## Troubleshooting

### Common Issues

1. **Authentication Error**: Run `dagger login` again
2. **Secret Not Found**: Ensure secrets are set with exact names
3. **Pipeline Timeout**: Increase timeout in module configuration
4. **API Rate Limits**: Reduce `max_articles` or add delays

### Debug Mode

Run with verbose output:

```bash
DAGGER_LOG_LEVEL=debug ./bin/dagger call run-pipeline \
  --anthropic-key=secret:anthropic-key \
  --niche="AI"
```

### View Logs

```bash
# Get recent runs
./bin/dagger list

# View specific run logs
./bin/dagger logs <run-id>
```

## Cost Optimization

1. **Cache Results**: Dagger Cloud caches pipeline steps automatically
2. **Limit Articles**: Process only necessary articles with `--max-articles`
3. **Schedule Wisely**: Run during off-peak hours
4. **Use Webhooks**: Trigger only when new content is available

## Security Best Practices

1. **Never commit secrets** to your repository
2. **Use Dagger Cloud secrets** for all sensitive data
3. **Rotate API keys** regularly
4. **Limit secret access** to specific pipelines
5. **Enable audit logs** in Dagger Cloud

## Next Steps

- [ ] Set up monitoring alerts
- [ ] Create custom publishers (Slack, Discord)
- [ ] Add A/B testing for newsletter formats
- [ ] Implement analytics tracking
- [ ] Create web dashboard for results

## Support

- Dagger Documentation: https://docs.dagger.io
- Dagger Discord: https://discord.gg/dagger
- GitHub Issues: https://github.com/yourusername/ai-news-summarizer/issues