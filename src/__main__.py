"""
Dagger module for AI News Summarizer
"""

import dagger
from dagger import dag, function, object_type


@object_type
class AiNewsSummarizer:
    """AI News Summarizer Dagger Module"""
    
    @function
    async def hello(self, name: str = "World") -> str:
        """Simple hello function to test the module"""
        return f"Hello {name} from AI News Summarizer!"
    
    @function
    async def build_base(self) -> dagger.Container:
        """Build the base container with dependencies"""
        return (
            dag.container()
            .from_("python:3.11-slim")
            .with_exec(["apt-get", "update", "-qq"])
            .with_exec(["apt-get", "install", "-y", "-qq", "git", "curl"])
            .with_exec(["pip", "install", "--no-cache-dir", 
                       "httpx", "beautifulsoup4", "lxml", "feedparser",
                       "python-dateutil", "anthropic", "tiktoken", 
                       "tenacity", "jinja2", "pyyaml", "cachetools"])
        )
    
    @function
    async def test_scraper(self) -> str:
        """Test the RSS scraper functionality"""
        container = await self.build_base()
        
        # Add source code
        container = container.with_directory(
            "/app", 
            dag.current_module().source().directory("..")
        ).with_workdir("/app")
        
        # Run test
        return await (
            container
            .with_exec([
                "python", "-c",
                """
import asyncio
import sys
sys.path.append('/app')

from src.scrapers.rss_parser import RSSParser

async def test():
    parser = RSSParser({'timeout': 30})
    feeds = [{
        'url': 'https://techcrunch.com/category/artificial-intelligence/feed/',
        'name': 'TechCrunch AI',
        'max_articles': 3
    }]
    
    articles = await parser.parse_all_feeds(feeds)
    print(f"Successfully parsed {len(articles)} articles!")
    for i, article in enumerate(articles[:2], 1):
        print(f"{i}. {article.title[:60]}...")
    return True

asyncio.run(test())
"""
            ])
            .stdout()
        )
    
    @function  
    async def run_demo(self, anthropic_key: dagger.Secret) -> str:
        """Run a demo of the complete pipeline"""
        container = await self.build_base()
        
        # Add source and environment
        container = (
            container
            .with_directory("/app", dag.current_module().source().directory(".."))
            .with_workdir("/app")
            .with_secret_variable("ANTHROPIC_API_KEY", anthropic_key)
            .with_exec(["mkdir", "-p", "output", "cache"])
        )
        
        # Run demo
        return await (
            container
            .with_exec(["python", "test_demo.py"])
            .stdout()
        )