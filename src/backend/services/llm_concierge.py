import logging
import os
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger("concierge")


class LLMConcierge:
    """
    Simple LLM Concierge with fallback routing.

    Uses direct LLM calls with simple fallback logic instead of litellm Router
    (to avoid complex litellm.router configuration issues).
    """

    # Model priority list (tried in order)
    MODELS = [
        {
            "name": "gemini-pro",
            "model": "gemini/gemini-2.5-pro",
            "key": "GEMINI_API_KEY",
        },
        {
            "name": "groq-llama",
            "model": "groq/llama-3.3-70b-versatile",
            "key": "GROQ_API_KEY",
        },
        {
            "name": "openrouter-deepseek",
            "model": "openrouter/deepseek/deepseek-r1",
            "key": "OPENROUTER_API_KEY",
        },
    ]

    def __init__(self):
        self.key_status: Dict[str, dict] = {}
        self._initialize_key_status()

    def _initialize_key_status(self):
        """Check which keys are available."""
        sentinel_values = (
            "",
            "your_gemini_api_key",
            "your_grok_api_key",
            "gsk_...",
            "free",
        )
        for m in self.MODELS:
            key = os.getenv(m["key"], "")
            if key and key not in sentinel_values:
                self.key_status[m["name"]] = {
                    "status": "healthy",
                    "last_checked": datetime.utcnow(),
                }
                logger.info(f"✅ LLMConcierge: {m['name']} key available")
            else:
                self.key_status[m["name"]] = {
                    "status": "missing",
                    "last_checked": datetime.utcnow(),
                }
                logger.warning(f"❌ LLMConcierge: {m['name']} key not set")

    async def health_check_all_keys(self):
        """Run every 30 min via APScheduler"""
        from litellm import acompletion

        sentinel_values = (
            "",
            "your_gemini_api_key",
            "your_grok_api_key",
            "gsk_...",
            "free",
        )
        for m in self.MODELS:
            try:
                api_key = os.getenv(m["key"], "")
                if not api_key or api_key in sentinel_values:
                    continue

                await acompletion(
                    model=m["model"],
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                    api_key=api_key,
                )
                self.key_status[m["name"]] = {
                    "status": "healthy",
                    "last_checked": datetime.utcnow(),
                }
                logger.info(f"✅ Key healthy: {m['name']}")
            except Exception as e:
                self.key_status[m["name"]] = {
                    "status": "failed",
                    "error": str(e),
                    "last_checked": datetime.utcnow(),
                }
                logger.error(f"🚨 Key problem: {m['name']} → {e}")

    async def get_secure_completion(self, messages: list, **kwargs):
        """ALL debate nodes MUST call through here - with fallback"""
        from litellm import acompletion

        sentinel_values = (
            "",
            "your_gemini_api_key",
            "your_grok_api_key",
            "gsk_...",
            "free",
        )

        # Try each model in priority order
        for m in self.MODELS:
            api_key = os.getenv(m["key"], "")
            if not api_key or api_key in sentinel_values:
                continue

            try:
                response = await acompletion(
                    model=m["model"], messages=messages, api_key=api_key, **kwargs
                )
                return response
            except Exception as e:
                logger.warning(f"LLMConcierge fallback: {m['name']} failed → {e}")
                continue

        # All models failed
        raise Exception("All LLM providers failed")

    def get_security_status(self) -> Dict[str, Any]:
        """For /api/concierge/status endpoint"""
        return {
            "keys_monitored": len(self.key_status),
            "healthy_keys": sum(
                1 for v in self.key_status.values() if v["status"] == "healthy"
            ),
            "last_sweep": datetime.utcnow(),
            "warnings": [
                k for k, v in self.key_status.items() if v["status"] != "healthy"
            ],
        }


# Global instance (import wherever needed)
concierge = LLMConcierge()
