# src/backend/llm_router.py
from litellm import Router
import os
import asyncio

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
        self.router = Router(
            model_list=[
                {"model": "puter/claude-sonnet-4.5", "api_base": "https://api.puter.com/ai/openai/v1", "api_key": "sk-free-puter"},  # ZERO cost
                {"model": "openrouter/free", "api_base": "https://openrouter.ai/api/v1", "api_key": os.getenv("OPENROUTER_API_KEY")},
                {"model": "gemini/gemini-2.5-flash", "api_key": os.getenv("GEMINI_API_KEY")},
                {"model": "groq/llama-3.3-70b", "api_key": os.getenv("GROQ_API_KEY")},
                {"model": "nvidia-auto", "api_key": os.getenv("NVIDIA_API_KEY")},  # 31 free APIs, latency winner
            ],
            routing_strategy="latency-based-routing",  # picks fastest free model
            fallbacks=["openrouter/free", "gemini/gemini-2.5-flash", "groq/llama-3.3-70b"],
            retry_after=60,  # cooldown on rate limits
        )
        self.token_budget = 0

    @traceable
    async def route(self, prompt: str, agent_name: str, priority: str = "cheap"):
        # Mem0 daily guard
        usage = mem0.search("daily_token_usage", user_id="polygod_swarm")
        if usage and int(usage[0].get("content", 0)) > 900_000:
            # emergency fallback to Puter only
            return await self.router.acompletion(model="puter/claude-sonnet-4.5", messages=[{"role": "user", "content": prompt}])

        model = "puter/claude-sonnet-4.5" if priority == "cheap" else "openrouter/free"
        if "evolution" in agent_name.lower():
            model = "nvidia-auto"  # fastest for tournaments

        response = await self.router.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            metadata={"agent": agent_name, "priority": priority}
        )
        
        # Auto Mem0 write + budget track
        mem0.add(f"Used {len(prompt)} tokens on {model} for {agent_name}", user_id="polygod_swarm")
        self.token_budget += len(prompt)
        return response.choices[0].message.content

router = GodTierLLMRouter()