# src/backend/llm_router.py
import os

from litellm import Router

try:
    from mem0 import Mem0

    mem0 = Mem0.from_config({"vector_store": {"provider": "qdrant"}})
except ImportError:
    Mem0 = None
    mem0 = None

try:
    from langsmith import traceable
except ImportError:

    def traceable(*args, **kwargs):
        def decorator(fn):
            return fn

        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator


class GodTierLLMRouter:
    def __init__(self):
        # LiteLLM router with god-tier free fallbacks (Apr 2026 meta)
        # Build model list with proper litellm format
        self.model_list = [
            {
                "model_name": "puter/claude-sonnet-4.5",
                "litellm_params": {
                    "model": "openai/claude-sonnet-4.5",
                    "api_base": "https://api.puter.com/ai/openai/v1",
                    "api_key": "sk-free-puter",
                },
            },  # ZERO cost
            {
                "model_name": "openrouter/free",
                "litellm_params": {
                    "model": "openrouter/auto",
                    "api_base": "https://openrouter.ai/api/v1",
                    "api_key": os.getenv("OPENROUTER_API_KEY", ""),
                },
            },
            {
                "model_name": "gemini/gemini-2.5-flash",
                "litellm_params": {
                    "model": "gemini/gemini-2.5-flash",
                    "api_key": os.getenv("GEMINI_API_KEY", ""),
                },
            },
            {
                "model_name": "groq/llama-3.3-70b",
                "litellm_params": {
                    "model": "groq/llama-3.3-70b",
                    "api_key": os.getenv("GROQ_API_KEY", ""),
                },
            },
            {
                "model_name": "nvidia-auto",
                "litellm_params": {
                    "model": "openai/nvidia",
                    "api_key": os.getenv("NVIDIA_API_KEY", ""),
                },
            },
        ]
        self.router = Router(
            model_list=self.model_list,
            routing_strategy="latency-based-routing",
            retry_after=60,
        )
        self.token_budget = 0

    @traceable
    async def route(self, prompt: str, agent_name: str, priority: str = "cheap"):
        # Mem0 daily guard (only if mem0 is available)
        if mem0 is not None:
            try:
                usage = mem0.search("daily_token_usage", user_id="polygod_swarm")
                if usage and int(usage[0].get("content", 0)) > 900_000:
                    # emergency fallback to Puter only
                    return await self.router.acompletion(
                        model="puter/claude-sonnet-4.5",
                        messages=[{"role": "user", "content": prompt}],
                    )
            except Exception:
                pass  # Continue without mem0 guard

        model = "puter/claude-sonnet-4.5" if priority == "cheap" else "openrouter/free"
        if "evolution" in agent_name.lower():
            model = "nvidia-auto"  # fastest for tournaments

        response = await self.router.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            metadata={"agent": agent_name, "priority": priority},
        )

        # Auto Mem0 write + budget track (only if mem0 is available)
        if mem0 is not None:
            try:
                mem0.add(
                    f"Used {len(prompt)} tokens on {model} for {agent_name}",
                    user_id="polygod_swarm",
                )
            except Exception:
                pass  # Continue without mem0 write
        self.token_budget += len(prompt)
        return response.choices[0].message.content


router = GodTierLLMRouter()
