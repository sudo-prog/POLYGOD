#!/usr/bin/env python3
"""
Analyze and categorize media without copying - FAST version
"""

import os
import re

SOURCE_VHS = "/media/thinkpad/SUPERBIGBOY/VHS"

SCIFI = [
    "space",
    "star",
    "robot",
    "alien",
    "future",
    "galactica",
    "planet",
    "trek",
    "wars",
    "droid",
    "cyber",
    "tetsuo",
    "stargate",
    "soylent",
]
HORROR = [
    "horror",
    "hellraiser",
    "devil",
    "demon",
    "zombie",
    "vampire",
    "nightmare",
    "blood",
    "creature",
    "possess",
    "phantasm",
    "suspiria",
    "nosferatu",
]
FANTASY = [
    "wizard",
    "magic",
    "sorcerer",
    "kingdom",
    "fantasy",
    "myth",
    "sword",
    "dragon",
    "quest",
    "labyrinth",
    "witch",
]
ACTION = [
    "war",
    "battle",
    "fight",
    "army",
    "soldier",
    "combat",
    "mission",
    "raid",
    "rambo",
    "riddick",
]
DOCO = ["documentary", "cosmos", "nature"]
CLASSIC = [
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
]
BW = ["black and white", "silent", "b&w"]
ANIMATION = ["animation", "animated", "anime", "cartoon"]
COMEDY = ["comedy", "funny"]
ROMANCE = ["romance", "love"]
WESTERN = ["western", "cowboy"]
MUSICAL = ["musical", "opera", "floyd", "pink"]
CRIME = ["crime", "mafia", "gangster", "noir"]
XXX = ["xxx", "porn", "erotic", "adult", "nude", "ilsa"]


def get_year(name):
    m = re.search(r"\((\d{4})", name)
    if m:
        return m.group(1)
    m = re.search(r"\[(\d{4})", name)
    if m:
        return m.group(1)
    return None


def get_category(name, year):
    s = name.lower()
    if any(k in s for k in XXX):
        return "XXX"
    if any(k in s for k in BW):
        return "B&W"
    if year and int(year) < 1940:
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


# Analyze VHS folder
folders = [f for f in os.listdir(SOURCE_VHS) if os.path.isdir(os.path.join(SOURCE_VHS, f))]
movie_folders = [f for f in folders if not f.startswith("_")]

cats = {}
movies = []

for f in sorted(movie_folders):
    year = get_year(f)
    cat = get_category(f, year)
    if cat not in cats:
        cats[cat] = []
    cats[cat].append(f)

print("=== VHS MOVIE CATEGORIES ===")
for cat, items in sorted(cats.items()):
    print(f"\n## {cat} ({len(items)} movies)")
    for m in items[:15]:
        year = get_year(m)
        print(f"  - {m}")
    if len(items) > 15:
        print(f"  ... and {len(items) - 15} more")

print(f"\n\nTOTAL MOVIES IN VHS: {len(movie_folders)}")
