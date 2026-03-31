"""
Application configuration using Pydantic Settings.

Loads environment variables from .env file.
"""

from functools import lru_cache
import logging
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./polymarket.db"

    # News API
    NEWS_API_KEY: str = ""

    # Polymarket API (Optional, for CLOB access)
    POLYMARKET_API_KEY: str = ""
    POLYMARKET_SECRET: str = ""
    POLYMARKET_PASSPHRASE: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # AI Agents for POLYGOD
    GEMINI_API_KEY: str = ""
    TAVILY_API_KEY: str = ""

    # POLYGOD Configuration
    POLYGOD_MODE: int = 0
    MEM0_CONFIG: str = '{"provider": "qdrant", "vector_store": {"url": "http://qdrant:6333"}}'

    # Network Configuration
    FORCE_IPV4: bool = False  # Force IPv4 for DNS resolution (helps in some Docker setups)

    # Database Configuration
    ALLOW_IN_MEMORY_DB_FALLBACK: bool = False  # Allow fallback to in-memory DB on init failure

    # Security Configuration
    POLYGOD_ADMIN_TOKEN: str = ""  # Admin token for POLYGOD mode switching endpoint

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
    logger.info("=== POLYGOD Configuration Validation ===")
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
    logger.info("=== Configuration Validation Complete ===")
    return settings


settings = get_settings()
