#!/usr/bin/env python3
"""Rewrite tests/expected/ from the current converter.

    python tools/hevy-to-sparkyfitness/tests/regenerate_expected.py

Only run this after changing the output on purpose, then review every
difference (git diff) before committing it.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cases import CASES  # noqa: E402

SCRIPT = HERE.parent / "hevy_to_sparkyfitness.py"
FIXTURES = HERE / "fixtures"
EXPECTED = HERE / "expected"


def main():
    EXPECTED.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, fixture, options in CASES:
            out = Path(tmp) / f"{name}.csv"
            args = [o.replace("{fixtures}", str(FIXTURES)) for o in options]
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(FIXTURES / fixture), *args, "-o", str(out)],
                capture_output=True, text=True, encoding="utf-8")
            if result.returncode != 0:
                sys.exit(f"{name} failed:\n{result.stderr}")
            shutil.copyfile(out, EXPECTED / f"{name}.csv")
            print(f"wrote expected/{name}.csv")


if __name__ == "__main__":
    main()
