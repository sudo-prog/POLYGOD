import os
import shutil
import re

source_dir = "/media/thinkpad/SUPERBIGBOY/VHS/"
dest_base = "/media/thinkpad/SUPERBIGBOY/Organized_Library/Movies/"

dry_run = False  # Set to False to actually move files

categories = [
    ("Anime", ["anime", "japanese", "ova", "manga", "gundam", "lupin", "berserk", "akira"]),
    (
        "Sci_Fi",
        [
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
            "stargate",
            "soylent",
            "sphere",
            "delta",
        ],
    ),
    (
        "Horror_Thriller",
        [
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
        ],
    ),
    (
        "Fantasy",
        [
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
        ],
    ),
    (
        "Action_Adventure",
        [
            "action",
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
        ],
    ),
    ("Animation", ["animation", "animated", "cartoon", "tintin", "alice", "disney", "dreamworks"]),
    ("Documentary", ["documentary", "cosmos", "nature", "history", "science"]),
    ("Western", ["western", "cowboy", "outlaw"]),
    ("Musical", ["musical", "opera", "rock", "concert", "floyd", "pink"]),
    ("Crime", ["crime", "criminal", "mafia", "gangster", "noir", "detective"]),
    ("Comedy", ["comedy", "funny", "laugh"]),
    ("Romance", ["romance", "love", "heart", "wedding"]),
    ("Drama", ["drama"]),
    ("XXX", ["xxx", "porn", "erotic", "adult", "nude", "sex", "nasty", "ilsa", "emmanuelle"]),
    ("Other", []),
]


def clean_title(name):
    match = re.search(r"\((\d{4})\)", name)
    year = int(match.group(1)) if match else None
    title = re.sub(r"\s*\(\d{4}\)", "", name)
    title = re.sub(r"\[.*?\]", "", title)
    title = re.sub(r"\(.*?\)", "", title)
    title = title.strip()
    if year:
        clean = f"{title} ({year})"
    else:
        clean = title
    return clean, year


def get_category(title, year):
    title_lower = title.lower()
    for cat, keywords in categories:
        if cat == "Other":
            continue
        if any(kw in title_lower for kw in keywords):
            return cat
    if (
        year
        and 1920 <= year <= 1955
        or any(kw in title_lower for kw in ["b&w", "black and white", "silent"])
    ):
        return "Classic/B&W"
    return "Other"


folders = [
    f
    for f in os.listdir(source_dir)
    if os.path.isdir(os.path.join(source_dir, f)) and not f.startswith("_") and f.startswith("A")
]
folders.sort()

counts = {}
for folder in folders:
    clean_name, year = clean_title(folder)
    category = get_category(clean_name, year)
    dest_dir = os.path.join(dest_base, category, clean_name)
    if os.path.exists(dest_dir):
        print(f"Skipping {folder} -> already exists in {category}")
        continue
    src_path = os.path.join(source_dir, folder)
    try:
        if dry_run:
            print(f"Would move {folder} to {category}/{clean_name}")
        else:
            shutil.move(src_path, dest_dir)
            print(f"Moved {folder} to {category}/{clean_name}")
        counts[category] = counts.get(category, 0) + 1
    except Exception as e:
        print(f"Error moving {folder}: {e}")

print("Final counts:")
for cat, count in sorted(counts.items()):
    print(f"{cat}: {count}")
