"""
Twitter API Client for twitterapi.io
Handles authentication and API requests to the twitterapi.io service
"""

import httpx
import os
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class TwitterAPIClient:
    """
    Client for interacting with twitterapi.io API.
    
    Provides methods for:
    - Searching tweets by keyword (Top/Latest)
    - Getting tweet replies/comments
    - Getting full tweet thread context
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("TWITTER_API_KEY")
        self.base_url = base_url or os.getenv("TWITTER_API_BASE_URL", "https://api.twitterapi.io")
        
        if not self.api_key:
            raise ValueError("TWITTER_API_KEY is required")
        
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an HTTP request to the API with retry logic."""
        import asyncio
        url = f"{self.base_url}{endpoint}"
        
        max_retries = 3
        base_delay = 5  # Start with 5s wait for 429
        
        for attempt in range(max_retries + 1):
            async with httpx.AsyncClient(timeout=120.0) as client:
                try:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self.headers,
                        params=params,
                        json=json_data
                    )
                    response.raise_for_status()
                    return response.json()
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        if attempt < max_retries:
                            wait_time = base_delay * (attempt + 1)
                            logger.warning(f"Rate limit hit (429). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error("Max retries reached for 429 error.")
                            raise
                    
                    logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                    raise
                except httpx.TimeoutException as e:
                    if attempt < max_retries:
                        wait_time = 5 # Wait 5s before retrying timeout
                        logger.warning(f"Request timed out ({type(e).__name__}). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                        await asyncio.sleep(wait_time)
                        continue
                    logger.error(f"Max retries reached for Timeout ({type(e).__name__}).")
                    raise
                except httpx.RequestError as e:
                    logger.error(f"Request error ({type(e).__name__}): {e}")
                    raise
    
    async def search_tweets(
        self, 
        keyword: str, 
        query_type: str = "Top",
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for tweets by keyword.
        
        Args:
            keyword: Search term/keyword
            query_type: "Top" or "Latest" for sorting
            cursor: Pagination cursor for next page
            
        Returns:
            API response with tweets and pagination info
        """
        params = {
            "query": keyword,
            "queryType": query_type
        }
        
        if cursor:
            params["cursor"] = cursor
        
        return await self._make_request(
            method="GET",
            endpoint="/twitter/tweet/advanced_search",
            params=params
        )
    
    async def get_tweet_replies(
        self, 
        tweet_id: str, 
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get replies/comments for a specific tweet.
        
        Args:
            tweet_id: The ID of the tweet
            cursor: Pagination cursor for next page
            
        Returns:
            API response with replies and pagination info
        """
        params = {"tweetId": tweet_id}
        
        if cursor:
            params["cursor"] = cursor
        
        return await self._make_request(
            method="GET",
            endpoint="/twitter/tweet/replies",
            params=params
        )
    
    async def get_tweet_thread(self, tweet_id: str) -> Dict[str, Any]:
        """
        Get the full thread context for a tweet.
        
        Args:
            tweet_id: The ID of the tweet
            
        Returns:
            API response with full thread context
        """
        params = {"tweetId": tweet_id}
        
        return await self._make_request(
            method="GET",
            endpoint="/twitter/tweet/thread",
            params=params
        )
    
    async def search_tweets_with_pagination(
        self, 
        keyword: str, 
        query_type: str = "Top",
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search tweets with automatic pagination to get desired number of results.
        
        Args:
            keyword: Search term/keyword
            query_type: "Top" or "Latest"
            max_results: Maximum number of tweets to retrieve
            
        Returns:
            List of tweet objects
        """
        all_tweets = []
        cursor = None
        
        while len(all_tweets) < max_results:
            response = await self.search_tweets(keyword, query_type, cursor)
            
            tweets = response.get("tweets", [])
            if not tweets:
                break
            
            all_tweets.extend(tweets)
            
            # Check for next page
            cursor = response.get("next_cursor")
            if not cursor:
                break
        
        return all_tweets[:max_results]
    
    async def get_tweet_replies_with_pagination(
        self, 
        tweet_id: str, 
        max_replies: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get replies for a tweet with automatic pagination.
        
        Args:
            tweet_id: The ID of the tweet
            max_replies: Maximum number of replies to retrieve
            
        Returns:
            List of reply tweet objects
        """
        all_replies = []
        cursor = None
        
        while len(all_replies) < max_replies:
            response = await self.get_tweet_replies(tweet_id, cursor)
            
            replies = response.get("replies", [])
            if not replies:
                break
            
            all_replies.extend(replies)
            
            # Check for next page
            cursor = response.get("next_cursor")
            if not cursor:
                break
        
        return all_replies[:max_replies]
