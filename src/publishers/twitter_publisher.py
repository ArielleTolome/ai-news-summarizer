import os
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

import tweepy
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TwitterPublisher:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', False)
        
        if self.enabled:
            # Load API keys from environment
            api_keys = self._load_api_keys()
            
            # Initialize Twitter client
            self.client = tweepy.Client(
                consumer_key=api_keys['consumer_key'],
                consumer_secret=api_keys['consumer_secret'],
                access_token=api_keys['access_token'],
                access_token_secret=api_keys['access_token_secret']
            )
            
            # Character limits
            self.max_tweet_length = 280
            self.thread_delimiter = config.get('thread_delimiter', '🧵')
    
    def _load_api_keys(self) -> Dict[str, str]:
        """Load Twitter API keys from environment."""
        api_keys_env = self.config.get('api_keys_env', 'TWITTER_API_KEYS')
        api_keys_json = os.getenv(api_keys_env)
        
        if not api_keys_json:
            raise ValueError(f"Twitter API keys not found in {api_keys_env}")
        
        try:
            return json.loads(api_keys_json)
        except json.JSONDecodeError:
            # Try individual env vars as fallback
            return {
                'consumer_key': os.getenv('TWITTER_CONSUMER_KEY'),
                'consumer_secret': os.getenv('TWITTER_CONSUMER_SECRET'),
                'access_token': os.getenv('TWITTER_ACCESS_TOKEN'),
                'access_token_secret': os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            }
    
    def _truncate_text(self, text: str, max_length: int, suffix: str = "...") -> str:
        """Truncate text to fit within character limit."""
        if len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
    
    def _create_thread_tweets(self, content: List[str], 
                            thread_number: Optional[int] = None) -> List[str]:
        """Split content into tweet-sized chunks for a thread."""
        tweets = []
        
        # Add thread marker to first tweet if specified
        first_tweet_suffix = f" {self.thread_delimiter}" if thread_number is None else f" {self.thread_delimiter} {thread_number}/"
        
        for i, text in enumerate(content):
            if i == 0:
                # First tweet gets thread marker
                max_length = self.max_tweet_length - len(first_tweet_suffix)
                tweet = self._truncate_text(text, max_length) + first_tweet_suffix
            else:
                # Subsequent tweets
                tweet = self._truncate_text(text, self.max_tweet_length)
            
            tweets.append(tweet)
        
        return tweets
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _post_tweet(self, text: str, 
                         reply_to_tweet_id: Optional[str] = None) -> Optional[str]:
        """Post a single tweet."""
        try:
            response = await asyncio.to_thread(
                self.client.create_tweet,
                text=text,
                reply_to_tweet_id=reply_to_tweet_id
            )
            
            if response.data:
                return response.data['id']
            
            return None
            
        except Exception as e:
            logger.error(f"Error posting tweet: {e}")
            raise
    
    async def publish_newsletter_thread(self, 
                                      newsletter_content: Dict[str, Any],
                                      top_articles: List[Dict[str, Any]]) -> List[str]:
        """Publish newsletter as a Twitter thread."""
        if not self.enabled:
            logger.info("Twitter publishing is disabled")
            return []
        
        try:
            thread_content = []
            
            # 1. Title tweet
            title_tweet = f"📰 {newsletter_content['title']}\n\n{newsletter_content['introduction']}"
            thread_content.append(title_tweet)
            
            # 2. Top stories tweets
            for i, story in enumerate(newsletter_content['top_stories'][:3], 1):
                story_tweet = f"{i}. {story['title']}\n\n"
                story_tweet += f"{story['summary']}\n\n"
                story_tweet += f"Read more: {story['url']}"
                thread_content.append(story_tweet)
            
            # 3. Trends tweet
            if newsletter_content.get('trends'):
                trends_tweet = "📈 Today's Trends:\n\n"
                for trend in newsletter_content['trends'][:3]:
                    trends_tweet += f"• {trend}\n"
                thread_content.append(trends_tweet)
            
            # 4. Closing tweet with link to full newsletter
            if self.config.get('newsletter_url'):
                closing_tweet = f"📖 Read the full newsletter with {len(top_articles)} articles and detailed analysis:\n{self.config['newsletter_url']}"
                thread_content.append(closing_tweet)
            
            # Create thread
            tweet_ids = []
            reply_to_id = None
            
            for content in thread_content:
                tweet_id = await self._post_tweet(content, reply_to_id)
                if tweet_id:
                    tweet_ids.append(tweet_id)
                    reply_to_id = tweet_id
                    # Rate limiting
                    await asyncio.sleep(2)
                else:
                    logger.error("Failed to post tweet in thread")
                    break
            
            logger.info(f"Published Twitter thread with {len(tweet_ids)} tweets")
            return tweet_ids
            
        except Exception as e:
            logger.error(f"Error publishing Twitter thread: {e}")
            return []
    
    async def publish_article_summary(self, 
                                    article: Dict[str, Any],
                                    summary: Dict[str, Any]) -> Optional[str]:
        """Publish a single article summary as a tweet."""
        if not self.enabled:
            logger.info("Twitter publishing is disabled")
            return None
        
        try:
            # Format tweet
            tweet = f"📄 {article['title']}\n\n"
            tweet += f"{summary['short_summary']}\n\n"
            
            # Add tags
            if summary.get('tags'):
                hashtags = ' '.join(f"#{tag.replace(' ', '')}" for tag in summary['tags'][:3])
                tweet += f"{hashtags}\n\n"
            
            tweet += f"Read more: {article['source_url']}"
            
            # Truncate if needed
            tweet = self._truncate_text(tweet, self.max_tweet_length)
            
            # Post tweet
            tweet_id = await self._post_tweet(tweet)
            
            if tweet_id:
                logger.info(f"Published article tweet: {tweet_id}")
                return tweet_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error publishing article tweet: {e}")
            return None
    
    async def publish_insights_thread(self, insights: str, niche: str) -> List[str]:
        """Publish insights as a mini-thread."""
        if not self.enabled:
            logger.info("Twitter publishing is disabled")
            return []
        
        try:
            # Split insights into paragraphs
            paragraphs = insights.split('\n\n')
            
            thread_content = []
            
            # Opening tweet
            opening = f"🔍 {niche} Industry Insights - {datetime.now().strftime('%B %d, %Y')}\n\nKey takeaways from today's news:"
            thread_content.append(opening)
            
            # Add insight paragraphs
            for paragraph in paragraphs[:3]:  # Limit to 3 tweets
                if len(paragraph.strip()) > 20:
                    thread_content.append(paragraph.strip())
            
            # Create thread
            tweets = self._create_thread_tweets(thread_content)
            
            tweet_ids = []
            reply_to_id = None
            
            for tweet in tweets:
                tweet_id = await self._post_tweet(tweet, reply_to_id)
                if tweet_id:
                    tweet_ids.append(tweet_id)
                    reply_to_id = tweet_id
                    await asyncio.sleep(2)
            
            logger.info(f"Published insights thread with {len(tweet_ids)} tweets")
            return tweet_ids
            
        except Exception as e:
            logger.error(f"Error publishing insights thread: {e}")
            return []


async def main():
    """Example usage."""
    config = {
        'enabled': True,
        'api_keys_env': 'TWITTER_API_KEYS'
    }
    
    publisher = TwitterPublisher(config)
    
    # Example newsletter content
    newsletter_content = {
        'title': 'AI News Digest - June 2024',
        'introduction': 'Top AI developments this week',
        'top_stories': [
            {
                'title': 'Major AI Breakthrough',
                'summary': 'Researchers achieve new milestone in natural language understanding',
                'url': 'https://example.com/article1'
            }
        ],
        'trends': ['Increased focus on AI safety', 'New open-source models']
    }
    
    # Publish as thread
    tweet_ids = await publisher.publish_newsletter_thread(newsletter_content, [])
    print(f"Published tweets: {tweet_ids}")


if __name__ == "__main__":
    asyncio.run(main())