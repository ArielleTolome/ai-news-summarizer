#!/usr/bin/env python3
"""
Demo script showing the AI News Summarizer in action without Dagger.
This demonstrates the core functionality directly.
"""

import os
import asyncio
from pathlib import Path
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Change to the ai-news-summarizer directory
os.chdir(Path(__file__).parent)

# Add to path
import sys
sys.path.append(str(Path(__file__).parent))

from src.scrapers import RSSParser
from src.summarizers import GPTSummarizer
from src.publishers import MarkdownPublisher


async def demo_pipeline():
    """Run a demo of the AI News Summarizer pipeline."""
    print("🚀 AI News Summarizer Demo\n")
    print("This demo will:")
    print("1. Fetch latest AI news from RSS feeds")
    print("2. Summarize articles using Claude AI")
    print("3. Generate a beautiful markdown newsletter\n")
    
    # Step 1: Fetch articles
    print("📰 Step 1: Fetching latest AI news...")
    
    rss_config = {'timeout': 30}
    parser = RSSParser(rss_config)
    
    feeds = [
        {
            'url': 'https://techcrunch.com/category/artificial-intelligence/feed/',
            'name': 'TechCrunch AI',
            'max_articles': 5
        },
        {
            'url': 'https://www.technologyreview.com/feed/',
            'name': 'MIT Technology Review',
            'max_articles': 3
        }
    ]
    
    articles = await parser.parse_all_feeds(feeds)
    print(f"✅ Fetched {len(articles)} articles\n")
    
    # Show article titles
    print("📋 Articles found:")
    for i, article in enumerate(articles[:5], 1):
        print(f"{i}. {article.title[:70]}...")
    print()
    
    # Step 2: Summarize articles
    print("🤖 Step 2: Summarizing articles with Claude AI...")
    
    summarizer_config = {
        'provider': 'anthropic',
        'model': 'claude-3-opus-20240229',
        'api_key_env': 'ANTHROPIC_API_KEY',
        'temperature': 0.7
    }
    
    summarizer = GPTSummarizer(summarizer_config)
    
    # Convert articles to dicts
    article_dicts = [article.to_dict() for article in articles[:5]]
    
    # Summarize articles
    summaries = await summarizer.process_articles(article_dicts)
    print(f"✅ Generated {len(summaries)} summaries\n")
    
    # Step 3: Generate newsletter
    print("📝 Step 3: Generating newsletter content...")
    
    # Create newsletter content
    newsletter_content = await summarizer.create_newsletter_content(
        summaries, 
        niche='AI'
    )
    
    # Step 4: Publish newsletter
    print("📤 Step 4: Publishing newsletter...")
    
    publisher_config = {
        'output_dir': './output',
        'template_dir': './templates'
    }
    
    publisher = MarkdownPublisher(publisher_config)
    
    # Prepare article data for publishing
    all_articles_data = [
        {
            'article': article,
            'summary': summary.to_dict()
        }
        for article, summary in summaries
    ]
    
    # Publish newsletter
    metadata = {
        'niche': 'AI', 
        'sources_count': len(feeds), 
        'top_sources': ['TechCrunch', 'VentureBeat'],
        'top_tags': ['AI', 'Technology', 'Machine Learning', 'Innovation', 'Startups'],
        'issue_number': 1,
        'frequency': 'daily',
        'publish_time': '9:00 AM'
    }
    
    filepath = publisher.publish_newsletter(
        newsletter_content.to_dict(),
        all_articles_data,
        metadata
    )
    
    print(f"✅ Newsletter published to: {filepath}\n")
    
    # Show summary
    print("📊 Summary:")
    print(f"- Articles fetched: {len(articles)}")
    print(f"- Articles summarized: {len(summaries)}")
    print(f"- Newsletter title: {newsletter_content.title}")
    print(f"- Top trends: {', '.join(newsletter_content.trends[:3])}")
    print(f"\n✨ Demo complete! Check the output directory for your newsletter.")
    
    return filepath


async def show_sample_output(filepath: str):
    """Show a sample of the generated newsletter."""
    if Path(filepath).exists():
        print("\n📄 Sample of generated newsletter:")
        print("=" * 70)
        
        with open(filepath, 'r') as f:
            lines = f.readlines()[:30]  # First 30 lines
            print(''.join(lines))
        
        print("=" * 70)
        print(f"\n📖 Full newsletter available at: {filepath}")


if __name__ == "__main__":
    try:
        filepath = asyncio.run(demo_pipeline())
        asyncio.run(show_sample_output(filepath))
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        print("\nMake sure you have:")
        print("1. Set ANTHROPIC_API_KEY in .env file")
        print("2. Installed all requirements: pip install -r requirements.txt")
        print("3. Have internet connection for fetching news")