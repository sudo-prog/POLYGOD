"""
X (Twitter) Sentiment Tool — real-time tweet sentiment for Polymarket markets.

Uses the X API v2 bearer token to fetch recent tweets and score sentiment
against a market question. Integrated into the Niche Scanner for tweet-count
markets and the Debate Floor generalist agent.

Requires: X_BEARER_TOKEN in .env
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from src.backend.config import settings

logger = logging.getLogger(__name__)

X_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"


@dataclass
class SentimentResult:
    query: str
    tweet_count: int
    positive: int
    negative: int
    neutral: int
    score: float  # -1.0 (bearish) → +1.0 (bullish)
    sample_tweets: list[str]


async def get_x_sentiment(query: str, max_results: int = 100) -> SentimentResult:
    """
    Fetch recent tweets matching `query` and return a simple sentiment score.

    Sentiment is computed via keyword matching (fast, no LLM cost):
    - Positive keywords: "yes", "win", "bullish", "up", "long", "call"
    - Negative keywords: "no", "lose", "bearish", "down", "short", "put"

    Falls back to a neutral zero-score result if the API key is not configured
    or the request fails — callers must handle this gracefully.
    """
    bearer = settings.X_BEARER_TOKEN.get_secret_value()
    if not bearer:
        logger.debug("X_BEARER_TOKEN not set — skipping sentiment fetch")
        return SentimentResult(
            query=query,
            tweet_count=0,
            positive=0,
            negative=0,
            neutral=0,
            score=0.0,
            sample_tweets=[],
        )

    _positive_words = frozenset(
        ["yes", "win", "bullish", "up", "long", "buy", "true", "confirm", "pass", "approve"]
    )
    _negative_words = frozenset(
        ["no", "lose", "bearish", "down", "short", "sell", "false", "deny", "fail", "reject"]
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                X_SEARCH_URL,
                headers={"Authorization": f"Bearer {bearer}"},
                params={
                    "query": f"{query} -is:retweet lang:en",
                    "max_results": min(max_results, 100),
                    "tweet.fields": "text",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        tweets = data.get("data", [])
        if not tweets:
            return SentimentResult(
                query=query,
                tweet_count=0,
                positive=0,
                negative=0,
                neutral=0,
                score=0.0,
                sample_tweets=[],
            )

        pos = neg = neu = 0
        samples: list[str] = []
        for t in tweets:
            text = t.get("text", "").lower()
            words = set(text.split())
            has_pos = bool(words & _positive_words)
            has_neg = bool(words & _negative_words)
            if has_pos and not has_neg:
                pos += 1
            elif has_neg and not has_pos:
                neg += 1
            else:
                neu += 1
            if len(samples) < 5:
                samples.append(t.get("text", "")[:120])

        total = pos + neg + neu
        score = ((pos - neg) / total) if total > 0 else 0.0

        return SentimentResult(
            query=query,
            tweet_count=total,
            positive=pos,
            negative=neg,
            neutral=neu,
            score=round(score, 3),
            sample_tweets=samples,
        )

    except Exception as exc:
        logger.warning("X sentiment fetch failed for %r: %s", query, exc)
        return SentimentResult(
            query=query,
            tweet_count=0,
            positive=0,
            negative=0,
            neutral=0,
            score=0.0,
            sample_tweets=[],
        )
