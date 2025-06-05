#!/usr/bin/env python3
"""
Quick test script to verify the pipeline works with Dagger.
Loads environment variables from .env file.
"""

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Change to the ai-news-summarizer directory
os.chdir(Path(__file__).parent)

# Import and run
from src.pipeline.news_pipeline import NewsPipeline


async def quick_test():
    """Run a quick test of the pipeline."""
    print("🚀 Running quick test with Dagger...")
    print(f"📍 Working directory: {os.getcwd()}")
    print(f"🔑 API Key loaded: {'ANTHROPIC_API_KEY' in os.environ}")
    
    # Create a test configuration
    test_config = {
        'niche': 'AI',
        'sources': {
            'rss_feeds': [
                {
                    'url': 'https://techcrunch.com/category/artificial-intelligence/feed/',
                    'name': 'TechCrunch AI',
                    'max_articles': 3,
                    'fetch_full_content': False
                }
            ],
            'web_scraping': []  # Disabled for quick test
        },
        'summarization': {
            'api_key_env': 'ANTHROPIC_API_KEY',
            'provider': 'anthropic',
            'model': 'claude-3-opus-20240229',
            'max_articles_per_run': 3,
            'temperature': 0.7
        },
        'publishing': {
            'markdown': {
                'enabled': True,
                'output_dir': './output',
                'template_dir': './templates'
            },
            'twitter': {
                'enabled': False
            },
            'github': {
                'enabled': False
            }
        },
        'rate_limit_delay': 1.0,
        'timeout': 30
    }
    
    # Save test config
    import yaml
    with open('config/test_config.yaml', 'w') as f:
        yaml.dump(test_config, f)
    
    try:
        # Run pipeline
        pipeline = NewsPipeline('config/test_config.yaml')
        metrics = await pipeline.run_pipeline()
        
        print("\n✅ Test completed successfully!")
        print(f"📊 Results:")
        print(f"  - Articles scraped: {metrics.articles_scraped}")
        print(f"  - Articles summarized: {metrics.articles_summarized}")
        print(f"  - Files published: {metrics.articles_published}")
        print(f"  - Duration: {(metrics.end_time - metrics.start_time).total_seconds():.1f}s")
        
        # Check output
        output_dir = Path('./output')
        if output_dir.exists():
            files = list(output_dir.glob('*.md'))
            print(f"\n📄 Generated files:")
            for file in files[:5]:
                print(f"  - {file.name}")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    # Install python-dotenv if not present
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("Installing python-dotenv...")
        import subprocess
        subprocess.check_call(["pip", "install", "python-dotenv"])
        from dotenv import load_dotenv
    
    asyncio.run(quick_test())