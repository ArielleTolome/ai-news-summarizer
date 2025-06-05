#!/usr/bin/env python3
"""
Simple runner script for the AI News Summarizer pipeline.
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.pipeline.news_pipeline import NewsPipeline


async def main():
    parser = argparse.ArgumentParser(
        description='AI News Summarizer - Automated news digest generation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run once with default config
  python run.py
  
  # Run in preview mode (no publishing)
  python run.py --preview
  
  # Run with custom config
  python run.py --config myconfig.yaml
  
  # Run on schedule
  python run.py --scheduled
  
  # Change niche
  python run.py --niche crypto
        """
    )
    
    parser.add_argument(
        '--config', 
        default='config/config.yaml',
        help='Path to configuration file (default: config/config.yaml)'
    )
    
    parser.add_argument(
        '--scheduled',
        action='store_true',
        help='Run on schedule defined in config'
    )
    
    parser.add_argument(
        '--preview',
        action='store_true',
        help='Preview mode - disable publishing'
    )
    
    parser.add_argument(
        '--niche',
        help='Override niche in config (e.g., AI, crypto, music)'
    )
    
    parser.add_argument(
        '--max-articles',
        type=int,
        help='Override maximum articles to process'
    )
    
    parser.add_argument(
        '--sources',
        nargs='+',
        choices=['rss', 'web', 'all'],
        default=['all'],
        help='Which sources to use (default: all)'
    )
    
    args = parser.parse_args()
    
    # Create pipeline
    pipeline = NewsPipeline(args.config)
    
    # Override configuration based on arguments
    if args.preview:
        print("🔍 Running in preview mode - publishing disabled")
        pipeline.config['publishing']['twitter']['enabled'] = False
        pipeline.config['publishing']['github']['enabled'] = False
    
    if args.niche:
        print(f"📰 Using niche: {args.niche}")
        pipeline.config['niche'] = args.niche
    
    if args.max_articles:
        print(f"📊 Processing maximum {args.max_articles} articles")
        pipeline.config['summarization']['max_articles_per_run'] = args.max_articles
    
    if 'all' not in args.sources:
        if 'rss' not in args.sources:
            pipeline.config['sources']['rss_feeds'] = []
        if 'web' not in args.sources:
            pipeline.config['sources']['web_scraping'] = []
    
    # Run pipeline
    try:
        if args.scheduled:
            print("⏰ Starting scheduled pipeline...")
            await pipeline.run_scheduled()
        else:
            print("🚀 Running pipeline...")
            metrics = await pipeline.run_pipeline()
            
            # Print summary
            print("\n✅ Pipeline completed!")
            print(f"📈 Articles scraped: {metrics.articles_scraped}")
            print(f"📝 Articles summarized: {metrics.articles_summarized}")
            print(f"📤 Files published: {metrics.articles_published}")
            print(f"⏱️  Duration: {(metrics.end_time - metrics.start_time).total_seconds():.1f}s")
            
            if metrics.errors:
                print(f"\n⚠️  Errors encountered:")
                for error in metrics.errors:
                    print(f"  - {error}")
    
    except KeyboardInterrupt:
        print("\n⛔ Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())