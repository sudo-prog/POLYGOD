import logging
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./polymarket.db"
    )
    NEWS_API_KEY: str = Field(default="")
    POLYMARKET_API_HOST: str = Field(
        default="https://clob.polymarket.com"
    )
    POLYMARKET_API_KEY: str = Field(default="")
    POLYMARKET_SECRET: str = Field(default="")
    POLYMARKET_PASSPHRASE: str = Field(default="")
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173"
    )
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    DEBUG: bool = Field(default=False)
    GEMINI_API_KEY: str = Field(default="")
    GROK_API_KEY: str = Field(default="")
    TAVILY_API_KEY: str = Field(default="")
    LIGHTNING_AI_TOKEN: str = Field(default="")
    POLYGOD_MODE: int = Field(default=0)
    MEM0_CONFIG: str = Field(
        default='{"provider": "qdrant", "vector_store": {"url": "http://qdrant:6333"}}'
    )
    FORCE_IPV4: bool = Field(default=False)
    ALLOW_IN_MEMORY_DB_FALLBACK: bool = Field(
        default=False
    )
    POLYGOD_ADMIN_TOKEN: str = Field(
        default="super-secret-admin-token-change-me"
    )
    X_BEARER_TOKEN: str = Field(default="")
    ENCRYPTION_KEY: str = Field(default="")
    REDIS_URL: str = Field(default="redis://redis:6379/0")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    logger = logging.getLogger(__name__)
    logger.info("=== POLYGOD Configuration Validation (GOD TIER) ===")
    logger.info(
        "🚀 POLYGOD_MODE=%s | REDIS=%s | ADMIN_TOKEN=***",
        settings.POLYGOD_MODE,
        settings.REDIS_URL,
    )
    grok_status = "YES (masked)" if settings.GROK_API_KEY else "NO (using fallback)"
    logger.info(f"GROK_API_KEY present: {grok_status}")
    logger.info(f"Database: {settings.DATABASE_URL!r}")
    logger.info(f"CORS Origins: {settings.CORS_ORIGINS!r}")
    logger.info(f"Server: {settings.HOST}:{settings.PORT}")
    logger.info(f"Debug Mode: {'Enabled' if settings.DEBUG else 'Disabled'}")
    if not settings.NEWS_API_KEY:
        logger.warning("NEWS_API_KEY not set - news features may be limited")
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set - AI agents disabled")
    if not settings.TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not set - search features limited")
    if not settings.POLYMARKET_API_KEY:
        logger.warning("POLYMARKET_API_KEY not set - using public API fallback")
    if not settings.POLYMARKET_SECRET or not settings.POLYMARKET_PASSPHRASE:
        logger.warning(
            "POLYMARKET_SECRET/POLYMARKET_PASSPHRASE not fully set - "
            "authenticated trading may be disabled"
        )
    if not settings.X_BEARER_TOKEN:
        logger.warning(
            "X_BEARER_TOKEN not set - X API features (sentiment) may be limited"
        )
    if not settings.LIGHTNING_AI_TOKEN:
        logger.warning("LIGHTNING_AI_TOKEN not set - GPU tournament offload disabled")
    else:
        logger.info("LIGHTNING_AI_TOKEN configured - GPU tournament offload available")
    if not settings.ENCRYPTION_KEY:
        logger.warning("ENCRYPTION_KEY not set - LLM Hub API keys stored in plaintext")
    logger.info(f"POLYMARKET_API_HOST: {settings.POLYMARKET_API_HOST}")
    logger.info("=== Configuration Validation Complete ===")
    return settings


settings = get_settings()
