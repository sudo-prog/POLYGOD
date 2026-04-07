import logging
import os
from datetime import datetime
from typing import Dict, Optional

from litellm import Router
from pydantic import BaseModel

logger = logging.getLogger("concierge")


class Deployment(BaseModel):
    model: str
    api_key: str
    provider: str
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    backup_keys: list[str] = []


class LLMConcierge:
    def __init__(self):
        self.router = Router(
            model_list=[
                # Current primary (high strength)
                {
                    "model": "gemini/gemini-2.5-pro",
                    "api_key": os.getenv("GEMINI_API_KEY"),
                    "rpm": 10,
                    "tpm": 1_000_000,
                    "provider": "gemini",
                },
                # Fast fallback
                {
                    "model": "groq/llama-3.3-70b-versatile",
                    "api_key": os.getenv("GROQ_API_KEY"),
                    "provider": "groq",
                },
                # High-volume / strong reasoning
                {
                    "model": "openrouter/deepseek/deepseek-r1",
                    "api_key": os.getenv("OPENROUTER_API_KEY"),
                    "provider": "openrouter",
                },
                # Add any new LLM here — no other code changes needed
                # Example: {"model": "cerebras/llama-4-scout", "api_key": os.getenv("CEREBRAS_API_KEY"), "provider": "cerebras"},
            ],
            routing_strategy="latency-based-routing",  # or "usage-based-routing"
            fallback_dict={"gemini/*": ["groq/*", "openrouter/*"]},
            retry_policy={"max_retries": 3, "allowed_fails": 2},
            num_retries=3,
            allowed_fails=2,
        )
        self.key_status: Dict[str, dict] = {}

    async def health_check_all_keys(self):
        """Periodic security sweep — run via APScheduler"""
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
                if deployment.get("backup_keys"):
                    self._rotate_key(deployment)

    def _rotate_key(self, deployment: dict):
        """Rotate to backup key if available"""
        logger.warning(f"🔄 Rotating key for {deployment['model']}")
        # Extend with secrets manager / multiple env vars if needed
        backup_env = deployment.get("backup_keys", [])
        if backup_env:
            backup_key = os.getenv(backup_env[0])
            if backup_key:
                deployment["api_key"] = backup_key
                logger.info(f"✅ Rotated to backup key for {deployment['model']}")

    async def get_secure_completion(self, model_group: str, messages: list, **kwargs):
        """Every agent LLM call MUST go through here — keys never exposed"""
        return await self.router.acompletion(
            model=model_group, messages=messages, **kwargs
        )

    def get_security_status(self):
        """For /api/concierge/status endpoint"""
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


# Global instance (import wherever needed)
concierge = LLMConcierge()
