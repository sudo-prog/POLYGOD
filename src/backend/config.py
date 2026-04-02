from functools import lru_cache
import logging
import os

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./polymarket.db", env="DATABASE_URL")
    NEWS_API_KEY: str = Field(default="", env="NEWS_API_KEY")
    POLYMARKET_API_HOST: str = Field(default="https://clob.polymarket.com", env="POLYMARKET_API_HOST")
    POLYMARKET_API_KEY: str = Field(default="", env="POLYMARKET_API_KEY")
    POLYMARKET_SECRET: str = Field(default="", env="POLYMARKET_SECRET")
    POLYMARKET_PASSPHRASE: str = Field(default="", env="POLYMARKET_PASSPHRASE")
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://127.0.0.1:5173", env="CORS_ORIGINS")
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    DEBUG: bool = Field(default=False, env="DEBUG")
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")
    TAVILY_API_KEY: str = Field(default="", env="TAVILY_API_KEY")
    GROK_API_KEY: str = Field(default="", env="GROK_API_KEY")  # ← NEW: xAI Grok
    LIGHTNING_AI_TOKEN: str = Field(default="", env="LIGHTNING_AI_TOKEN")  # Lightning AI GPU offload
    POLYGOD_MODE: int = Field(default=0, env="POLYGOD_MODE")
    MEM0_CONFIG: str = Field(default='{"provider": "qdrant", "vector_store": {"url": "http://qdrant:6333"}}', env="MEM0_CONFIG")
    FORCE_IPV4: bool = Field(default=False, env="FORCE_IPV4")
    ALLOW_IN_MEMORY_DB_FALLBACK: bool = Field(default=False, env="ALLOW_IN_MEMORY_DB_FALLBACK")
    POLYGOD_ADMIN_TOKEN: str = Field(default="", env="POLYGOD_ADMIN_TOKEN")
    X_BEARER_TOKEN: str = Field(default="", env="X_BEARER_TOKEN")
    ENCRYPTION_KEY: str = Field(default="", env="ENCRYPTION_KEY")  # ← LLM Hub: API key encryption (Fernet)

    @property
    def cors_origins_list(self) -> list[str]:
        """
        Parse CORS origins string into a list, filtering out blanks.

        Handles cases like:
        - empty string -> []
        - trailing commas -> ignores empty segments
        - whitespace around origins -> stripped
        """
        if not self.CORS_ORIGINS:
            return []

        return [
            origin
            for origin in (o.strip() for o in self.CORS_ORIGINS.split(","))
            if origin
        ]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    # Validation logs for all env vars from .env.example
    logger = logging.getLogger(__name__)
    logger.info("=== POLYGOD Configuration Validation (GOD TIER) ===")
    logger.info(f"GROK_API_KEY present: {'YES' if settings.GROK_API_KEY else 'NO (using fallback)'}")
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
            "POLYMARKET_SECRET/POLYMARKET_PASSPHRASE not fully set - authenticated trading may be disabled"
        )
    if not settings.MEM0_CONFIG:
        logger.warning("MEM0_CONFIG not set - vector store features disabled")
    if not settings.POLYMARKET_API_KEY:
        logger.info("POLYMARKET_API_KEY not set - using public API fallback")
    if not settings.POLYMARKET_SECRET or not settings.POLYMARKET_PASSPHRASE:
        logger.info(
            "POLYMARKET_SECRET/POLYMARKET_PASSPHRASE not fully set - authenticated trading may be disabled"
        )
    # MEM0_CONFIG has a non-empty default, so `bool(settings.MEM0_CONFIG)` is not useful to detect loading.
    # Instead, distinguish between default and environment-provided values in the log output.
    mem0_config_source = "env" if "MEM0_CONFIG" in os.environ else "default"
    logger.info(
        f"POLYGOD_MODE={settings.POLYGOD_MODE} | MEM0_CONFIG source={mem0_config_source}"
    )
    # Added validation logging for them in get_settings() (similar to other keys)
    if not settings.X_BEARER_TOKEN:
        logger.warning("X_BEARER_TOKEN not set - X API features (sentiment) may be limited")
    if not settings.LIGHTNING_AI_TOKEN:
        logger.warning("LIGHTNING_AI_TOKEN not set - GPU tournament offload disabled")
    else:
        logger.info("LIGHTNING_AI_TOKEN configured - GPU tournament offload available")
    logger.info(f"POLYMARKET_API_HOST: {settings.POLYMARKET_API_HOST}")
    logger.info("=== Configuration Validation Complete ===")
    return settings


settings = get_settings()