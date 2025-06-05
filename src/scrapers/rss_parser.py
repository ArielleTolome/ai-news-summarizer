import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import httpx
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .web_scraper import Article, WebScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RSSParser:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.timeout = config.get('timeout', 30)
        self.headers = {
            'User-Agent': config.get('user_agent', 
                'Mozilla/5.0 (compatible; NewsBot/1.0)')
        }
        self.web_scraper = WebScraper(config)
        
    async def validate_feed(self, feed_url: str) -> bool:
        """Validate if the URL is a valid RSS/Atom feed."""
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
                response = await client.get(feed_url)
                response.raise_for_status()
                
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if any(ct in content_type for ct in ['xml', 'rss', 'atom']):
                    return True
                
                # Try to parse as XML
                try:
                    ET.fromstring(response.text)
                    return True
                except ET.ParseError:
                    return False
                    
        except Exception as e:
            logger.error(f"Feed validation failed for {feed_url}: {e}")
            return False
    
    def extract_full_content(self, entry: Dict[str, Any]) -> str:
        """Extract full content from feed entry."""
        content = ""
        
        # Try different content fields
        content_fields = [
            'content',
            'summary_detail',
            'description',
            'summary'
        ]
        
        for field in content_fields:
            if field in entry:
                if isinstance(entry[field], list):
                    content = entry[field][0].get('value', '')
                elif isinstance(entry[field], dict):
                    content = entry[field].get('value', '')
                else:
                    content = str(entry[field])
                
                if content:
                    break
        
        # Clean HTML if present
        if '<' in content and '>' in content:
            soup = BeautifulSoup(content, 'html.parser')
            content = soup.get_text(separator=' ', strip=True)
        
        return content
    
    def parse_date(self, entry: Dict[str, Any]) -> Optional[datetime]:
        """Parse date from various feed date fields."""
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']
        
        for field in date_fields:
            if field in entry and entry[field]:
                try:
                    # feedparser returns time.struct_time
                    return datetime(*entry[field][:6])
                except Exception:
                    pass
        
        # Try parsing string dates
        date_str_fields = ['published', 'updated', 'created', 'pubDate']
        for field in date_str_fields:
            if field in entry and entry[field]:
                try:
                    return date_parser.parse(entry[field])
                except Exception:
                    pass
        
        return None
    
    def extract_author(self, entry: Dict[str, Any]) -> Optional[str]:
        """Extract author information from feed entry."""
        if 'author' in entry:
            return entry['author']
        
        if 'authors' in entry and entry['authors']:
            authors = entry['authors']
            if isinstance(authors, list) and authors:
                author = authors[0]
                if isinstance(author, dict):
                    return author.get('name', '')
                return str(author)
        
        if 'author_detail' in entry:
            return entry['author_detail'].get('name', '')
        
        return None
    
    async def fetch_full_article(self, url: str, feed_name: str) -> Optional[str]:
        """Attempt to fetch full article content from the URL."""
        try:
            async with self.web_scraper as scraper:
                # Simple content extraction - can be enhanced with specific selectors
                html = await scraper.fetch_page(url)
                soup = BeautifulSoup(html, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Try common article containers
                article_selectors = [
                    'article',
                    'main',
                    '.article-content',
                    '.post-content',
                    '.entry-content',
                    '#content'
                ]
                
                for selector in article_selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        return content_elem.get_text(separator=' ', strip=True)
                
                # Fallback to body
                body = soup.find('body')
                if body:
                    return body.get_text(separator=' ', strip=True)[:5000]  # Limit length
                    
        except Exception as e:
            logger.warning(f"Failed to fetch full article from {url}: {e}")
        
        return None
    
    async def parse_feed_entry(self, entry: Dict[str, Any], feed_config: Dict[str, Any]) -> Optional[Article]:
        """Parse a single feed entry into an Article."""
        try:
            # Extract basic information
            title = entry.get('title', '').strip()
            link = entry.get('link', '').strip()
            
            if not title or not link:
                return None
            
            # Extract content
            content = self.extract_full_content(entry)
            
            # Try to fetch full article if configured
            if feed_config.get('fetch_full_content', False) and link:
                full_content = await self.fetch_full_article(link, feed_config['name'])
                if full_content and len(full_content) > len(content):
                    content = full_content
            
            if not content:
                return None
            
            # Extract metadata
            author = self.extract_author(entry)
            date = self.parse_date(entry)
            
            return Article(
                title=title,
                content=content,
                author=author,
                date=date,
                source_url=link,
                source_name=feed_config.get('name', urlparse(feed_config['url']).netloc)
            )
            
        except Exception as e:
            logger.error(f"Error parsing feed entry: {e}")
            return None
    
    async def parse_feed(self, feed_config: Dict[str, Any]) -> List[Article]:
        """Parse all entries from a single RSS/Atom feed."""
        feed_url = feed_config['url']
        
        # Validate feed
        if not await self.validate_feed(feed_url):
            logger.error(f"Invalid feed: {feed_url}")
            return []
        
        try:
            # Fetch and parse feed
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
                response = await client.get(feed_url)
                response.raise_for_status()
                feed_data = feedparser.parse(response.text)
            
            if feed_data.bozo:
                logger.warning(f"Feed parsing issues for {feed_url}: {feed_data.bozo_exception}")
            
            # Parse entries
            articles = []
            max_articles = feed_config.get('max_articles', 20)
            
            for entry in feed_data.entries[:max_articles]:
                article = await self.parse_feed_entry(entry, feed_config)
                if article:
                    articles.append(article)
            
            logger.info(f"Parsed {len(articles)} articles from {feed_config.get('name', feed_url)}")
            return articles
            
        except Exception as e:
            logger.error(f"Error parsing feed {feed_url}: {e}")
            return []
    
    async def parse_all_feeds(self, feeds: List[Dict[str, Any]]) -> List[Article]:
        """Parse all configured RSS/Atom feeds."""
        all_articles = []
        
        # Process feeds concurrently
        tasks = [self.parse_feed(feed_config) for feed_config in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Feed parsing failed: {result}")
            elif isinstance(result, list):
                all_articles.extend(result)
        
        return all_articles


async def main():
    """Example usage."""
    config = {
        'timeout': 30
    }
    
    feeds = [
        {
            'url': 'https://example.com/feed.xml',
            'name': 'Example Tech Feed',
            'max_articles': 10,
            'fetch_full_content': True
        }
    ]
    
    parser = RSSParser(config)
    articles = await parser.parse_all_feeds(feeds)
    
    for article in articles:
        print(f"Title: {article.title}")
        print(f"Author: {article.author}")
        print(f"Date: {article.date}")
        print(f"URL: {article.source_url}")
        print(f"Content preview: {article.content[:200]}...")
        print("---")


if __name__ == "__main__":
    asyncio.run(main())