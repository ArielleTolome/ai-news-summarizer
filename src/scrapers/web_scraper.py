import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
import lxml.html
from lxml import etree

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    content: str
    author: Optional[str]
    date: Optional[datetime]
    source_url: str
    source_name: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'content': self.content,
            'author': self.author,
            'date': self.date.isoformat() if self.date else None,
            'source_url': self.source_url,
            'source_name': self.source_name
        }


class WebScraper:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rate_limit_delay = config.get('rate_limit_delay', 1.0)
        self.timeout = config.get('timeout', 30)
        self.headers = {
            'User-Agent': config.get('user_agent', 
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        }
        self.session = None
        
    async def __aenter__(self):
        self.session = httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def fetch_page(self, url: str) -> str:
        """Fetch page content with retry logic."""
        try:
            response = await self.session.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise
    
    def extract_with_css(self, soup: BeautifulSoup, selector: str, 
                        attribute: Optional[str] = None) -> Optional[str]:
        """Extract text or attribute using CSS selector."""
        try:
            element = soup.select_one(selector)
            if element:
                if attribute:
                    return element.get(attribute)
                return element.get_text(strip=True)
        except Exception as e:
            logger.warning(f"CSS extraction failed for {selector}: {e}")
        return None
    
    def extract_with_xpath(self, html: str, xpath: str) -> Optional[str]:
        """Extract text using XPath."""
        try:
            tree = lxml.html.fromstring(html)
            result = tree.xpath(xpath)
            if result:
                if isinstance(result[0], str):
                    return result[0].strip()
                return result[0].text_content().strip()
        except Exception as e:
            logger.warning(f"XPath extraction failed for {xpath}: {e}")
        return None
    
    def parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse various date formats."""
        if not date_str:
            return None
            
        date_formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        return None
    
    async def scrape_article(self, url: str, selectors: Dict[str, str], 
                           source_name: str) -> Optional[Article]:
        """Scrape a single article."""
        try:
            html = await self.fetch_page(url)
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract using CSS or XPath
            title = None
            content = None
            author = None
            date = None
            
            for field, selector in selectors.items():
                if selector.startswith('//'):  # XPath
                    value = self.extract_with_xpath(html, selector)
                else:  # CSS
                    value = self.extract_with_css(soup, selector)
                
                if field == 'title':
                    title = value
                elif field == 'content':
                    content = value
                elif field == 'author':
                    author = value
                elif field == 'date':
                    date = self.parse_date(value)
            
            if not title or not content:
                logger.warning(f"Missing required fields for {url}")
                return None
            
            return Article(
                title=title,
                content=content,
                author=author,
                date=date,
                source_url=url,
                source_name=source_name
            )
            
        except Exception as e:
            logger.error(f"Error scraping article {url}: {e}")
            return None
    
    async def scrape_article_list(self, source_config: Dict[str, Any]) -> List[str]:
        """Scrape list of article URLs from a source."""
        try:
            base_url = source_config['url']
            html = await self.fetch_page(base_url)
            
            article_selector = source_config['selectors'].get('articles')
            if not article_selector:
                return []
            
            urls = []
            
            if article_selector.startswith('//'):  # XPath
                tree = lxml.html.fromstring(html)
                elements = tree.xpath(article_selector)
                for elem in elements:
                    href = elem.get('href')
                    if href:
                        urls.append(urljoin(base_url, href))
            else:  # CSS
                soup = BeautifulSoup(html, 'html.parser')
                elements = soup.select(article_selector)
                for elem in elements:
                    href = elem.get('href') or elem.find('a', href=True)
                    if href:
                        if isinstance(href, dict):
                            href = href.get('href')
                        urls.append(urljoin(base_url, href))
            
            return urls[:source_config.get('max_articles', 10)]
            
        except Exception as e:
            logger.error(f"Error scraping article list from {source_config['url']}: {e}")
            return []
    
    async def scrape_source(self, source_config: Dict[str, Any]) -> List[Article]:
        """Scrape all articles from a source."""
        source_name = source_config.get('name', urlparse(source_config['url']).netloc)
        
        # Get article URLs
        article_urls = await self.scrape_article_list(source_config)
        logger.info(f"Found {len(article_urls)} articles from {source_name}")
        
        # Scrape individual articles with rate limiting
        articles = []
        for url in article_urls:
            article = await self.scrape_article(
                url, 
                source_config['selectors'],
                source_name
            )
            if article:
                articles.append(article)
            
            # Rate limiting
            await asyncio.sleep(self.rate_limit_delay)
        
        return articles
    
    async def scrape_all_sources(self, sources: List[Dict[str, Any]]) -> List[Article]:
        """Scrape articles from all configured sources."""
        all_articles = []
        
        for source in sources:
            logger.info(f"Scraping {source.get('name', source['url'])}")
            articles = await self.scrape_source(source)
            all_articles.extend(articles)
            logger.info(f"Scraped {len(articles)} articles")
        
        return all_articles


async def main():
    """Example usage."""
    config = {
        'rate_limit_delay': 1.0,
        'timeout': 30
    }
    
    sources = [
        {
            'url': 'https://example.com/tech-news',
            'name': 'Example Tech',
            'selectors': {
                'articles': '.article-list a',
                'title': 'h1.article-title',
                'content': '.article-content',
                'author': '.author-name',
                'date': '.publish-date'
            },
            'max_articles': 5
        }
    ]
    
    async with WebScraper(config) as scraper:
        articles = await scraper.scrape_all_sources(sources)
        for article in articles:
            print(f"Title: {article.title}")
            print(f"URL: {article.source_url}")
            print("---")


if __name__ == "__main__":
    asyncio.run(main())