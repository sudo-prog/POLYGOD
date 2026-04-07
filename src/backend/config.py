import logging
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:pass@localhost/polymarket"
    )
    NEWS_API_KEY: SecretStr = Field(default=SecretStr(""))
    POLYMARKET_API_HOST: str = Field(default="https://clob.polymarket.com")
    POLYMARKET_API_KEY: SecretStr = Field(default=SecretStr(""))
    POLYMARKET_SECRET: SecretStr = Field(default=SecretStr(""))
    POLYMARKET_PASSPHRASE: SecretStr = Field(default=SecretStr(""))
    CORS_ORIGINS: str = Field(default="http://localhost:5173,https://yourdomain.com")
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    DEBUG: bool = Field(default=False)
    GEMINI_API_KEY: SecretStr = Field(default=SecretStr(""))
    GROK_API_KEY: SecretStr = Field(default=SecretStr(""))
    TAVILY_API_KEY: SecretStr = Field(default=SecretStr(""))
    POLYGOD_ADMIN_TOKEN: SecretStr = Field(default=SecretStr(""))
    ENCRYPTION_KEY: SecretStr = Field(
        default=SecretStr("dev-encryption-key-32-chars-here!!")
    )
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    TELEGRAM_BOT_TOKEN: SecretStr = Field(default=SecretStr(""))
    TELEGRAM_CHAT_ID: str = Field(default="")
    LANGSMITH_API_KEY: SecretStr = Field(default=SecretStr(""))
    LIGHTNING_AI_TOKEN: SecretStr = Field(default=SecretStr(""))
    X_BEARER_TOKEN: SecretStr = Field(default=SecretStr(""))
    INTERNAL_API_KEY: SecretStr = Field(default=SecretStr("change-this-before-use"))
    MEM0_CONFIG: str = Field(
        default='{"provider": "qdrant", "vector_store": {"url": "http://qdrant:6333"}}'
    )
    POLYGOD_MODE: int = Field(default=0)
    ALLOW_IN_MEMORY_DB_FALLBACK: bool = Field(default=False)
    FORCE_IPV4: bool = Field(default=False)

    model_config = {"env_file": ".env", "extra": "ignore", "env_file_encoding": "utf-8"}

    @field_validator("POLYGOD_ADMIN_TOKEN", "INTERNAL_API_KEY")
    @classmethod
    def validate_prod_secrets(cls, v: SecretStr, info) -> SecretStr:
        """Validate required secrets in production (when DEBUG=False)."""
        if not info.data.get("DEBUG", False) and not v.get_secret_value():
            raise ValueError(f"{info.field_name} is required in production")
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def debug(self) -> bool:
        return self.DEBUG

    @property
    def internal_api_key(self) -> str:
        return self.INTERNAL_API_KEY.get_secret_value()


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
    grok_status = (
        "YES (masked)"
        if settings.GROK_API_KEY.get_secret_value()
        else "NO (using fallback)"
    )
    logger.info(f"GROK_API_KEY present: {grok_status}")
    logger.info(f"Database: {settings.DATABASE_URL!r}")
    logger.info(f"CORS Origins: {settings.CORS_ORIGINS!r}")
    logger.info(f"Server: {settings.HOST}:{settings.PORT}")
    logger.info(f"Debug Mode: {'Enabled' if settings.DEBUG else 'Disabled'}")
    if not settings.NEWS_API_KEY.get_secret_value():
        logger.warning("NEWS_API_KEY not set - news features may be limited")
    if not settings.GEMINI_API_KEY.get_secret_value():
        logger.warning("GEMINI_API_KEY not set - AI agents disabled")
    if not settings.TAVILY_API_KEY.get_secret_value():
        logger.warning("TAVILY_API_KEY not set - search features limited")
    if not settings.POLYMARKET_API_KEY.get_secret_value():
        logger.warning("POLYMARKET_API_KEY not set - using public API fallback")
    if (
        not settings.POLYMARKET_SECRET.get_secret_value()
        or not settings.POLYMARKET_PASSPHRASE.get_secret_value()
    ):
        logger.warning(
            "POLYMARKET_SECRET/PASSPHRASE not set - authenticated trading disabled"
        )
    if not settings.X_BEARER_TOKEN.get_secret_value():
        logger.warning(
            "X_BEARER_TOKEN not set - X API features (sentiment) may be limited"
        )
    if not settings.LIGHTNING_AI_TOKEN.get_secret_value():
        logger.warning("LIGHTNING_AI_TOKEN not set - GPU tournament offload disabled")
    if not settings.ENCRYPTION_KEY.get_secret_value():
        logger.warning("ENCRYPTION_KEY not set - LLM Hub API keys stored in plaintext")
    logger.info(f"POLYMARKET_API_HOST: {settings.POLYMARKET_API_HOST}")
    logger.info("=== Configuration Validation Complete ===")
    # Note: POLYGOD_ADMIN_TOKEN and INTERNAL_API_KEY validation
    # is now handled by field_validator at model initialization
    return settings


settings = get_settings()
