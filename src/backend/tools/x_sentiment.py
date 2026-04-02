from typing import Dict

import aiohttp

from src.backend.config import settings


async def get_x_sentiment(market_slug: str) -> Dict:
    """
    Fetch X sentiment data for a given market slug.

    Args:
        market_slug: The market identifier to search for

    Returns:
        Dictionary containing bull_score, top_posts, and whale_mentions
    """
    if not hasattr(settings, "X_BEARER_TOKEN") or not settings.X_BEARER_TOKEN:
        return {
            "bull_score": 0.5,
            "top_posts": [],
            "whale_mentions": [],
            "error": "X_BEARER_TOKEN not configured",
        }

    async with aiohttp.ClientSession() as session:
        try:
            # Search for posts related to the market
            search_url = "https://api.x.com/2/tweets/search/recent"
            search_params = {
                "query": f"{market_slug} OR #{market_slug.replace('-', '')}",
                "max_results": 10,
                "tweet.fields": "public_metrics,created_at,text,author_id",
            }

            async with session.get(
                search_url,
                headers={"Authorization": f"Bearer {settings.X_BEARER_TOKEN}"},
                params=search_params,
            ) as response:
                if response.status != 200:
                    return {
                        "bull_score": 0.5,
                        "top_posts": [],
                        "whale_mentions": [],
                        "error": f"Search API error: {response.status}",
                    }
                search_results = await response.json()

            # Get user details for author information
            author_ids = [
                tweet["author_id"] for tweet in search_results.get("data", [])
            ]
            if author_ids:
                users_url = "https://api.x.com/2/users"
                users_params = {
                    "ids": ",".join(author_ids),
                    "user.fields": "public_metrics,verified,created_at",
                }

                async with session.get(
                    users_url,
                    headers={"Authorization": f"Bearer {settings.X_BEARER_TOKEN}"},
                    params=users_params,
                ) as response:
                    if response.status == 200:
                        users_results = await response.json()
                        users_dict = {
                            user["id"]: user for user in users_results.get("data", [])
                        }
                    else:
                        users_dict = {}
            else:
                users_dict = {}

            # Process tweets and calculate sentiment
            posts = []
            total_sentiment = 0
            valid_posts = 0

            for tweet in search_results.get("data", []):
                author = users_dict.get(tweet["author_id"], {})
                metrics = tweet.get("public_metrics", {})
                likes = metrics.get("like_count", 0)
                replies = metrics.get("reply_count", 0)
                retweets = metrics.get("retweet_count", 0)
                engagement = likes + replies + retweets

                # Simple sentiment scoring (positive/negative keywords)
                text = tweet.get("text", "").lower()
                positive_keywords = ["bullish", "moon", "buy", "strong", "up"]
                negative_keywords = ["bearish", "sell", "down", "weak", "dump"]

                sentiment_score = 0
                for word in positive_keywords:
                    if word in text:
                        sentiment_score += 0.2
                for word in negative_keywords:
                    if word in text:
                        sentiment_score -= 0.2

                # Normalize sentiment between -1 and 1
                sentiment_score = max(-1, min(1, sentiment_score))

                posts.append(
                    {
                        "text": tweet["text"],
                        "created_at": tweet["created_at"],
                        "author": author.get("username", ""),
                        "verified": author.get("verified", False),
                        "engagement": engagement,
                        "sentiment": sentiment_score,
                    }
                )

                if sentiment_score != 0:
                    total_sentiment += sentiment_score
                    valid_posts += 1

            # Calculate average bull score
            bull_score = 0.5
            if valid_posts > 0:
                avg_sentiment = total_sentiment / valid_posts
                # Convert -1 to 1 range to 0 to 1 range
                bull_score = (avg_sentiment + 1) / 2

            # Identify whale mentions (high engagement posts)
            whale_mentions = []
            for post in posts:
                if post["engagement"] > 100:  # Threshold for whale activity
                    whale_mentions.append(
                        {
                            "text": post["text"],
                            "author": post["author"],
                            "verified": post["verified"],
                            "engagement": post["engagement"],
                            "sentiment": post["sentiment"],
                        }
                    )

            return {
                "bull_score": round(bull_score, 3),
                "top_posts": posts[:5],  # Return top 5 posts
                "whale_mentions": whale_mentions[:3],  # Return top 3 whale mentions
            }

        except Exception as e:
            return {
                "bull_score": 0.5,
                "top_posts": [],
                "whale_mentions": [],
                "error": str(e),
            }
