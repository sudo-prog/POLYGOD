#!/usr/bin/env python3
"""
Package fix_python skill for distribution.
"""

import zipfile
from pathlib import Path


def package_skill(skill_path=None):
    """Package the skill into a .skill file."""
    if skill_path:
        skill_dir = Path(skill_path)
    else:
        skill_dir = Path(__file__).parent.parent

    skill_name = skill_dir.name
    output_path = Path(f"{skill_name}.skill")

    # Create zip archive
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("."):
                arcname = file_path.relative_to(skill_dir)
                zf.write(file_path, arcname)
                print(f"  Added: {arcname}")

    print(f"\nPackaged skill to: {output_path.absolute()}")
    return output_path


if __name__ == "__main__":
    import sys

    skill_path = sys.argv[1] if len(sys.argv) > 1 else None
    package_skill(skill_path)
