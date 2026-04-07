import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict

from litellm import Router
from pydantic import BaseModel

logger = logging.getLogger("concierge")


class LLMConcierge:
    def __init__(self):
        self.router = Router(
            model_list=[
                # Primary strong reasoning
                {
                    "model": "gemini/gemini-2.5-pro",
                    "api_key": os.getenv("GEMINI_API_KEY"),
                    "provider": "gemini",
                    "rpm": 10,
                },
                # Fast fallback
                {
                    "model": "groq/llama-3.3-70b-versatile",
                    "api_key": os.getenv("GROQ_API_KEY"),
                    "provider": "groq",
                },
                # High-volume
                {
                    "model": "openrouter/deepseek/deepseek-r1",
                    "api_key": os.getenv("OPENROUTER_API_KEY"),
                    "provider": "openrouter",
                },
                # Add more free tiers here — no code changes elsewhere
                # {"model": "cerebras/llama-4-scout", "api_key": os.getenv("CEREBRAS_API_KEY"), "provider": "cerebras"},
            ],
            routing_strategy="latency-based-routing",
            fallback_dict={"gemini/*": ["groq/*", "openrouter/*"]},
            retry_policy={"max_retries": 3, "allowed_fails": 2},
        )
        self.key_status: Dict[str, dict] = {}

    async def health_check_all_keys(self):
        """Run every 30 min via APScheduler"""
        for deployment in self.router.model_list:
            try:
                await self.router.acompletion(
                    model=deployment["model"],
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                )
                self.key_status[deployment["model"]] = {
                    "status": "healthy",
                    "last_checked": datetime.utcnow(),
                }
                logger.info(f"✅ Key healthy: {deployment['model']}")
            except Exception as e:
                self.key_status[deployment["model"]] = {
                    "status": "failed",
                    "error": str(e),
                }
                logger.error(f"🚨 Key problem: {deployment['model']} → {e}")

    async def get_secure_completion(self, messages: list, **kwargs):
        """ALL debate nodes MUST call through here"""
        return await self.router.acompletion(messages=messages, **kwargs)

    def get_security_status(self):
        return {
            "keys_monitored": len(self.key_status),
            "healthy_keys": sum(
                1 for v in self.key_status.values() if v["status"] == "healthy"
            ),
            "last_sweep": datetime.utcnow(),
            "warnings": [
                k for k, v in self.key_status.items() if v["status"] == "failed"
            ],
        }


concierge = LLMConcierge()
