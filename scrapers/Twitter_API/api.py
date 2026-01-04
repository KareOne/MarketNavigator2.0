"""
FastAPI application for Twitter Scraper API
Uses twitterapi.io to search tweets by keywords and retrieve comments/replies
"""

import asyncio
import logging
import os
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from twitter_client import TwitterAPIClient

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models
# =============================================================================

class Author(BaseModel):
    """Tweet author information"""
    id: str
    username: str
    name: str
    profile_image_url: Optional[str] = None
    verified: Optional[bool] = False
    followers_count: Optional[int] = 0


class TweetMetrics(BaseModel):
    """Tweet engagement metrics"""
    retweet_count: int = 0
    like_count: int = 0
    reply_count: int = 0
    quote_count: int = 0
    views_count: Optional[int] = 0


class Reply(BaseModel):
    """Reply/comment on a tweet"""
    id: str
    text: str
    author: Author
    created_at: str
    metrics: TweetMetrics


class Tweet(BaseModel):
    """Full tweet with optional replies"""
    id: str
    text: str
    author: Author
    created_at: str
    metrics: TweetMetrics
    replies: List[Reply] = []


class SearchRequest(BaseModel):
    """Request model for tweet search"""
    keyword: str = Field(..., description="Keyword or search term to search for")
    query_type: str = Field(default="Top", description="Search type: 'Top' or 'Latest'")
    num_posts: int = Field(default=10, ge=1, le=100, description="Number of posts to retrieve (max 100)")
    num_comments: int = Field(default=0, ge=0, le=50, description="Number of comments to retrieve per post (max 50)")


class SearchResponse(BaseModel):
    """Response model for tweet search"""
    keyword: str
    query_type: str
    total_results: int
    tweets: List[Tweet]


class TweetRepliesRequest(BaseModel):
    """Request model for getting tweet replies"""
    tweet_id: str = Field(..., description="The ID of the tweet to get replies for")
    num_replies: int = Field(default=20, ge=1, le=100, description="Number of replies to retrieve (max 100)")


class TweetRepliesResponse(BaseModel):
    """Response model for tweet replies"""
    tweet_id: str
    total_replies: int
    replies: List[Reply]


# =============================================================================
# FastAPI App
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info("Twitter Scraper API starting up...")
    yield
    logger.info("Twitter Scraper API shutting down...")


app = FastAPI(
    title="Twitter Scraper API",
    description="API for searching tweets and retrieving comments using twitterapi.io",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Initialize Twitter API client
twitter_client = TwitterAPIClient()


# =============================================================================
# Helper Functions
# =============================================================================

def parse_author(author_data: dict) -> Author:
    """Parse author data from API response"""
    return Author(
        id=author_data.get("id", ""),
        username=author_data.get("userName", author_data.get("username", "")),
        name=author_data.get("name", ""),
        profile_image_url=author_data.get("profilePicture", author_data.get("profile_image_url")),
        verified=author_data.get("isVerified", author_data.get("verified", False)),
        followers_count=author_data.get("followers", author_data.get("followers_count", 0))
    )


def parse_metrics(tweet_data: dict) -> TweetMetrics:
    """Parse tweet metrics from API response"""
    return TweetMetrics(
        retweet_count=tweet_data.get("retweetCount", tweet_data.get("retweet_count", 0)),
        like_count=tweet_data.get("likeCount", tweet_data.get("like_count", 0)),
        reply_count=tweet_data.get("replyCount", tweet_data.get("reply_count", 0)),
        quote_count=tweet_data.get("quoteCount", tweet_data.get("quote_count", 0)),
        views_count=tweet_data.get("viewCount", tweet_data.get("views_count", 0))
    )


def parse_tweet(tweet_data: dict, replies: List[Reply] = None) -> Tweet:
    """Parse tweet data from API response"""
    author_data = tweet_data.get("author", {})
    
    return Tweet(
        id=tweet_data.get("id", ""),
        text=tweet_data.get("text", ""),
        author=parse_author(author_data),
        created_at=tweet_data.get("createdAt", tweet_data.get("created_at", "")),
        metrics=parse_metrics(tweet_data),
        replies=replies or []
    )


def parse_reply(reply_data: dict) -> Reply:
    """Parse reply data from API response"""
    author_data = reply_data.get("author", {})
    
    return Reply(
        id=reply_data.get("id", ""),
        text=reply_data.get("text", ""),
        author=parse_author(author_data),
        created_at=reply_data.get("createdAt", reply_data.get("created_at", "")),
        metrics=parse_metrics(reply_data)
    )


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "twitter-scraper-api"}


