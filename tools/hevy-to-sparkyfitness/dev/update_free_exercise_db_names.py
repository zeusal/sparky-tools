#!/usr/bin/env python3
"""Refresh site/free-exercise-db-names.json from Free Exercise DB.

    python3 tools/hevy-to-sparkyfitness/dev/update_free_exercise_db_names.py

SparkyFitness can add exercises from Free Exercise DB
(https://github.com/yuhonas/free-exercise-db, released into the public domain
under the Unlicense) and keeps their names, so the easy version offers
those names as suggestions for the exercise table.
"""
import json
import urllib.request
from pathlib import Path

SOURCE = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json"
TARGET = Path(__file__).resolve().parent.parent / "site" / "free-exercise-db-names.json"


def main():
    with urllib.request.urlopen(SOURCE, timeout=60) as response:
        exercises = json.load(response)
    names = sorted({e["name"].strip() for e in exercises if e.get("name", "").strip()},
                   key=lambda n: (n.lower(), n))
    data = {
        "source": "https://github.com/yuhonas/free-exercise-db",
        "license": "Unlicense (public domain)",
        "names": names,
    }
    TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"Wrote {len(names)} names to {TARGET}")


if __name__ == "__main__":
    main()
