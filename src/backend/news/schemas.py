"""
Pydantic schemas for news articles.

Defines data models for news API responses.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NewsArticleIn(BaseModel):
    """Input model for a news article from external APIs."""

    model_config = ConfigDict(extra="ignore")

    title: str = ""
    description: str | None = None
    url: str = ""
    source: dict | str = Field(default_factory=lambda: {})
    author: str | None = None
    urlToImage: str | None = None
    publishedAt: str | None = None
    content: str | None = None


class NewsArticleOut(BaseModel):
    """Output model for a news article sent to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    market_id: str
    title: str
    description: str | None = None
    url: str
    source: str | None = None
    author: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None
    sentiment_score: float | None = None


class NewsListResponse(BaseModel):
    """Response containing a list of news articles."""

    articles: list[NewsArticleOut]
    total: int
    market_id: str
