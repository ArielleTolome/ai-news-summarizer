import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import Counter
import asyncio
import json

import openai
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential
import tiktoken

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Summary:
    short_summary: str  # 2-3 sentences
    detailed_summary: str  # Comprehensive summary
    key_insights: List[str]  # Bullet points
    tags: List[str]  # Relevant tags/categories
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'short_summary': self.short_summary,
            'detailed_summary': self.detailed_summary,
            'key_insights': self.key_insights,
            'tags': self.tags
        }


@dataclass
class NewsletterContent:
    title: str
    introduction: str
    top_stories: List[Dict[str, Any]]
    trends: List[str]
    insights: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'introduction': self.introduction,
            'top_stories': self.top_stories,
            'trends': self.trends,
            'insights': self.insights
        }


class GPTSummarizer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = config.get('model', 'gpt-4')
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 2000)
        
        # Initialize API client based on provider
        self.provider = config.get('provider', 'openai')
        if self.provider == 'openai':
            api_key = os.getenv(config.get('api_key_env', 'OPENAI_API_KEY'))
            openai.api_key = api_key
            self.client = openai
        elif self.provider == 'anthropic':
            api_key = os.getenv(config.get('api_key_env', 'ANTHROPIC_API_KEY'))
            self.client = Anthropic(api_key=api_key)
            self.model = config.get('model', 'claude-3-opus-20240229')
        
        # Initialize tokenizer for content truncation
        try:
            self.encoding = tiktoken.encoding_for_model(self.model if self.provider == 'openai' else 'gpt-4')
        except:
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))
    
    def truncate_content(self, content: str, max_tokens: int = 3000) -> str:
        """Truncate content to fit within token limit."""
        tokens = self.encoding.encode(content)
        if len(tokens) <= max_tokens:
            return content
        
        truncated_tokens = tokens[:max_tokens]
        return self.encoding.decode(truncated_tokens)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _call_api(self, messages: List[Dict[str, str]], 
                       max_tokens: Optional[int] = None) -> str:
        """Call the AI API with retry logic."""
        try:
            if self.provider == 'openai':
                response = await asyncio.to_thread(
                    self.client.ChatCompletion.create,
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens or self.max_tokens
                )
                return response.choices[0].message.content
            
            elif self.provider == 'anthropic':
                # Extract system message if present
                system_message = None
                user_messages = []
                
                for msg in messages:
                    if msg['role'] == 'system':
                        system_message = msg['content']
                    else:
                        user_messages.append(msg)
                
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model,
                    messages=user_messages,
                    system=system_message,
                    temperature=self.temperature,
                    max_tokens=max_tokens or self.max_tokens
                )
                return response.content[0].text
                
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    async def summarize_article(self, article: Dict[str, Any]) -> Summary:
        """Generate comprehensive summary for a single article."""
        content = self.truncate_content(article['content'])
        
        prompt = f"""
You are an expert news summarizer. Analyze the following article and provide:

1. A short summary (2-3 sentences) capturing the main point
2. A detailed summary (1-2 paragraphs) with key information
3. 3-5 key insights or takeaways as bullet points
4. 3-5 relevant tags/categories

Article Title: {article['title']}
Source: {article['source_name']}
Author: {article.get('author', 'Unknown')}

Content:
{content}

Please format your response as JSON with the following structure:
{{
    "short_summary": "...",
    "detailed_summary": "...",
    "key_insights": ["insight1", "insight2", ...],
    "tags": ["tag1", "tag2", ...]
}}
"""
        
        messages = [
            {"role": "system", "content": "You are an expert news analyst and summarizer."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self._call_api(messages)
        
        try:
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                return Summary(
                    short_summary=data.get('short_summary', '')[:500],
                    detailed_summary=data.get('detailed_summary', ''),
                    key_insights=data.get('key_insights', [])[:5],
                    tags=data.get('tags', [])[:5]
                )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse JSON response: {e}")
        
        # Fallback parsing if JSON fails
        lines = response.split('\n')
        return Summary(
            short_summary="AI-generated summary of the article.",
            detailed_summary=response[:500],
            key_insights=["Key insight extracted from article"],
            tags=["AI", "Technology"]
        )
    
    def extract_trends(self, summaries: List[Tuple[Dict[str, Any], Summary]]) -> List[str]:
        """Extract trending topics and themes from multiple summaries."""
        # Collect all tags and key terms
        all_tags = []
        all_insights = []
        
        for article, summary in summaries:
            all_tags.extend(summary.tags)
            all_insights.extend(summary.key_insights)
        
        # Count tag frequency
        tag_counts = Counter(all_tags)
        
        # Extract top trends
        trends = []
        for tag, count in tag_counts.most_common(5):
            if count > 1:
                trends.append(f"{tag} (mentioned in {count} articles)")
        
        return trends
    
    async def generate_newsletter_title(self, niche: str, summaries: List[Summary]) -> str:
        """Generate an engaging newsletter title."""
        # Get top topics from summaries
        top_topics = []
        for summary in summaries[:5]:
            if summary.tags:
                top_topics.append(summary.tags[0])
        
        prompt = f"""
Generate an engaging, professional newsletter title for a {niche} news digest.

Top topics covered: {', '.join(top_topics[:3])}

Requirements:
- Catchy but professional
- Includes the niche ({niche})
- Under 10 words
- Relevant to current news cycle

Provide only the title, no explanation.
"""
        
        messages = [
            {"role": "system", "content": "You are a professional newsletter editor."},
            {"role": "user", "content": prompt}
        ]
        
        title = await self._call_api(messages, max_tokens=50)
        return title.strip().strip('"').strip("'")
    
    async def generate_insights(self, summaries: List[Tuple[Dict[str, Any], Summary]], 
                               niche: str) -> str:
        """Generate overall insights and analysis."""
        # Prepare insights data
        all_insights = []
        for article, summary in summaries[:10]:
            all_insights.extend(summary.key_insights)
        
        prompt = f"""
Based on the following key insights from today's {niche} news, provide a brief analysis
of the overall trends, patterns, and what they mean for the industry.

Key insights:
{chr(10).join(f"- {insight}" for insight in all_insights[:20])}

Write 2-3 paragraphs of thoughtful analysis. Focus on:
1. Major themes and patterns
2. What this means for the future
3. Action items for readers

Keep it concise and insightful.
"""
        
        messages = [
            {"role": "system", "content": f"You are an expert {niche} industry analyst."},
            {"role": "user", "content": prompt}
        ]
        
        return await self._call_api(messages)
    
    async def create_newsletter_content(self, 
                                      articles_with_summaries: List[Tuple[Dict[str, Any], Summary]],
                                      niche: str) -> NewsletterContent:
        """Create complete newsletter content."""
        # Sort by relevance/quality (you could implement a scoring system)
        sorted_articles = articles_with_summaries[:10]  # Top 10 stories
        
        # Generate newsletter components
        summaries = [summary for _, summary in sorted_articles]
        
        # Generate title
        title = await self.generate_newsletter_title(niche, summaries)
        
        # Extract trends
        trends = self.extract_trends(sorted_articles)
        
        # Generate insights
        insights = await self.generate_insights(sorted_articles, niche)
        
        # Create introduction
        introduction = f"Welcome to today's {niche} news digest! We've analyzed {len(articles_with_summaries)} articles to bring you the most important developments and insights."
        
        # Format top stories
        top_stories = []
        for article, summary in sorted_articles[:5]:
            top_stories.append({
                'title': article['title'],
                'source': article['source_name'],
                'url': article['source_url'],
                'summary': summary.short_summary,
                'key_insights': summary.key_insights[:3]
            })
        
        return NewsletterContent(
            title=title,
            introduction=introduction,
            top_stories=top_stories,
            trends=trends,
            insights=insights
        )
    
    async def process_articles(self, articles: List[Dict[str, Any]], 
                             max_articles: Optional[int] = None) -> List[Tuple[Dict[str, Any], Summary]]:
        """Process multiple articles with summaries."""
        if max_articles:
            articles = articles[:max_articles]
        
        # Process articles concurrently in batches
        batch_size = 5
        all_summaries = []
        
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            tasks = [self.summarize_article(article) for article in batch]
            summaries = await asyncio.gather(*tasks, return_exceptions=True)
            
            for article, summary in zip(batch, summaries):
                if isinstance(summary, Summary):
                    all_summaries.append((article, summary))
                else:
                    logger.error(f"Failed to summarize article: {article['title']}")
        
        return all_summaries


async def main():
    """Example usage."""
    config = {
        'provider': 'openai',
        'model': 'gpt-4',
        'api_key_env': 'OPENAI_API_KEY',
        'temperature': 0.7
    }
    
    # Example article
    articles = [
        {
            'title': 'AI Breakthrough in Natural Language Understanding',
            'content': 'Researchers have developed a new AI model that shows remarkable improvements in understanding context and nuance in human language...',
            'source_name': 'Tech News Daily',
            'source_url': 'https://example.com/article1',
            'author': 'Jane Doe'
        }
    ]
    
    summarizer = GPTSummarizer(config)
    summaries = await summarizer.process_articles(articles)
    
    for article, summary in summaries:
        print(f"Title: {article['title']}")
        print(f"Short Summary: {summary.short_summary}")
        print(f"Tags: {', '.join(summary.tags)}")
        print("---")


if __name__ == "__main__":
    asyncio.run(main())