@app.post("/search/tweets", response_model=SearchResponse)
async def search_tweets(request: SearchRequest):
    """
    Search for tweets by keyword.
    
    - **keyword**: Search term (supports Twitter search syntax)
    - **query_type**: "Top" for popular tweets or "Latest" for recent tweets
    - **num_posts**: Number of tweets to retrieve (1-100)
    - **num_comments**: Number of comments/replies to fetch per tweet (0-50)
    """
    try:
        logger.info(f"Searching tweets for keyword: '{request.keyword}', type: {request.query_type}")
        
        # Fetch tweets
        raw_tweets = await twitter_client.search_tweets_with_pagination(
            keyword=request.keyword,
            query_type=request.query_type,
            max_results=request.num_posts
        )
        
        logger.info(f"API returned {len(raw_tweets)} raw tweets for '{request.keyword}'")
        if len(raw_tweets) > 0:
            logger.info(f"Sample tweet ID: {raw_tweets[0].get('id')} - {raw_tweets[0].get('text')[:30]}...")
        else:
            logger.warning(f"No tweets found for keyword: '{request.keyword}' via twitterapi.io")
        
        # Parse tweets and optionally fetch replies
        tweets = []
        for raw_tweet in raw_tweets:
            try:
                replies = []
                
                # Fetch replies if requested
                if request.num_comments > 0:
                    tweet_id = raw_tweet.get("id", "")
                    if tweet_id:
                        try:
                            raw_replies = await twitter_client.get_tweet_replies_with_pagination(
                                tweet_id=tweet_id,
                                max_replies=request.num_comments
                            )
                            replies = [parse_reply(r) for r in raw_replies]
                            logger.info(f"Fetched {len(replies)} replies for tweet {tweet_id}")
                        except Exception as e:
                            logger.warning(f"Failed to fetch replies for tweet {tweet_id}: {e}")
                
                tweets.append(parse_tweet(raw_tweet, replies))
            except Exception as e:
                 logger.error(f"Error parsing tweet {raw_tweet.get('id')}: {e}")
        
        logger.info(f"Returning {len(tweets)} parsed tweets")

        return SearchResponse(
            keyword=request.keyword,
            query_type=request.query_type,
            total_results=len(tweets),
            tweets=tweets
        )
        
    except Exception as e:
        logger.error(f"Error searching tweets: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search tweets: {str(e)}")


@app.post("/tweet/replies", response_model=TweetRepliesResponse)
async def get_tweet_replies(request: TweetRepliesRequest):
    """
    Get replies/comments for a specific tweet.
    
    - **tweet_id**: The ID of the tweet
    - **num_replies**: Number of replies to retrieve (1-100)
    """
    try:
        logger.info(f"Fetching replies for tweet: {request.tweet_id}")
        
        raw_replies = await twitter_client.get_tweet_replies_with_pagination(
            tweet_id=request.tweet_id,
            max_replies=request.num_replies
        )
        
        replies = [parse_reply(r) for r in raw_replies]
        
        return TweetRepliesResponse(
            tweet_id=request.tweet_id,
            total_replies=len(replies),
            replies=replies
        )
        
    except Exception as e:
        logger.error(f"Error fetching replies: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch replies: {str(e)}")


@app.get("/tweet/{tweet_id}/thread")
async def get_tweet_thread(tweet_id: str):
    """
    Get the full conversation thread for a tweet.
    
    - **tweet_id**: The ID of the tweet
    """
    try:
        logger.info(f"Fetching thread for tweet: {tweet_id}")
        
        thread_data = await twitter_client.get_tweet_thread(tweet_id)
        
        return thread_data
        
    except Exception as e:
        logger.error(f"Error fetching thread: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch thread: {str(e)}")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8004, reload=True)
