import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import re

from jinja2 import Template, Environment, FileSystemLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarkdownPublisher:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.output_dir = Path(config.get('output_dir', './output'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 environment
        template_dir = Path(config.get('template_dir', './templates'))
        if template_dir.exists():
            self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))
        else:
            self.jinja_env = None
            
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility."""
        # Remove/replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = filename.strip()
        # Limit length
        if len(filename) > 200:
            filename = filename[:200]
        return filename
    
    def format_article_section(self, article: Dict[str, Any], summary: Dict[str, Any]) -> str:
        """Format a single article section in markdown."""
        section = f"### {article['title']}\n\n"
        section += f"**Source:** [{article['source_name']}]({article['source_url']})\n"
        
        if article.get('author'):
            section += f"**Author:** {article['author']}\n"
        
        if article.get('date'):
            section += f"**Date:** {article['date']}\n"
        
        section += "\n"
        section += f"**Summary:** {summary['short_summary']}\n\n"
        
        if summary.get('key_insights'):
            section += "**Key Insights:**\n"
            for insight in summary['key_insights']:
                section += f"- {insight}\n"
            section += "\n"
        
        if summary.get('tags'):
            section += f"**Tags:** {', '.join(summary['tags'])}\n"
        
        section += "\n---\n\n"
        return section
    
    def format_newsletter(self, newsletter_content: Dict[str, Any], 
                         all_articles: List[Dict[str, Any]],
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """Format complete newsletter in markdown."""
        # Use template if available
        if self.jinja_env and 'newsletter_template.md' in self.jinja_env.list_templates():
            template = self.jinja_env.get_template('newsletter_template.md')
            return template.render(
                newsletter=newsletter_content,
                articles=all_articles,
                metadata=metadata or {},
                date=datetime.now()
            )
        
        # Fallback to manual formatting
        content = f"# {newsletter_content['title']}\n\n"
        content += f"*Generated on {datetime.now().strftime('%B %d, %Y')}*\n\n"
        
        # Table of Contents
        content += "## Table of Contents\n\n"
        content += "1. [Introduction](#introduction)\n"
        content += "2. [Top Stories](#top-stories)\n"
        content += "3. [Trends](#trends)\n"
        content += "4. [Insights & Analysis](#insights--analysis)\n"
        content += "5. [All Articles](#all-articles)\n\n"
        
        # Introduction
        content += "## Introduction\n\n"
        content += f"{newsletter_content['introduction']}\n\n"
        
        # Top Stories
        content += "## Top Stories\n\n"
        for i, story in enumerate(newsletter_content['top_stories'], 1):
            content += f"### {i}. {story['title']}\n\n"
            content += f"**Source:** [{story['source']}]({story['url']})\n\n"
            content += f"{story['summary']}\n\n"
            
            if story.get('key_insights'):
                content += "**Key Points:**\n"
                for insight in story['key_insights']:
                    content += f"- {insight}\n"
                content += "\n"
        
        # Trends
        if newsletter_content.get('trends'):
            content += "## Trends\n\n"
            for trend in newsletter_content['trends']:
                content += f"- {trend}\n"
            content += "\n"
        
        # Insights
        content += "## Insights & Analysis\n\n"
        content += f"{newsletter_content['insights']}\n\n"
        
        # All Articles
        if all_articles:
            content += "## All Articles\n\n"
            for article_data in all_articles:
                article = article_data['article']
                summary = article_data['summary']
                content += self.format_article_section(article, summary)
        
        # Footer
        content += "---\n\n"
        content += "*This newsletter was generated automatically by AI News Summarizer.*\n"
        
        return content
    
    def publish_newsletter(self, newsletter_content: Dict[str, Any],
                          all_articles: List[Dict[str, Any]],
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """Publish newsletter to markdown file."""
        try:
            # Generate filename
            date_str = datetime.now().strftime('%Y-%m-%d')
            niche = metadata.get('niche', 'news') if metadata else 'news'
            base_filename = f"{date_str}-{niche}-digest"
            filename = self.sanitize_filename(base_filename) + ".md"
            
            # Format content
            content = self.format_newsletter(newsletter_content, all_articles, metadata)
            
            # Write to file
            filepath = self.output_dir / filename
            filepath.write_text(content, encoding='utf-8')
            
            logger.info(f"Newsletter published to {filepath}")
            
            # Also create a 'latest' symlink for easy access
            latest_link = self.output_dir / "latest.md"
            if latest_link.exists():
                latest_link.unlink()
            latest_link.symlink_to(filename)
            
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error publishing newsletter: {e}")
            raise
    
    def publish_article(self, article: Dict[str, Any], 
                       summary: Dict[str, Any]) -> str:
        """Publish a single article as markdown."""
        try:
            # Generate filename
            date_str = datetime.now().strftime('%Y-%m-%d')
            title_slug = self.sanitize_filename(article['title'][:50])
            filename = f"{date_str}-{title_slug}.md"
            
            # Format content
            content = f"# {article['title']}\n\n"
            content += f"*Published on {datetime.now().strftime('%B %d, %Y')}*\n\n"
            content += self.format_article_section(article, summary)
            
            # Add detailed summary if available
            if summary.get('detailed_summary'):
                content += "## Detailed Summary\n\n"
                content += f"{summary['detailed_summary']}\n\n"
            
            # Write to articles subdirectory
            articles_dir = self.output_dir / "articles"
            articles_dir.mkdir(exist_ok=True)
            
            filepath = articles_dir / filename
            filepath.write_text(content, encoding='utf-8')
            
            logger.info(f"Article published to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error publishing article: {e}")
            raise
    
    def generate_index(self, published_files: List[str]) -> str:
        """Generate an index file linking to all published content."""
        try:
            content = "# AI News Summarizer - Index\n\n"
            content += f"*Last updated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n"
            
            # Group files by type
            newsletters = []
            articles = []
            
            for filepath in published_files:
                path = Path(filepath)
                if 'articles' in path.parts:
                    articles.append(path)
                else:
                    newsletters.append(path)
            
            # List newsletters
            if newsletters:
                content += "## Newsletters\n\n"
                for path in sorted(newsletters, reverse=True):
                    relative_path = path.relative_to(self.output_dir)
                    content += f"- [{path.stem}]({relative_path})\n"
                content += "\n"
            
            # List articles
            if articles:
                content += "## Individual Articles\n\n"
                for path in sorted(articles, reverse=True)[:20]:  # Last 20 articles
                    relative_path = path.relative_to(self.output_dir)
                    content += f"- [{path.stem}]({relative_path})\n"
                content += "\n"
            
            # Write index
            index_path = self.output_dir / "index.md"
            index_path.write_text(content, encoding='utf-8')
            
            logger.info(f"Index generated at {index_path}")
            return str(index_path)
            
        except Exception as e:
            logger.error(f"Error generating index: {e}")
            raise


def main():
    """Example usage."""
    config = {
        'output_dir': './output',
        'template_dir': './templates'
    }
    
    publisher = MarkdownPublisher(config)
    
    # Example data
    newsletter_content = {
        'title': 'AI News Digest - June 2024',
        'introduction': 'Welcome to this week\'s AI news digest!',
        'top_stories': [
            {
                'title': 'Major AI Breakthrough',
                'source': 'Tech News',
                'url': 'https://example.com',
                'summary': 'Researchers achieve new milestone...',
                'key_insights': ['Insight 1', 'Insight 2']
            }
        ],
        'trends': ['Trend 1', 'Trend 2'],
        'insights': 'This week showed significant progress...'
    }
    
    all_articles = [
        {
            'article': {
                'title': 'AI Article',
                'source_name': 'Tech Blog',
                'source_url': 'https://example.com',
                'author': 'John Doe',
                'date': '2024-06-04'
            },
            'summary': {
                'short_summary': 'Brief summary...',
                'key_insights': ['Insight 1', 'Insight 2'],
                'tags': ['AI', 'Technology']
            }
        }
    ]
    
    # Publish newsletter
    filepath = publisher.publish_newsletter(newsletter_content, all_articles, {'niche': 'AI'})
    print(f"Published to: {filepath}")


if __name__ == "__main__":
    main()