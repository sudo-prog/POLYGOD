"""
Dynamic skill loader for POLYGOD AI.

Skills are markdown files loaded on-demand.
The system prompt stays lean — skills are injected only when triggered.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent / "skills"

# Keyword → skill mapping (loaded from SKILLS_INDEX.md if present, else hardcoded)
SKILL_TRIGGERS: dict[str, str] = {
    # Error/fix skills
    "traceback": "fix_python",
    "exception": "fix_python",
    "error": "fix_python",
    "importerror": "fix_python",
    "syntax": "fix_python",
    "crash": "fix_python",
    "typeerror": "fix_python",
    "attributeerror": "fix_python",
    # UI skills
    "react": "fix_ui",
    "typescript": "fix_ui",
    "tsx": "fix_ui",
    "component": "fix_ui",
    "frontend": "fix_ui",
    "css": "fix_ui",
    "tailwind": "fix_ui",
    # Database skills
    "database": "fix_db",
    "migration": "fix_db",
    "alembic": "fix_db",
    "sqlalchemy": "fix_db",
    "sqlite": "fix_db",
    "postgres": "fix_db",
    # Docker skills
    "docker": "fix_docker",
    "container": "fix_docker",
    "compose": "fix_docker",
    "healthcheck": "fix_docker",
    # Market analysis
    "analyse": "analyse_market",
    "analyze": "analyse_market",
    "edge": "analyse_market",
    "kelly": "analyse_market",
    "probability": "analyse_market",
    # Deploy
    "deploy": "deploy",
    "production": "deploy",
    "startup": "deploy",
    # Backtest
    "backtest": "backtest",
    "history": "backtest",
    "sharpe": "backtest",
    # Playwright
    "browser": "playwright",
    "scrape": "playwright",
    "navigate": "playwright",
    "screenshot": "playwright",
    "playwright": "playwright",
    # Memory
    "mempalace": "memory",
    "mem0": "memory",
    "remember": "memory",
    "memory": "memory",
    # Telegram
    "telegram": "telegram",
    "bot": "telegram",
    "command": "telegram",
}


def detect_needed_skills(message: str) -> list[str]:
    """Detect which skills are needed based on message content."""
    message_lower = message.lower()
    needed: set[str] = set()

    for keyword, skill in SKILL_TRIGGERS.items():
        if keyword in message_lower:
            needed.add(skill)

    return list(needed)


def load_skill(skill_name: str) -> str:
    """Load a skill file by name. Returns empty string if not found."""
    skill_file = SKILLS_DIR / f"{skill_name}.md"

    if not skill_file.exists():
        logger.warning(f"Skill file not found: {skill_file}")
        return f"# SKILL: {skill_name.upper()}\nSkill file not found at {skill_file}"

    try:
        return skill_file.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to load skill {skill_name}: {e}")
        return ""


def load_skills_for_message(message: str) -> tuple[list[str], str]:
    """
    Auto-detect and load skills for a given message.

    Returns:
        (skill_names, combined_skill_content)
    """
    skill_names = detect_needed_skills(message)
    if not skill_names:
        return [], ""

    combined = "\n\n---\n\n".join(
        f"[SKILL LOADED: {name.upper()}]\n\n{load_skill(name)}" for name in skill_names
    )

    logger.info(f"Skills loaded: {skill_names}")
    return skill_names, combined


def list_available_skills() -> list[dict]:
    """List all available skill files."""
    skills = []
    for skill_file in SKILLS_DIR.glob("*.md"):
        if skill_file.name == "SKILLS_INDEX.md":
            continue
        content = skill_file.read_text(encoding="utf-8")
        # Extract first line as description
        first_line = content.split("\n")[0].lstrip("# ").strip()
        skills.append(
            {
                "name": skill_file.stem,
                "file": str(skill_file),
                "description": first_line,
            }
        )
    return sorted(skills, key=lambda x: x["name"])
