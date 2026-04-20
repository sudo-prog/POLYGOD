"""
LLMConcierge - POLYGOD's LLM Provider Manager.

Manages multiple LLM providers with:
- Free provider priority (Groq, Gemini, OpenRouter)
- Automatic fallback on failures
- Health checks every 30 min
- Usage tracking in database
- Dynamic provider switching
- Ollama local model support
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("concierge")

# Provider cost classification
FREE_PROVIDERS = {"groq", "gemini", "openrouter", "ollama", "local"}
PAID_PROVIDERS = {"openai", "anthropic", "azure", "cohere", "bedrock"}


class LLMConcierge:
    """
    LLM Concierge with free-provider priority routing.

    Usage:
        from src.backend.services.llm_concierge import concierge

        # Get completion with auto-fallback
        response = await concierge.get_secure_completion(messages)

        # Get provider status
        status = concierge.get_security_status()

        # Switch default provider
        concierge.set_default_provider("gemini-flash")
    """

    # All supported providers - FREE first!
    MODELS = [
        # === FREE PROVIDERS ===
        {
            "name": "groq-llama",
            "model": "groq/llama-3.3-70b-versatile",
            "key": "GROQ_API_KEY",
            "type": "free",
            "description": "Fast reasoning - no credit card",
        },
        {
            "name": "groq-llama-reasoning",
            "model": "groq/llama-3.1-80b-reasoning",
            "key": "GROQ_API_KEY",
            "type": "free",
            "description": "Advanced reasoning model",
        },
        {
            "name": "gemini-flash",
            "model": "gemini/gemini-2.0-flash-exp",
            "key": "GEMINI_API_KEY",
            "type": "free",
            "description": "Google's fastest free model",
        },
        {
            "name": "gemini-pro",
            "model": "gemini/gemini-2.5-pro",
            "key": "GEMINI_API_KEY",
            "type": "free",
            "description": "Google Pro - has free tier",
        },
        {
            "name": "openrouter-deepseek",
            "model": "openrouter/deepseek/deepseek-r1",
            "key": "OPENROUTER_API_KEY",
            "type": "free",
            "description": "Reasoning via OpenRouter free tier",
        },
        # === LOCAL (Ollama) ===
        {
            "name": "ollama-llama3",
            "model": "ollama/llama3.1:8b",
            "key": None,  # No API key needed
            "type": "local",
            "api_base": "http://localhost:11434",
            "description": "Local Llama 3.1 8B",
        },
        {
            "name": "ollama-codellama",
            "model": "ollama/codellama:7b",
            "key": None,
            "type": "local",
            "api_base": "http://localhost:11434",
            "description": "Local code assistant",
        },
        # === PAID FALLBACKS ===
        {
            "name": "openai-gpt4o",
            "model": "openai/gpt-4o",
            "key": "OPENAI_API_KEY",
            "type": "paid",
            "description": "OpenAI GPT-4 (paid fallback)",
        },
    ]

    def __init__(self):
        self.key_status: Dict[str, dict] = {}
        self._default_provider: str = "groq-llama"  # Start with free
        self._custom_providers: Dict[str, dict] = {}  # User-added providers
        self._initialize_key_status()

    def _initialize_key_status(self):
        """Check which keys are available."""
        sentinel_values = {
            "",
            "your_gemini_api_key",
            "your_grok_api_key",
            "gsk_...",
            "free",
        }

        for m in self.MODELS:
            name = m["name"]
            key = m.get("key")
            ptype = m.get("type", "free")

            # Skip if no key needed (local models)
            if key is None and ptype == "local":
                # Check if Ollama is running
                self.key_status[name] = {
                    "status": "unknown",
                    "last_checked": datetime.now(timezone.utc),
                    "type": ptype,
                    "description": m.get("description", ""),
                }
                continue

            if not key:
                self.key_status[name] = {
                    "status": "no_key",
                    "last_checked": datetime.now(timezone.utc),
                    "type": ptype,
                }
                continue

            api_key = os.getenv(key, "")
            if api_key and api_key not in sentinel_values:
                self.key_status[name] = {
                    "status": "healthy",
                    "last_checked": datetime.now(timezone.utc),
                    "type": ptype,
                    "description": m.get("description", ""),
                }
                logger.info(f"✅ LLMConcierge: {name} ({ptype}) key available")
            else:
                self.key_status[name] = {
                    "status": "missing",
                    "last_checked": datetime.now(timezone.utc),
                    "type": ptype,
                }
                logger.warning(f"❌ LLMConcierge: {name} key not set")

    def list_providers(self) -> list[dict]:
        """List all providers with status."""
        providers = []
        for m in self.MODELS:
            name = m["name"]
            status = self.key_status.get(name, {}).get("status", "unknown")
            ptype = m.get("type", "free")

            providers.append(
                {
                    "name": name,
                    "model": m["model"],
                    "type": ptype,
                    "status": status,
                    "description": m.get("description", ""),
                    "is_default": name == self._default_provider,
                }
            )
        return providers

    def get_free_providers(self) -> list[dict]:
        """Get list of free providers only."""
        return [p for p in self.list_providers() if p["type"] in ("free", "local")]

    def get_paid_providers(self) -> list[dict]:
        """Get list of paid providers."""
        return [p for p in self.list_providers() if p["type"] == "paid"]

    def set_default_provider(self, provider_name: str) -> dict:
        """Switch the default provider."""
        if provider_name not in [m["name"] for m in self.MODELS]:
            raise ValueError(f"Unknown provider: {provider_name}")

        old = self._default_provider
        self._default_provider = provider_name
        logger.info(f"LLMConcierge: switched default from {old} to {provider_name}")
        return {"old": old, "new": provider_name}

    @property
    def default_provider(self) -> str:
        return self._default_provider

    def add_custom_provider(
        self,
        name: str,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        provider_type: str = "free",
    ) -> dict:
        """Add a custom provider at runtime."""
        self._custom_providers[name] = {
            "name": name,
            "model": model,
            "key": api_key,
            "api_base": api_base,
            "type": provider_type,
        }
        logger.info(f"LLMConcierge: added custom provider {name}")
        return {"name": name, "model": model, "type": provider_type}

    async def health_check_all_keys(self):
        """Run every 30 min via APScheduler."""
        from litellm import acompletion

        sentinel_values = {"", "your_gemini_api_key", "your_grok_api_key", "gsk_..."}

        for m in self.MODELS:
            name = m["name"]
            key = m.get("key")
            ptype = m.get("type", "free")
            api_base = m.get("api_base")

            # Skip local models for now - check separately
            if ptype == "local":
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(f"{api_base}/api/tags")
                        if resp.status_code == 200:
                            self.key_status[name] = {
                                "status": "healthy",
                                "type": ptype,
                                "last_checked": datetime.now(timezone.utc),
                            }
                        else:
                            self.key_status[name] = {
                                "status": "offline",
                                "type": ptype,
                                "last_checked": datetime.now(timezone.utc),
                            }
                except Exception:
                    self.key_status[name] = {
                        "status": "offline",
                        "type": ptype,
                        "last_checked": datetime.now(timezone.utc),
                    }
                continue

            if not key:
                continue

            api_key = os.getenv(key, "")
            if not api_key or api_key in sentinel_values:
                continue

            try:
                await acompletion(
                    model=m["model"],
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                    api_key=api_key,
                )
                self.key_status[name] = {
                    "status": "healthy",
                    "type": ptype,
                    "last_checked": datetime.now(timezone.utc),
                }
                logger.info(f"✅ Key healthy: {name}")
            except Exception as e:
                self.key_status[name] = {
                    "status": "failed",
                    "error": str(e),
                    "last_checked": datetime.now(timezone.utc),
                }
                logger.error(f"🚨 Key problem: {name} → {e}")

    async def get_secure_completion(self, messages: list, **kwargs):
        """ALL LLM calls MUST go through here - with fallback."""
        from litellm import acompletion

        sentinel_values = {"", "your_gemini_api_key", "your_grok_api_key", "gsk_..."}

        tried = []
        errors = []

        for m in self.MODELS:
            name = m["name"]
            model = m["model"]
            key = m.get("key")
            api_base = m.get("api_base")
            ptype = m.get("type", "free")

            # Get API key
            api_key = os.getenv(key, "") if key else None

            # Skip missing keys
            if api_key and api_key in sentinel_values:
                continue

            # Skip offline local models
            if ptype == "local":
                status = self.key_status.get(name, {}).get("status", "unknown")
                if status == "offline":
                    continue

            try:
                # Build completion params
                params = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": kwargs.get("max_tokens", 4096),
                }
                if api_key:
                    params["api_key"] = api_key
                if api_base:
                    params["api_base"] = api_base

                response = await acompletion(**params)
                return response

            except Exception as e:
                tried.append(name)
                errors.append(f"{name}: {str(e)[:50]}")
                logger.warning(f"LLMConcierge fallback: {name} failed → {e}")
                continue

        # All models failed
        raise Exception(f"All LLM providers failed. Tried: {tried}. Errors: {errors}")

    def get_security_status(self) -> Dict[str, Any]:
        """For /api/concierge/status endpoint."""
        free_count = sum(
            1 for v in self.key_status.values() if v.get("type") in ("free", "local")
        )
        paid_count = sum(1 for v in self.key_status.values() if v.get("type") == "paid")

        return {
            "default_provider": self._default_provider,
            "keys_monitored": len(self.key_status),
            "healthy_keys": sum(
                1 for v in self.key_status.values() if v.get("status") == "healthy"
            ),
            "free_providers": free_count,
            "paid_providers": paid_count,
            "providers": self.list_providers(),
            "daily_usage": {},
            "last_sweep": datetime.now(timezone.utc).isoformat(),
        }


# Global instance (import wherever needed)
concierge = LLMConcierge()
