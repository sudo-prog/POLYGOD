#!/usr/bin/env python3
"""
Validate github_mcp skill structure and content.
"""

import json
from pathlib import Path


def validate_skill():
    """Validate the github_mcp skill structure."""
    skill_dir = Path(__file__).parent.parent
    results = {"passed": [], "failed": []}

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        results["failed"].append("SKILL.md not found")
        return results

    with open(skill_md, "r") as f:
        content = f.read()

    if not content.startswith("---"):
        results["failed"].append("SKILL.md must start with frontmatter (---)")
    else:
        results["passed"].append("SKILL.md starts with valid frontmatter")

    lines = content.split("\n")
    if len(lines) > 1 and lines[0] == "---":
        end_idx = None
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                end_idx = i
                break

        if end_idx:
            frontmatter_text = "\n".join(lines[1:end_idx])
            frontmatter = {}
            for line in frontmatter_text.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip()

            if "name" in frontmatter:
                results["passed"].append("Frontmatter has 'name' field")
            else:
                results["failed"].append("Frontmatter missing 'name' field")

            if "description" in frontmatter:
                results["passed"].append("Frontmatter has 'description' field")
            else:
                results["failed"].append("Frontmatter missing 'description' field")

    meta_file = skill_dir / "_meta.json"
    if not meta_file.exists():
        results["failed"].append("_meta.json not found")
    else:
        with open(meta_file, "r") as f:
            meta = json.load(f)

        if "id" in meta and isinstance(meta["id"], int):
            results["passed"].append("_meta.json has valid 'id' field")
        else:
            results["failed"].append("_meta.json missing or invalid 'id' field")

        if "version" in meta and isinstance(meta["version"], str):
            results["passed"].append("_meta.json has valid 'version' field")
        else:
            results["failed"].append("_meta.json missing or invalid 'version' field")

    return results


if __name__ == "__main__":
    results = validate_skill()
    print("=== Validation Results ===")
    print(f"\nPassed ({len(results['passed'])}):")
    for item in results["passed"]:
        print(f"  ✓ {item}")

    if results["failed"]:
        print(f"\nFailed ({len(results['failed'])}):")
        for item in results["failed"]:
            print(f"  ✗ {item}")
        exit(1)
    else:
        print("\nAll validations passed!")
        exit(0)
