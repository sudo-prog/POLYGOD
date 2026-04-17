"""
Dynamic skill loader for POLYGOD AI.

Supports both the old markdown-based format and the new structured format
with YAML frontmatter and bundled resources. Skills are loaded on-demand to
keep the system prompt lean.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# Support both old and new skill directories
SKILLS_DIR_OLD = Path(__file__).parent.parent / "skills"  # Old format: *.md files
SKILLS_DIR_NEW = (
    Path(__file__).parent.parent / "skills_new"
)  # New format: skill-name/ directories

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


def _parse_yaml_frontmatter(content: str) -> tuple[Optional[Dict[str, Any]], str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---\n"):
        return None, content

    # Find the end of frontmatter
    end_pos = content.find("\n---\n", 4)
    if end_pos == -1:
        return None, content

    frontmatter_text = content[4:end_pos]
    markdown_content = content[end_pos + 5 :]

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        return frontmatter, markdown_content
    except Exception as e:
        logger.warning(f"Failed to parse YAML frontmatter: {e}")
        return None, content


def _load_skill_old_format(skill_name: str) -> Optional[str]:
    """Load skill from old format (single .md file)."""
    skill_file = SKILLS_DIR_OLD / f"{skill_name}.md"

    if not skill_file.exists():
        return None

    try:
        return skill_file.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to load old format skill {skill_name}: {e}")
        return None


def _load_skill_new_format(skill_name: str) -> Optional[tuple[Dict[str, Any], str]]:
    """Load skill from new format (directory with SKILL.md)."""
    skill_dir = SKILLS_DIR_NEW / skill_name
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.exists():
        return None

    try:
        content = skill_file.read_text(encoding="utf-8")
        frontmatter, markdown_content = _parse_yaml_frontmatter(content)

        if frontmatter:
            return frontmatter, markdown_content
        else:
            # Fallback: treat as old format
            return {"name": skill_name, "description": f"Skill: {skill_name}"}, content

    except Exception as e:
        logger.error(f"Failed to load new format skill {skill_name}: {e}")
        return None


def load_skill(skill_name: str) -> str:
    """Load a skill by name. Supports both old and new formats. Returns empty string if not found."""
    # Try new format first
    new_format = _load_skill_new_format(skill_name)
    if new_format:
        frontmatter, content = new_format
        skill_title = frontmatter.get("name", skill_name).replace("-", " ").title()
        description = frontmatter.get("description", f"Skill: {skill_name}")

        # Format as structured skill with metadata
        formatted_content = (
            f"# {skill_title}\n\n**Description:** {description}\n\n{content}"
        )
        logger.info(f"Loaded new format skill: {skill_name}")
        return formatted_content

    # Fall back to old format
    old_content = _load_skill_old_format(skill_name)
    if old_content:
        logger.info(f"Loaded old format skill: {skill_name}")
        return old_content

    logger.warning(f"Skill '{skill_name}' not found in either format")
    return (
        f"# SKILL: {skill_name.upper()}\n"
        f"Skill file not found in {SKILLS_DIR_OLD} or {SKILLS_DIR_NEW}"
    )


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
    """List all available skills from both old and new formats."""
    skills = []

    # Load old format skills
    for skill_file in SKILLS_DIR_OLD.glob("*.md"):
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
                "format": "old",
            }
        )

    # Load new format skills
    for skill_dir in SKILLS_DIR_NEW.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        content = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = _parse_yaml_frontmatter(content)

        if frontmatter:
            name = frontmatter.get("name", skill_dir.name)
            description = frontmatter.get("description", f"Skill: {skill_dir.name}")
        else:
            name = skill_dir.name
            description = f"Skill: {skill_dir.name}"

        skills.append(
            {
                "name": name,
                "file": str(skill_file),
                "description": description,
                "format": "new",
                "directory": str(skill_dir),
            }
        )

    return sorted(skills, key=lambda x: x["name"])
