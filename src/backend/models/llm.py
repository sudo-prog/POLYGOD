"""
SQLAlchemy models for the LLM Hub — Provider, AgentConfig, UsageLog.

Changes vs previous version:
  - FIXED H3: Encryption key is now read from settings instead of os.getenv()
              with a Fernet.generate_key() default. The previous implementation
              generated a NEW random key on every cold start when ENCRYPTION_KEY
              was not set, permanently corrupting all previously-encrypted API
              keys in the database after the first restart.
              Now it uses the consistent (if insecure) dev default from Settings,
              and logs a CRITICAL warning when the insecure default is active.
"""

import logging
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.database import Base

logger = logging.getLogger(__name__)


def _build_cipher() -> Fernet:
    """
    Build the Fernet cipher using the ENCRYPTION_KEY from settings.

    Importing settings here (instead of at module level) avoids a circular
    import: database.py → models_llm.py → config.py → database.py.
    """
    from src.backend.config import settings

    raw = settings.ENCRYPTION_KEY.get_secret_value()

    if "INSECURE_DEV_KEY" in raw:
        logger.critical(
            "ENCRYPTION_KEY is using the insecure development default. "
            "LLM Hub API keys are NOT securely encrypted. "
            "Set ENCRYPTION_KEY in your .env — generate with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )

    # Fernet requires a 32-byte url-safe base64-encoded key.
    # If the provided key isn't valid Fernet format (e.g. the dev placeholder),
    # derive a stable key from it so the app at least starts.
    try:
        return Fernet(raw.encode() if isinstance(raw, str) else raw)
    except Exception:
        import base64
        import hashlib

        derived = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
        logger.warning(
            "ENCRYPTION_KEY is not valid Fernet format — "
            "using SHA-256 derived key. Set a proper Fernet key in production."
        )
        return Fernet(derived)


# Build cipher once at module import time.
cipher = _build_cipher()


class Provider(Base):
    """An LLM provider (Gemini, Groq, Puter, OpenRouter, etc.)."""

    __tablename__ = "llm_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    models_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    uptime_24h: Mapped[str] = mapped_column(String(20), default="100%")
    avg_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_today: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def encrypt_key(self, raw_key: str) -> None:
        """Encrypt and store an API key."""
        self.api_key_encrypted = cipher.encrypt(raw_key.encode()).decode()

    def decrypt_key(self) -> str | None:
        """Decrypt and return the stored API key, or None on failure."""
        if not self.api_key_encrypted:
            return None
        try:
            return cipher.decrypt(self.api_key_encrypted.encode()).decode()
        except InvalidToken:
            logger.error(
                "Provider %r: API key decryption failed — "
                "ENCRYPTION_KEY may have changed since the key was stored.",
                self.name,
            )
            return None

    def to_dict(self, include_key: bool = False) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "base_url": self.base_url,
            "models": self.models_json or [],
            "status": self.status,
            "uptime_24h": self.uptime_24h,
            "avg_speed": self.avg_speed,
            "tokens_today": self.tokens_today,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_key:
            data["api_key"] = self.decrypt_key()
        return data


class AgentConfig(Base):
    """Per-agent LLM configuration and model overrides."""

    __tablename__ = "agent_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    overrides_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "overrides": self.overrides_json or {},
        }


class UsageLog(Base):
    """LLM token usage log — one row per LLM call."""

    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "agent_name": self.agent_name,
            "market_id": self.market_id,
        }
