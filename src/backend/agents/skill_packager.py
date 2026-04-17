#!/usr/bin/env python3
"""
Skill packaging utilities for POLYGOD.

Supports packaging skills into .skill files (zip archives) and unpacking them.
"""

import json
import zipfile
from pathlib import Path
from typing import Any, Dict

import yaml


def package_skill(skill_path: str) -> Path:
    """Package a skill directory into a .skill file."""
    skill_dir = Path(skill_path)
    if not skill_dir.is_dir():
        raise ValueError(f"Skill path {skill_path} is not a directory")

    skill_name = skill_dir.name
    output_path = skill_dir.parent / f"{skill_name}.skill"

    print(f"Packaging skill: {skill_name}")

    # Create zip archive
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("."):
                arcname = file_path.relative_to(skill_dir)
                zf.write(file_path, arcname)
                print(f"  Added: {arcname}")

    print(f"\nPackaged skill to: {output_path.absolute()}")
    return output_path


def unpack_skill(skill_file: str, output_dir: str | None = None) -> Path:
    """Unpack a .skill file into a skill directory."""
    skill_file_path = Path(skill_file)
    if not skill_file_path.exists():
        raise ValueError(f"Skill file {skill_file} does not exist")

    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = skill_file_path.parent

    # Extract skill name from .skill filename
    skill_name = skill_file_path.stem
    skill_dir = output_path / skill_name

    print(f"Unpacking skill: {skill_name}")

    # Create directory if it doesn't exist
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Extract zip archive
    with zipfile.ZipFile(skill_file_path, "r") as zf:
        zf.extractall(skill_dir)
        for file_path in zf.namelist():
            print(f"  Extracted: {file_path}")

    print(f"\nUnpacked skill to: {skill_dir.absolute()}")
    return skill_dir


def validate_skill(skill_path: str) -> Dict[str, Any]:
    """Validate a skill directory structure and return metadata."""
    skill_dir = Path(skill_path)
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.exists():
        raise ValueError(f"SKILL.md not found in {skill_path}")

    content = skill_file.read_text(encoding="utf-8")

    # Parse YAML frontmatter
    if not content.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter (---)")

    end_pos = content.find("\n---\n", 4)
    if end_pos == -1:
        raise ValueError("SKILL.md missing closing frontmatter (---)")

    frontmatter_text = content[4:end_pos]
    markdown_content = content[end_pos + 5 :]

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except Exception as e:
        raise ValueError(f"Invalid YAML frontmatter: {e}")

    # Validate required fields
    required_fields = ["name", "description"]
    for field in required_fields:
        if field not in frontmatter:
            raise ValueError(f"Required field '{field}' missing from frontmatter")

    # Check bundled resources
    bundled_resources = {}
    for resource_dir in ["scripts", "references", "assets"]:
        resource_path = skill_dir / resource_dir
        if resource_path.exists():
            files = list(resource_path.rglob("*"))
            bundled_resources[resource_dir] = len([f for f in files if f.is_file()])

    result = {
        "name": frontmatter["name"],
        "description": frontmatter["description"],
        "path": str(skill_dir),
        "frontmatter": frontmatter,
        "markdown_length": len(markdown_content),
        "bundled_resources": bundled_resources,
        "valid": True,
    }

    print(f"✅ Skill '{frontmatter['name']}' is valid")
    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python skill_packager.py package <skill_directory>")
        print("  python skill_packager.py unpack <skill.skill> [output_dir]")
        print("  python skill_packager.py validate <skill_directory>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "package":
        if len(sys.argv) < 3:
            print("Usage: python skill_packager.py package <skill_directory>")
            sys.exit(1)
        package_skill(sys.argv[2])

    elif command == "unpack":
        if len(sys.argv) < 3:
            print("Usage: python skill_packager.py unpack <skill.skill> [output_dir]")
            sys.exit(1)
        output_dir = sys.argv[3] if len(sys.argv) > 3 else None
        unpack_skill(sys.argv[2], output_dir)

    elif command == "validate":
        if len(sys.argv) < 3:
            print("Usage: python skill_packager.py validate <skill_directory>")
            sys.exit(1)
        result = validate_skill(sys.argv[2])
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
