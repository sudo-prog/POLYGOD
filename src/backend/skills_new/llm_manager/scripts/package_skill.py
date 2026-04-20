#!/usr/bin/env python3
"""Package the llm_manager skill for distribution."""

import json
import sys
from pathlib import Path


def package_skill():
    """Package the skill into a distributable format."""
    skill_dir = Path(__file__).parent.parent

    # Validate required files exist
    required = ["SKILL.md", "llm_manager.skill", "_meta.json"]
    missing = [f for f in required if not (skill_dir / f).exists()]

    if missing:
        print(f"❌ Missing files: {missing}")
        return False

    # Validate _meta.json
    try:
        with open(skill_dir / "_meta.json") as f:
            meta = json.load(f)
        print(f"✓ Skill: {meta['name']} v{meta['version']}")
        print(f"  - Description: {meta['description']}")
    except Exception as e:
        print(f"❌ Invalid _meta.json: {e}")
        return False

    # Check scripts
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        scripts = list(scripts_dir.glob("*.py"))
        print(f"  - Scripts: {len(scripts)}")

    print(f"\n✅ Package ready at: {skill_dir}")
    print("\nTo use this skill:")
    print("  1. Install litellm: uv add litellm")
    print("  2. Set GROQ_API_KEY in .env (free key from console.groq.com)")
    print("  3. Start Ollama locally (optional): ollama serve")
    print("  4. Validate: uv run python scripts/validate_skill.py")

    return True


if __name__ == "__main__":
    success = package_skill()
    sys.exit(0 if success else 1)
