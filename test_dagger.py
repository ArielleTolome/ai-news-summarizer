#!/usr/bin/env python3
"""
Test script for running the AI News Summarizer with Dagger.
This demonstrates the containerized pipeline execution.
"""

import asyncio
import os
import sys
from pathlib import Path

import dagger

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))


async def test_scraper_module():
    """Test the scraper module in a Dagger container."""
    print("🧪 Testing Scraper Module...")
    
    async with dagger.connect() as client:
        # Create container with scraper dependencies
        container = (
            client.container()
            .from_("python:3.11-slim")
            .with_exec(["apt-get", "update", "-qq"])
            .with_exec(["apt-get", "install", "-y", "-qq", "git"])
            .with_exec(["pip", "install", "-q", "httpx", "beautifulsoup4", "lxml", 
                       "feedparser", "python-dateutil", "tenacity"])
        )
        
        # Mount source code
        src_dir = client.host().directory("./src", exclude=["**/__pycache__"])
        container = container.with_directory("/app/src", src_dir)
        container = container.with_workdir("/app")
        
        # Test RSS parsing
        test_script = """
import asyncio
from src.scrapers.rss_parser import RSSParser

async def test():
    parser = RSSParser({'timeout': 30})
    # Test with a reliable RSS feed
    feeds = [{
        'url': 'https://feeds.bbci.co.uk/news/technology/rss.xml',
        'name': 'BBC Technology',
        'max_articles': 3
    }]
    articles = await parser.parse_all_feeds(feeds)
    print(f"✅ Parsed {len(articles)} articles from RSS feeds")
    for article in articles[:2]:
        print(f"  - {article.title[:60]}...")
    return len(articles) > 0

asyncio.run(test())
"""
        
        # Run test
        result = await container.with_exec(["python", "-c", test_script]).sync()
        
        if result:
            print("✅ Scraper module test passed!\n")
        else:
            print("❌ Scraper module test failed!\n")


async def test_summarizer_module():
    """Test the summarizer module with Claude API."""
    print("🧪 Testing Summarizer Module...")
    
    # Ensure API key is set
    if 'ANTHROPIC_API_KEY' not in os.environ:
        print("⚠️  ANTHROPIC_API_KEY not found in environment")
        print("Please set it in your .env file or environment")
        return
    
    async with dagger.connect() as client:
        # Create container with AI dependencies
        container = (
            client.container()
            .from_("python:3.11-slim")
            .with_exec(["pip", "install", "-q", "anthropic", "tiktoken", "tenacity"])
            .with_env_variable("ANTHROPIC_API_KEY", os.environ['ANTHROPIC_API_KEY'])
        )
        
        # Mount source code
        src_dir = client.host().directory("./src", exclude=["**/__pycache__"])
        container = container.with_directory("/app/src", src_dir)
        container = container.with_workdir("/app")
        
        # Test summarization
        test_script = """
import asyncio
from src.summarizers.gpt_summarizer import GPTSummarizer

async def test():
    config = {
        'provider': 'anthropic',
        'model': 'claude-3-opus-20240229',
        'api_key_env': 'ANTHROPIC_API_KEY'
    }
    
    summarizer = GPTSummarizer(config)
    
    # Test article
    article = {
        'title': 'Test Article: AI Advances in 2024',
        'content': 'Artificial intelligence continues to make significant strides in 2024. Recent developments in large language models have shown improvements in reasoning capabilities and reduced hallucinations. This is a test article for the summarizer.',
        'source_name': 'Test Source',
        'source_url': 'https://example.com/test',
        'author': 'Test Author'
    }
    
    try:
        summary = await summarizer.summarize_article(article)
        print("✅ Successfully generated summary:")
        print(f"  Short: {summary.short_summary[:100]}...")
        print(f"  Tags: {', '.join(summary.tags[:3])}")
        return True
    except Exception as e:
        print(f"❌ Summarization failed: {e}")
        return False

asyncio.run(test())
"""
        
        # Run test
        result = await container.with_exec(["python", "-c", test_script]).sync()
        
        if result:
            print("✅ Summarizer module test passed!\n")
        else:
            print("❌ Summarizer module test failed!\n")


async def test_publisher_module():
    """Test the publisher module."""
    print("🧪 Testing Publisher Module...")
    
    async with dagger.connect() as client:
        # Create container with publishing dependencies
        container = (
            client.container()
            .from_("python:3.11-slim")
            .with_exec(["pip", "install", "-q", "jinja2"])
        )
        
        # Mount source code and templates
        src_dir = client.host().directory("./src", exclude=["**/__pycache__"])
        container = container.with_directory("/app/src", src_dir)
        
        templates_dir = client.host().directory("./templates")
        container = container.with_directory("/app/templates", templates_dir)
        
        container = container.with_workdir("/app")
        
        # Test markdown publishing
        test_script = """
from src.publishers.markdown_publisher import MarkdownPublisher
import os

# Create output directory
os.makedirs('/app/output', exist_ok=True)

config = {
    'output_dir': '/app/output',
    'template_dir': '/app/templates'
}

publisher = MarkdownPublisher(config)

# Test data
newsletter_content = {
    'title': 'Test AI News Digest',
    'introduction': 'This is a test newsletter',
    'top_stories': [{
        'title': 'Test Story',
        'source': 'Test Source',
        'url': 'https://example.com',
        'summary': 'Test summary',
        'key_insights': ['Insight 1', 'Insight 2']
    }],
    'trends': ['Test Trend 1'],
    'insights': 'Test insights about the industry.'
}

all_articles = [{
    'article': {
        'title': 'Test Article',
        'source_name': 'Test Source',
        'source_url': 'https://example.com',
        'date': '2024-06-04'
    },
    'summary': {
        'short_summary': 'Brief test summary',
        'key_insights': ['Test insight'],
        'tags': ['AI', 'Test']
    }
}]

try:
    filepath = publisher.publish_newsletter(newsletter_content, all_articles, {'niche': 'AI'})
    print(f"✅ Successfully published newsletter")
    # Check if file exists
    if os.path.exists(filepath):
        print(f"  File created at: {filepath}")
        print(f"  File size: {os.path.getsize(filepath)} bytes")
except Exception as e:
    print(f"❌ Publishing failed: {e}")
"""
        
        # Run test
        result = await container.with_exec(["python", "-c", test_script]).sync()
        
        if result:
            print("✅ Publisher module test passed!\n")
        else:
            print("❌ Publisher module test failed!\n")


