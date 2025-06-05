#!/bin/bash

# AI News Summarizer - Dagger Cloud Deployment Script

set -e

echo "🚀 AI News Summarizer - Dagger Cloud Deployment"
echo "=============================================="

# Check if dagger is available
if command -v dagger &> /dev/null; then
    DAGGER_CMD="dagger"
elif [ -f "./bin/dagger" ]; then
    DAGGER_CMD="./bin/dagger"
else
    echo "❌ Dagger CLI not found. Please install it first."
    echo "Run: curl -L https://dl.dagger.io/dagger/install.sh | sh"
    exit 1
fi

echo "✅ Using Dagger: $DAGGER_CMD"

# Step 1: Login to Dagger Cloud
echo ""
echo "📝 Step 1: Logging into Dagger Cloud..."
echo "This will open your browser for authentication."
read -p "Press Enter to continue..."

$DAGGER_CMD login

# Step 2: Set up secrets
echo ""
echo "🔐 Step 2: Setting up secrets..."
echo "Your Anthropic API key will be stored securely in Dagger Cloud."

# Check if ANTHROPIC_API_KEY exists in environment
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ANTHROPIC_API_KEY not found in environment."
    echo "Reading from .env file..."
    if [ -f ".env" ]; then
        export $(grep ANTHROPIC_API_KEY .env | xargs)
    fi
fi

if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "Setting Anthropic API key as secret..."
    $DAGGER_CMD secret set anthropic-key --value="$ANTHROPIC_API_KEY"
    echo "✅ Anthropic key set successfully"
else
    echo "⚠️  No ANTHROPIC_API_KEY found. You'll need to set it manually:"
    echo "   $DAGGER_CMD secret set anthropic-key --value='your-key'"
fi

# Optional: GitHub token
if [ -n "$GITHUB_TOKEN" ]; then
    echo "Setting GitHub token as secret..."
    $DAGGER_CMD secret set github-token --value="$GITHUB_TOKEN"
    echo "✅ GitHub token set successfully"
fi

# Step 3: Test the pipeline
echo ""
echo "🧪 Step 3: Testing the pipeline..."
read -p "Run a test with 3 articles? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running test pipeline..."
    $DAGGER_CMD call scrape-articles --niche="AI" --max-articles=3
fi

# Step 4: Deploy
echo ""
echo "🚀 Step 4: Publishing to Dagger Cloud..."
$DAGGER_CMD publish

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Run manually:"
echo "   $DAGGER_CMD call run-pipeline --anthropic-key=secret:anthropic-key --niche='AI'"
echo ""
echo "2. View in Dagger Cloud:"
echo "   https://dagger.cloud"
echo ""
echo "3. Set up scheduled runs:"
echo "   - Use GitHub Actions (see .github/workflows/daily-newsletter.yml)"
echo "   - Or wait for Dagger Cloud scheduling feature"
echo ""
echo "🎉 Your AI News Summarizer is ready in Dagger Cloud!"