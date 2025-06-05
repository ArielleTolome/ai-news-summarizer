import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json
import hashlib
from dataclasses import dataclass, asdict

import dagger
import yaml
from cachetools import TTLCache

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.scrapers import WebScraper, RSSParser, Article
from src.summarizers import GPTSummarizer, Summary
from src.publishers import MarkdownPublisher, TwitterPublisher, GitHubPublisher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PipelineMetrics:
    start_time: datetime
    end_time: Optional[datetime] = None
    articles_scraped: int = 0
    articles_summarized: int = 0
    articles_published: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
            data['duration_seconds'] = (self.end_time - self.start_time).total_seconds()
        return data


class NewsPipeline:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # Initialize cache for deduplication
        self.article_cache = TTLCache(
            maxsize=1000,
            ttl=86400 * 7  # 7 days
        )
        
        # Load cache from disk if exists
        self._load_cache()
        
        # Initialize components
        self.web_scraper = None
        self.rss_parser = None
        self.summarizer = None
        self.publishers = {}
        
        # Metrics
        self.metrics = None
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Set up environment variables for API keys
        # API key should be set in environment or .env file
        
        return config
    
    def _load_cache(self):
        """Load article cache from disk."""
        cache_file = Path("cache/article_cache.json")
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    for key, value in cache_data.items():
                        self.article_cache[key] = value
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
    
    def _save_cache(self):
        """Save article cache to disk."""
        cache_file = Path("cache/article_cache.json")
        cache_file.parent.mkdir(exist_ok=True)
        
        try:
            cache_data = dict(self.article_cache)
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
    
    def _get_article_hash(self, article: Article) -> str:
        """Generate unique hash for article."""
        content = f"{article.title}:{article.source_url}:{article.content[:200]}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _deduplicate_articles(self, articles: List[Article]) -> List[Article]:
        """Remove duplicate articles based on content similarity."""
        unique_articles = []
        
        for article in articles:
            article_hash = self._get_article_hash(article)
            
            if article_hash not in self.article_cache:
                self.article_cache[article_hash] = {
                    'title': article.title,
                    'date': datetime.now().isoformat()
                }
                unique_articles.append(article)
            else:
                logger.info(f"Skipping duplicate article: {article.title}")
        
        return unique_articles
    
    async def _scrape_articles_container(self, client: dagger.Client) -> List[Article]:
        """Run article scraping in Dagger container."""
        logger.info("Starting article scraping...")
        
        # Create container with Python and dependencies
        container = (
            client.container()
            .from_("python:3.11-slim")
            .with_exec(["apt-get", "update"])
            .with_exec(["apt-get", "install", "-y", "git"])
            .with_exec(["pip", "install", "httpx", "beautifulsoup4", "lxml", 
                       "feedparser", "python-dateutil", "tenacity"])
        )
        
        # Mount source code
        src_dir = client.host().directory("./src")
        container = container.with_directory("/app/src", src_dir)
        container = container.with_workdir("/app")
        
        # Run scraping
        all_articles = []
        
        # Web scraping
        if self.config['sources'].get('web_scraping'):
            async with WebScraper(self.config) as scraper:
                web_articles = await scraper.scrape_all_sources(
                    self.config['sources']['web_scraping']
                )
                all_articles.extend(web_articles)
        
        # RSS parsing
        if self.config['sources'].get('rss_feeds'):
            parser = RSSParser(self.config)
            rss_articles = await parser.parse_all_feeds(
                self.config['sources']['rss_feeds']
            )
            all_articles.extend(rss_articles)
        
        # Deduplicate
        unique_articles = self._deduplicate_articles(all_articles)
        
        logger.info(f"Scraped {len(unique_articles)} unique articles")
        return unique_articles
    
    async def _summarize_articles_container(self, client: dagger.Client, 
                                          articles: List[Article]) -> List[Tuple[Dict[str, Any], Summary]]:
        """Run article summarization in Dagger container."""
        logger.info("Starting article summarization...")
        
        # Create container with AI dependencies
        container = (
            client.container()
            .from_("python:3.11-slim")
            .with_exec(["pip", "install", "openai", "anthropic", "tiktoken", "tenacity"])
            .with_env_variable("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
            .with_env_variable("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
        )
        
        # Mount source code
        src_dir = client.host().directory("./src")
        container = container.with_directory("/app/src", src_dir)
        container = container.with_workdir("/app")
        
        # Configure summarizer for Anthropic Claude
        summarizer_config = self.config.get('summarization', {})
        summarizer_config['provider'] = 'anthropic'
        summarizer_config['model'] = 'claude-3-opus-20240229'
        summarizer_config['api_key_env'] = 'ANTHROPIC_API_KEY'
        
        summarizer = GPTSummarizer(summarizer_config)
        
        # Limit articles if configured
        max_articles = self.config.get('summarization', {}).get('max_articles_per_run', 20)
        articles_to_process = articles[:max_articles]
        
        # Convert articles to dicts for processing
        article_dicts = [article.to_dict() for article in articles_to_process]
        
        # Process articles
        summaries = await summarizer.process_articles(article_dicts, max_articles)
        
        logger.info(f"Summarized {len(summaries)} articles")
        return summaries
    
    async def _publish_content_container(self, client: dagger.Client,
                                       summaries: List[Tuple[Dict[str, Any], Summary]],
                                       niche: str) -> List[str]:
        """Run content publishing in Dagger container."""
        logger.info("Starting content publishing...")
        
        # Create container with publishing dependencies
        container = (
            client.container()
            .from_("python:3.11-slim")
            .with_exec(["apt-get", "update"])
            .with_exec(["apt-get", "install", "-y", "git"])
            .with_exec(["pip", "install", "jinja2", "tweepy", "pygithub", "gitpython"])
        )
        
        # Mount source code and templates
        src_dir = client.host().directory("./src")
        container = container.with_directory("/app/src", src_dir)
        
        if Path("./templates").exists():
            templates_dir = client.host().directory("./templates")
            container = container.with_directory("/app/templates", templates_dir)
        
        container = container.with_workdir("/app")
        
        published_files = []
        
        # Initialize publishers
        publishers = {}
        
        # Markdown publisher
        if self.config['publishing'].get('markdown', {}).get('enabled', True):
            markdown_config = self.config['publishing']['markdown']
            markdown_config['template_dir'] = './templates'
            publishers['markdown'] = MarkdownPublisher(markdown_config)
        
        # Twitter publisher
        if self.config['publishing'].get('twitter', {}).get('enabled', False):
            publishers['twitter'] = TwitterPublisher(self.config['publishing']['twitter'])
        
        # GitHub publisher
        if self.config['publishing'].get('github', {}).get('enabled', False):
            publishers['github'] = GitHubPublisher(self.config['publishing']['github'])
        
        # Generate newsletter content
        summarizer_config = self.config.get('summarization', {})
        summarizer_config['provider'] = 'anthropic'
        summarizer_config['model'] = 'claude-3-opus-20240229'
        summarizer_config['api_key_env'] = 'ANTHROPIC_API_KEY'
        
        summarizer = GPTSummarizer(summarizer_config)
        newsletter_content = await summarizer.create_newsletter_content(summaries, niche)
        
        # Publish with each publisher
        if 'markdown' in publishers:
            # Prepare article data for publishing
            all_articles_data = [
                {
                    'article': article,
                    'summary': summary.to_dict()
                }
                for article, summary in summaries
            ]
            
            filepath = publishers['markdown'].publish_newsletter(
                newsletter_content.to_dict(),
                all_articles_data,
                {'niche': niche}
            )
            published_files.append(filepath)
            
            # Publish individual articles
            for article, summary in summaries[:5]:  # Top 5 articles
                article_path = publishers['markdown'].publish_article(
                    article,
                    summary.to_dict()
                )
                published_files.append(article_path)
            
            # Generate index
            index_path = publishers['markdown'].generate_index(published_files)
            published_files.append(index_path)
        
        if 'twitter' in publishers:
            await publishers['twitter'].publish_newsletter_thread(
                newsletter_content.to_dict(),
                [article for article, _ in summaries]
            )
        
        if 'github' in publishers:
            await publishers['github'].publish_to_github(
                published_files,
                f"Update {niche} news digest - {datetime.now().strftime('%Y-%m-%d')}"
            )
        
        logger.info(f"Published {len(published_files)} files")
        return published_files
    
    async def run_pipeline(self) -> PipelineMetrics:
        """Run the complete news summarization pipeline."""
        self.metrics = PipelineMetrics(start_time=datetime.now())
        
        try:
            async with await dagger.connect() as client:
                # 1. Scrape articles
                articles = await self._scrape_articles_container(client)
                self.metrics.articles_scraped = len(articles)
                
                if not articles:
                    logger.warning("No articles found to process")
                    self.metrics.end_time = datetime.now()
                    return self.metrics
                
                # 2. Summarize articles
                summaries = await self._summarize_articles_container(client, articles)
                self.metrics.articles_summarized = len(summaries)
                
                if not summaries:
                    logger.warning("No articles were summarized")
                    self.metrics.end_time = datetime.now()
                    return self.metrics
                
                # 3. Publish content
                niche = self.config.get('niche', 'News')
                published_files = await self._publish_content_container(client, summaries, niche)
                self.metrics.articles_published = len(published_files)
                
                # Save cache
                self._save_cache()
                
                self.metrics.end_time = datetime.now()
                
                # Log metrics
                logger.info(f"Pipeline completed successfully!")
                logger.info(f"Metrics: {json.dumps(self.metrics.to_dict(), indent=2)}")
                
                return self.metrics
                
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.metrics.errors.append(str(e))
            self.metrics.end_time = datetime.now()
            
            # Create error report if GitHub publisher is enabled
            if self.config['publishing'].get('github', {}).get('enabled', False):
                try:
                    github_publisher = GitHubPublisher(self.config['publishing']['github'])
                    await github_publisher.create_issue_for_errors(
                        self.metrics.errors,
                        f"Pipeline Error - {datetime.now().strftime('%Y-%m-%d')}"
                    )
                except:
                    pass
            
            raise
    
    async def run_scheduled(self):
        """Run pipeline on schedule."""
        schedule_config = self.config.get('schedule', {})
        frequency = schedule_config.get('frequency', 'daily')
        run_time = schedule_config.get('time', '09:00')
        
        logger.info(f"Starting scheduled pipeline: {frequency} at {run_time}")
        
        while True:
            now = datetime.now()
            
            # Parse run time
            hour, minute = map(int, run_time.split(':'))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If time has passed today, schedule for tomorrow
            if now > next_run:
                next_run += timedelta(days=1)
            
            # Wait until next run
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"Next run scheduled for {next_run} ({wait_seconds/3600:.1f} hours)")
            
            await asyncio.sleep(wait_seconds)
            
            # Run pipeline
            try:
                await self.run_pipeline()
            except Exception as e:
                logger.error(f"Scheduled run failed: {e}")
            
            # Wait for next interval
            if frequency == 'weekly':
                await asyncio.sleep(86400 * 7)  # 7 days
            else:  # daily
                await asyncio.sleep(60)  # Small delay to avoid immediate re-run


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI News Summarizer Pipeline')
    parser.add_argument('--config', default='config/config.yaml', help='Path to config file')
    parser.add_argument('--scheduled', action='store_true', help='Run on schedule')
    parser.add_argument('--preview', action='store_true', help='Preview mode (no publishing)')
    
    args = parser.parse_args()
    
    # Create pipeline
    pipeline = NewsPipeline(args.config)
    
    if args.preview:
        pipeline.config['publishing']['twitter']['enabled'] = False
        pipeline.config['publishing']['github']['enabled'] = False
        logger.info("Running in preview mode - publishing disabled")
    
    if args.scheduled:
        await pipeline.run_scheduled()
    else:
        await pipeline.run_pipeline()


if __name__ == "__main__":
    asyncio.run(main())