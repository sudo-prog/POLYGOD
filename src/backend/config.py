"""
POLYGOD Configuration — Hardened for production.

Changes vs previous version:
  - POLYMARKET_PRIVATE_KEY: kept from previous version for live CLOB trading
  - DATABASE_URL default changed to SQLite (matches Docker Compose volumes)
  - INTERNAL_API_KEY sentinel rejection now checks DEBUG correctly
  - ENCRYPTION_KEY auto-generates a valid Fernet key instead of sentinel
  - Logging block trimmed — no spam on lru_cache miss
  - case_sensitive=True added to SettingsConfigDict
  - X_BEARER_TOKEN added
"""

import logging
from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SENTINEL_VALUES = frozenset(
    {
        "",
        "change-this-before-use",
        "dev-encryption-key-32-chars-here!!",
        "your_gemini_api_key",
        "your_grok_api_key",
    }
)


class Settings(BaseSettings):
    # ── Database ────────────────────────────────────────────────────────────
    # Default to SQLite so the app boots without a .env file in development.
    # Override to postgresql+asyncpg://... in production via .env / Docker env.
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./polymarket.db")

    # ── External APIs ────────────────────────────────────────────────────────
    NEWS_API_KEY: SecretStr = Field(default=SecretStr(""))
    POLYMARKET_API_HOST: str = Field(default="https://clob.polymarket.com")
    POLYMARKET_API_KEY: SecretStr = Field(default=SecretStr(""))
    POLYMARKET_SECRET: SecretStr = Field(default=SecretStr(""))
    POLYMARKET_PASSPHRASE: SecretStr = Field(default=SecretStr(""))
    # EVM private key for signing CLOB orders (live trading only)
    POLYMARKET_PRIVATE_KEY: SecretStr = Field(default=SecretStr(""))
    GEMINI_API_KEY: SecretStr = Field(default=SecretStr(""))
    # Groq - completely FREE model provider (no credit card)
    GROQ_API_KEY: SecretStr = Field(default=SecretStr(""))
    GROK_API_KEY: SecretStr = Field(default=SecretStr(""))
    TAVILY_API_KEY: SecretStr = Field(default=SecretStr(""))
    # RESTORED: Used by llm_router.py GodTierLLMRouter
    OPENROUTER_API_KEY: SecretStr = Field(default=SecretStr(""))
    PUTER_API_KEY: SecretStr = Field(default=SecretStr(""))
    X_BEARER_TOKEN: SecretStr = Field(default=SecretStr(""))
    LANGSMITH_API_KEY: SecretStr = Field(default=SecretStr(""))
    LIGHTNING_AI_TOKEN: SecretStr = Field(default=SecretStr(""))

    # ── Kronos / HuggingFace ─────────────────────────────────────────────────────
    HF_TOKEN: SecretStr = Field(default=SecretStr(""))
    # Use "amazon/chronos-t5-small" for CPU, "amazon/chronos-t5-large" for GPU
    KRONOS_MODEL_NAME: str = Field(default="amazon/chronos-t5-small")
    # Hard cap on candles streamed per call to prevent OOM in 2 GB swarm container
    KRONOS_MAX_CANDLES: int = Field(default=5000)
    # Timeout in seconds for HF streaming calls
    KRONOS_STREAM_TIMEOUT: int = Field(default=30)

    # ── Server ───────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = Field(default="http://localhost:5173,https://yourdomain.com")
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    DEBUG: bool = Field(default=False)

    # ── Security ─────────────────────────────────────────────────────────────
    # POLYGOD_ADMIN_TOKEN: required in all environments — no default.
    POLYGOD_ADMIN_TOKEN: SecretStr = Field(default=SecretStr(""))
    # INTERNAL_API_KEY: required in prod; sentinel allowed ONLY when DEBUG=True.
    INTERNAL_API_KEY: SecretStr = Field(default=SecretStr("change-this-before-use"))
    # ENCRYPTION_KEY: must be a valid Fernet key (32-byte URL-safe base64).
    # If empty/sentinel, a secure key is auto-generated at startup (dev only).
    ENCRYPTION_KEY: SecretStr = Field(default=SecretStr(""))

    # ── Infrastructure ────────────────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    COLAB_WEBHOOK_URL: str = Field(default="")  # set in .env to enable Colab offload
    TELEGRAM_BOT_TOKEN: SecretStr = Field(default=SecretStr(""))
    TELEGRAM_CHAT_ID: str = Field(default="")
    MEM0_CONFIG: str = Field(
        default='{"provider": "qdrant", "vector_store": {"url": "http://qdrant:6333"}}'
    )

    # ── POLYGOD Runtime ───────────────────────────────────────────────────────
    POLYGOD_MODE: int = Field(default=0)
    ALLOW_IN_MEMORY_DB_FALLBACK: bool = Field(default=False)
    FORCE_IPV4: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # ── Validators ───────────────────────────────────────────────────────────

    @field_validator("POLYGOD_ADMIN_TOKEN")
    @classmethod
    def require_admin_token(cls, v: SecretStr) -> SecretStr:
        """
        Reject the explicit sentinel but allow empty string.
        Empty string is allowed here so DEBUG-mode startups work without a token.
        Production enforcement is in lifespan() in main.py.
        """
        val = v.get_secret_value()
        if val in ("change-this-before-use", ""):
            # Don't raise here — enforcement is in lifespan().
            # But log loudly so misconfigured deploys are obvious in container logs.
            import logging as _log

            _log.getLogger(__name__).error(
                "POLYGOD_ADMIN_TOKEN is not set or is default sentinel. "
                "The app will refuse to start. "
                'Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return v

    @field_validator("INTERNAL_API_KEY")
    @classmethod
    def validate_internal_key(cls, v: SecretStr, info) -> SecretStr:
        """
        INTERNAL_API_KEY: sentinel allowed in DEBUG mode only.
        In production (DEBUG=False) this must be a real secret.

        NOTE: We can't read DEBUG here (field order dependency), so we validate
        at the model level in validate_security_posture() below.
        """
        return v

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def ensure_valid_fernet_key(cls, v: SecretStr) -> SecretStr:
        """
        ENCRYPTION_KEY must be a valid Fernet key.
        If missing/sentinel, auto-generate a secure one.
        WARNING: Auto-generated keys are ephemeral — store the output in .env
        or encrypted API keys will be unreadable after restart.
        """
        val = v.get_secret_value()
        if val in _SENTINEL_VALUES:
            # Auto-generate a valid Fernet key
            new_key = Fernet.generate_key().decode()
            import logging as _log

            _log.getLogger(__name__).warning(
                "ENCRYPTION_KEY not set — auto-generated ephemeral Fernet key. "
                "LLM Hub API keys will be UNREADABLE after restart! "
                "Set ENCRYPTION_KEY in your .env file."
            )
            return SecretStr(new_key)

        # Validate that the provided value is actually a valid Fernet key
        try:
            Fernet(val.encode() if isinstance(val, str) else val)
        except Exception:
            raise ValueError(
                "ENCRYPTION_KEY must be a valid 32-byte URL-safe base64 Fernet key. "
                'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        return v

    @model_validator(mode="after")
    def validate_security_posture(self) -> "Settings":
        """
        Cross-field validation: enforce that INTERNAL_API_KEY is a real secret
        when DEBUG=False (production mode). Warn in DEBUG mode.
        """
        import logging as _log

        _logger = _log.getLogger(__name__)
        internal_val = self.INTERNAL_API_KEY.get_secret_value()
        if internal_val in _SENTINEL_VALUES:
            if not self.DEBUG:
                raise ValueError(
                    "INTERNAL_API_KEY must be set to a strong secret in production (DEBUG=False). "
                    'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
                )
            else:
                # FIX C-3: Warn even in DEBUG so misconfigured staging deployments are visible
                _logger.warning(
                    "INTERNAL_API_KEY is using a sentinel/default value. "
                    "This is only acceptable in local development (DEBUG=True). "
                    "Never deploy to staging/production with this value."
                )
        return self

    # ── Computed Properties ───────────────────────────────────────────────────

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def debug(self) -> bool:
        return self.DEBUG

    @property
    def internal_api_key(self) -> str:
        return self.INTERNAL_API_KEY.get_secret_value()

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL.lower()

    @property
    def is_postgres(self) -> bool:
        return (
            "postgresql" in self.DATABASE_URL.lower()
            or "postgres" in self.DATABASE_URL.lower()
        )

    @property
    def live_trading_enabled(self) -> bool:
        """True only when all CLOB credentials are present."""
        return all(
            [
                self.POLYMARKET_PRIVATE_KEY.get_secret_value(),
                self.POLYMARKET_API_KEY.get_secret_value(),
                self.POLYMARKET_SECRET.get_secret_value(),
                self.POLYMARKET_PASSPHRASE.get_secret_value(),
            ]
        )


@lru_cache
def get_settings() -> Settings:
    _settings = Settings()
    logger = logging.getLogger(__name__)
    # Minimal startup log — no secrets, no noise
    logger.info(
        "POLYGOD settings loaded | MODE=%s | DB_DRIVER=%s | DEBUG=%s",
        _settings.POLYGOD_MODE,
        _settings.DATABASE_URL.split(":")[0],  # e.g. "sqlite+aiosqlite"
        _settings.DEBUG,
    )
    if _settings.is_sqlite and not _settings.DEBUG:
        logger.warning(
            "Using SQLite in non-DEBUG mode. Consider PostgreSQL for production workloads."
        )
    if not _settings.GEMINI_API_KEY.get_secret_value():
        logger.warning("GEMINI_API_KEY not set — AI agents disabled")
    if not _settings.NEWS_API_KEY.get_secret_value():
        logger.warning("NEWS_API_KEY not set — news aggregation disabled")
    if (
        _settings.POLYGOD_MODE >= 3
        and not _settings.POLYMARKET_PRIVATE_KEY.get_secret_value()
    ):
        logger.warning(
            "POLYGOD_MODE=3 (BEAST) but POLYMARKET_PRIVATE_KEY is not set. "
            "Live trades will fall back to paper execution."
        )
    return _settings


settings = get_settings()
