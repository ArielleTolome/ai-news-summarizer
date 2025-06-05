#!/usr/bin/env python3
"""
Simple test without Dagger to verify basic functionality.
"""

import os
import asyncio
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Change to the ai-news-summarizer directory
os.chdir(Path(__file__).parent)

# Add to path
import sys
sys.path.append(str(Path(__file__).parent))


async def test_components():
    """Test individual components."""
    print("🧪 Testing AI News Summarizer Components\n")
    
    # Test 1: RSS Parser
    print("1️⃣ Testing RSS Parser...")
    try:
        from src.scrapers.rss_parser import RSSParser
        
        parser = RSSParser({'timeout': 30})
        feeds = [{
            'url': 'https://techcrunch.com/category/artificial-intelligence/feed/',
            'name': 'TechCrunch AI',
            'max_articles': 2
        }]
        
        articles = await parser.parse_all_feeds(feeds)
        print(f"✅ Parsed {len(articles)} articles")
        if articles:
            print(f"   Latest: {articles[0].title[:60]}...")
    except Exception as e:
        print(f"❌ RSS Parser failed: {e}")
    
    # Test 2: Summarizer
    print("\n2️⃣ Testing AI Summarizer...")
    try:
        from src.summarizers.gpt_summarizer import GPTSummarizer
        
        config = {
            'provider': 'anthropic',
            'model': 'claude-3-opus-20240229',
            'api_key_env': 'ANTHROPIC_API_KEY',
            'temperature': 0.7
        }
        
        summarizer = GPTSummarizer(config)
        
        # Test with a simple article
        test_article = {
            'title': 'AI Test Article',
            'content': 'This is a test article about artificial intelligence advancements in 2024. The field continues to evolve rapidly with new breakthroughs in language models and computer vision.',
            'source_name': 'Test Source',
            'source_url': 'https://example.com',
            'author': 'Test Author'
        }
        
        summary = await summarizer.summarize_article(test_article)
        print(f"✅ Generated summary")
        print(f"   Short: {summary.short_summary[:80]}...")
        print(f"   Tags: {', '.join(summary.tags[:3])}")
    except Exception as e:
        print(f"❌ Summarizer failed: {e}")
    
    # Test 3: Markdown Publisher
    print("\n3️⃣ Testing Markdown Publisher...")
    try:
        from src.publishers.markdown_publisher import MarkdownPublisher
        
        config = {
            'output_dir': './output',
            'template_dir': './templates'
        }
        
        publisher = MarkdownPublisher(config)
        
        # Test newsletter content
        newsletter = {
            'title': 'Test AI News Digest',
            'introduction': 'This is a test newsletter.',
            'top_stories': [{
                'title': 'Test Story',
                'source': 'Test Source',
                'url': 'https://example.com',
                'summary': 'A brief test summary.',
                'key_insights': ['Test insight 1', 'Test insight 2']
            }],
            'trends': ['Test trend'],
            'insights': 'Test insights about the industry.'
        }
        
        articles = [{
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
        
        filepath = publisher.publish_newsletter(newsletter, articles, {'niche': 'AI'})
        print(f"✅ Published newsletter to {filepath}")
    except Exception as e:
        print(f"❌ Publisher failed: {e}")
    
    print("\n✨ Component testing complete!")
    print("\nTo run the full pipeline with Dagger:")
    print("  python test_quick.py")


if __name__ == "__main__":
    asyncio.run(test_components())