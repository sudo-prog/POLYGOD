#!/usr/bin/env python3
"""
Media Library Organizer - Bulk Processing
Handles folder-based movie releases.
"""

import os
import re
import shutil
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()

# Paths
SOURCE_VHS = "/media/thinkpad/SUPERBIGBOY/VHS"
SOURCE_ANIME = "/media/thinkpad/SUPERBIGBOY/ANIME"
DEST_ROOT = "/media/thinkpad/SUPERBIGBOY/Organized_Library"

# Keywords for categorization
SCIFI = [
    "space",
    "star",
    "robot",
    "alien",
    "future",
    "galactica",
    "planet",
    "cosmos",
    "trek",
    "wars",
    "laser",
    "droid",
    "cyber",
    "tetsuo",
    "megazone",
    "orbital",
    "moontrap",
    "stargate",
    "soylent",
    "sphere",
    "delta",
    "voyage",
    "gravity",
    "arrival",
]
HORROR = [
    "horror",
    "hellraiser",
    "devil",
    "demon",
    "evil",
    "dead",
    "zombie",
    "vampire",
    "nightmare",
    "terror",
    "blood",
    "creature",
    "shiver",
    "haunt",
    "cannibal",
    "possess",
    "phantasm",
    "suspiria",
    "inferno",
    "nosferatu",
    "dracula",
    "fright",
]
FANTASY = [
    "wizard",
    "magic",
    "sorcerer",
    "kingdom",
    "lord",
    "fantasy",
    "myth",
    "mystic",
    "enchanted",
    "sword",
    "dragon",
    "quest",
    "labyrinth",
    "witch",
    "merlin",
    "fairy",
]
ACTION = [
    "war",
    "battle",
    "fight",
    "kill",
    "army",
    "soldier",
    "combat",
    "mission",
    "raid",
    "escape",
    "chase",
    "gun",
    "weapon",
    "rambo",
    "commando",
]
DOCO = ["documentary", "nature", "history channel"]
CLASSIC_OLD = [
    "1920",
    "1921",
    "1922",
    "1923",
    "1924",
    "1925",
    "1926",
    "1927",
    "1928",
    "1929",
    "1930",
    "1931",
    "1932",
    "1933",
    "1934",
    "1935",
    "1936",
    "1937",
    "1938",
    "1939",
    "1940",
]
BW = ["b&w", "black and white", "silent"]
ANIMATION = ["animation", "animated", "cartoon", "anime"]
COMEDY = ["comedy", "funny", "laugh"]
ROMANCE = ["romance", "love", "heart", "wedding"]
WESTERN = ["western", "cowboy", "outlaw"]
MUSICAL = ["musical", "opera", "rock", "concert", "floyd"]
CRIME = ["crime", "criminal", "mafia", "gangster", "noir", "detective"]
XXX = ["xxx", "porn", "erotic", "adult", "nude", "sex", "nasty", "ilsa", "emmanuelle"]


def get_year(folder_name):
    """Extract year from folder name."""
    patterns = [r"\((\d{4})", r"\[(\d{4})", r"\.(\d{4})\."]
    for p in patterns:
        m = re.search(p, folder_name)
        if m:
            return m.group(1)
    return None


def clean_title(folder_name):
    """Extract clean movie title."""
    # Remove everything in brackets/parentheses first
    title = re.sub(r"\[.*?\]", "", folder_name)
    title = re.sub(r"\(.*?\)", "", title)
    title = re.sub(r"(\d{4})", "", title)  # remove standalone years
    title = re.sub(r"\d{3,4}p", "", title)
    title = re.sub(r"BluRay|WEBRip|DVDRip|x265|x264|HEVC|H\d?\d?", "", title)
    title = re.sub(r"REMASTERED|PROPER|DC|UNRATED|EXTENDED|UNCUT", "", title)
    title = re.sub(r"RARBG|YTS|VXT|SAVAGE|Silence|SPARKS|PHDTeam|SAMPA|Tigole", "", title)
    title = re.sub(r"[A-Za-z]{3,}\s*$", "", title)  # release group at end
    title = re.sub(r"\s+", " ", title)
    title = title.replace(".", " ").replace("_", " ").strip()
    # Clean up trailing stuff
    title = re.sub(r"\s+-\s*$", "", title)
    return title.strip() if title else folder_name[:40]


def get_category(folder_name, year):
    """Determine movie category."""
    s = folder_name.lower()

    # Special cases first
    if any(k in s for k in XXX):
        return "XXX"
    if any(k in s for k in BW) or (year and int(year) < 1930):
        return "B&W"
    if year and int(year) < 1950:
        return "Classic"

    if any(k in s for k in SCIFI):
        return "Sci_Fi"
    if any(k in s for k in HORROR):
        return "Horror_Thriller"
    if any(k in s for k in FANTASY):
        return "Fantasy"
    if any(k in s for k in ANIMATION):
        return "Animation"
    if any(k in s for k in DOCO):
        return "Documentary"
    if any(k in s for k in WESTERN):
        return "Western"
    if any(k in s for k in MUSICAL):
        return "Musical"
    if any(k in s for k in CRIME):
        return "Crime"
    if any(k in s for k in COMEDY):
        return "Comedy"
    if any(k in s for k in ROMANCE):
        return "Romance"
    if any(k in s for k in ACTION):
        return "Action_Adventure"

    return "Other"


def get_files_in_folder(folder_path):
    """Get all media files in a folder."""
    files = []
    for f in os.listdir(folder_path):
        fp = os.path.join(folder_path, f)
        if os.path.isfile(fp):
            ext = os.path.splitext(f)[1].lower()
            if ext in [".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".flv", ".webm"]:
                files.append(f)
    return files


def organize_vhs():
    """Organize the VHS folder."""
    processed = []
    categories = {}

    # Get all folders in VHS
    folders = [f for f in os.listdir(SOURCE_VHS) if os.path.isdir(os.path.join(SOURCE_VHS, f))]
    folders = [f for f in folders if not f.startswith("_")]

    logger.info(f"Processing {len(folders)} movie folders...")

    for folder in sorted(folders):
        src = os.path.join(SOURCE_VHS, folder)

        # Get movie info
        year = get_year(folder)
        if not year:
            year = "unknown"

        title = clean_title(folder)
        category = get_category(folder, year)

        # Create destination
        dest_cat = os.path.join(DEST_ROOT, "Movies", category)
        dest_folder = os.path.join(dest_cat, f"{title} ({year})")

        # Track
        if category not in categories:
            categories[category] = 0
        categories[category] += 1

        # Copy folder contents
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)
            # Copy all files
            for f in os.listdir(src):
                src_file = os.path.join(src, f)
                if os.path.isfile(src_file):
                    dst_file = os.path.join(dest_folder, f)
                    try:
                        shutil.copy2(src_file, dst_file)
                    except Exception as e:
                        logger.info(f"Error copying {f}: {e}")

        processed.append(f"{title} ({year}) -> {category}")

    # Summary
    logger.info("\n=== ORGANIZATION SUMMARY ===")
    for cat, count in sorted(categories.items()):
        logger.info(f"  {cat}: {count}")
    logger.info(f"  TOTAL: {len(processed)}")

    return processed, categories


if __name__ == "__main__":
    organize_vhs()