async def test_full_pipeline():
    """Test the full pipeline with minimal data."""
    print("🧪 Testing Full Pipeline...")
    
    # Ensure API key is set
    if 'ANTHROPIC_API_KEY' not in os.environ:
        print("⚠️  ANTHROPIC_API_KEY not found in environment")
        print("Please set it in your .env file or environment")
        return
    
    async with dagger.connect() as client:
        # Create container with all dependencies
        container = (
            client.container()
            .from_("python:3.11-slim")
            .with_exec(["apt-get", "update", "-qq"])
            .with_exec(["apt-get", "install", "-y", "-qq", "git"])
            .with_exec(["pip", "install", "-q"] + [
                "httpx", "beautifulsoup4", "lxml", "feedparser", "python-dateutil",
                "anthropic", "tiktoken", "tenacity", "jinja2", "pyyaml", "cachetools"
            ])
            .with_env_variable("ANTHROPIC_API_KEY", os.environ['ANTHROPIC_API_KEY'])
        )
        
        # Mount all necessary directories
        src_dir = client.host().directory("./src", exclude=["**/__pycache__"])
        config_dir = client.host().directory("./config")
        templates_dir = client.host().directory("./templates")
        
        container = (
            container
            .with_directory("/app/src", src_dir)
            .with_directory("/app/config", config_dir)
            .with_directory("/app/templates", templates_dir)
            .with_workdir("/app")
        )
        
        # Create necessary directories
        container = container.with_exec(["mkdir", "-p", "/app/output", "/app/cache", "/app/metrics"])
        
        # Run minimal pipeline test
        test_script = """
import asyncio
import sys
sys.path.append('/app')

from src.pipeline.news_pipeline import NewsPipeline

async def test():
    # Create test config
    import yaml
    test_config = {
        'niche': 'AI',
        'sources': {
            'rss_feeds': [{
                'url': 'https://feeds.bbci.co.uk/news/technology/rss.xml',
                'name': 'BBC Tech',
                'max_articles': 2
            }]
        },
        'summarization': {
            'provider': 'anthropic',
            'model': 'claude-3-opus-20240229',
            'api_key_env': 'ANTHROPIC_API_KEY',
            'max_articles_per_run': 2
        },
        'publishing': {
            'markdown': {
                'enabled': True,
                'output_dir': '/app/output'
            },
            'twitter': {'enabled': False},
            'github': {'enabled': False}
        }
    }
    
    # Write test config
    with open('/app/config/test_config.yaml', 'w') as f:
        yaml.dump(test_config, f)
    
    # Run pipeline
    pipeline = NewsPipeline('/app/config/test_config.yaml')
    metrics = await pipeline.run_pipeline()
    
    print(f"✅ Pipeline completed!")
    print(f"  Articles scraped: {metrics.articles_scraped}")
    print(f"  Articles summarized: {metrics.articles_summarized}")
    print(f"  Articles published: {metrics.articles_published}")
    
    return metrics.articles_published > 0

try:
    result = asyncio.run(test())
    if not result:
        sys.exit(1)
except Exception as e:
    print(f"❌ Pipeline test failed: {e}")
    sys.exit(1)
"""
        
        # Run test
        result = await container.with_exec(["python", "-c", test_script]).sync()
        
        if result:
            print("✅ Full pipeline test passed!\n")
        else:
            print("❌ Full pipeline test failed!\n")


async def main():
    """Run all Dagger tests."""
    print("🚀 AI News Summarizer - Dagger Test Suite\n")
    print("This will test each module in isolated containers using Dagger.\n")
    
    # Test each module
    await test_scraper_module()
    await test_summarizer_module()
    await test_publisher_module()
    await test_full_pipeline()
    
    print("\n✨ All Dagger tests completed!")
    print("\nTo run the actual pipeline with Dagger:")
    print("  python run.py")
    print("\nTo run in preview mode:")
    print("  python run.py --preview")


if __name__ == "__main__":
    # Check if we're in the right directory
    if not Path("ai-news-summarizer").exists():
        print("❌ Please run this script from the parent directory of ai-news-summarizer")
        sys.exit(1)
    
    os.chdir("ai-news-summarizer")
    asyncio.run(main())