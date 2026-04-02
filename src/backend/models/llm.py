"""
SQLAlchemy models for the LLM Hub — Provider, AgentConfig, UsageLog.

Handles multi-provider LLM management, per-agent configurations,
and token usage tracking with encrypted API key storage.
"""

import os
from datetime import datetime

from cryptography.fernet import Fernet
from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.database import Base

# Encryption for API keys — uses ENCRYPTION_KEY env var, generates if missing
_key = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher = Fernet(_key.encode() if isinstance(_key, str) else _key)


class Provider(Base):
    """Model representing an LLM provider (Gemini, Groq, Puter, OpenRouter, etc.)."""

    __tablename__ = "llm_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # list of available model IDs
    models_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="unknown")  # ✅ / ⚠️ / 🔴
    uptime_24h: Mapped[str] = mapped_column(String(20), default="100%")
    avg_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)  # tokens/sec
    tokens_today: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def encrypt_key(self, raw_key: str) -> None:
        """Encrypt and store an API key."""
        self.api_key_encrypted = cipher.encrypt(raw_key.encode()).decode()

    def decrypt_key(self) -> str | None:
        """Decrypt and return the stored API key."""
        if not self.api_key_encrypted:
            return None
        return str(cipher.decrypt(self.api_key_encrypted.encode()).decode())

    def to_dict(self, include_key: bool = False) -> dict:
        """Convert model to dictionary."""
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
    """Model for per-agent LLM configuration and overrides."""

    __tablename__ = "agent_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # e.g. {"volume_threshold": 10000}
    overrides_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "overrides": self.overrides_json or {},
        }


class UsageLog(Base):
    """Model for tracking LLM token usage per provider/agent/market."""

    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "agent_name": self.agent_name,
            "market_id": self.market_id,
        }
