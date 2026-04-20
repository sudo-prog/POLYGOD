#!/usr/bin/env python3
"""Validate the llm_manager skill installation."""

import sys


def validate_llm_manager():
    """Validate llm_manager skill can be loaded."""
    try:
        # Add project root to path
        import sys
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # Test imports
        from src.backend.services.llm_concierge import concierge

        # Test provider listing
        providers = concierge.list_providers()
        print(f"✓ Loaded {len(providers)} providers")

        # Test free provider detection
        free = concierge.get_free_providers()
        paid = concierge.get_paid_providers()
        print(f"  - {len(free)} free/local providers")
        print(f"  - {len(paid)} paid providers")

        # Test default provider
        print(f"  - Default: {concierge.default_provider}")

        # Test status
        status = concierge.get_security_status()
        print(
            f"  - Health: {status['healthy_keys']}/{status['keys_monitored']} providers healthy"
        )

        # Check for litellm
        try:
            import litellm

            print(f"✓ LiteLLM version: {litellm.__version__}")
        except ImportError:
            print("⚠ LiteLLM not installed")

        # Check for Ollama (optional)
        try:
            import asyncio

            import httpx

            async def check_ollama():
                try:
                    async with httpx.AsyncClient(timeout=2.0) as client:
                        resp = await client.get("http://localhost:11434/api/tags")
                        return resp.status_code == 200
                except:
                    return False

            if asyncio.run(check_ollama()):
                print("✓ Ollama running locally")
            else:
                print("○ Ollama not running (optional)")
        except ImportError:
            print("○ httpx not available for Ollama check")

        print("\n✅ llm_manager skill validation PASSED")
        return True

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False


if __name__ == "__main__":
    success = validate_llm_manager()
    sys.exit(0 if success else 1)
