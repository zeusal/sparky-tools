#!/usr/bin/env python3
"""Run every tool's tests.

    python scripts/run_tests.py

Each tool's tests run in their own Python process, so tools can't affect each
other. Exits with a non-zero status when any test fails or a tool has none.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    tools = sorted(p for p in (ROOT / "tools").iterdir() if p.is_dir())
    if not tools:
        sys.exit("No tools found under tools/.")
    failed = []
    for tool in tools:
        tests = tool / "tests"
        print(f"\n== {tool.name} ==", flush=True)
        if not any(tests.glob("test_*.py")):
            print(f"No tests found in {tests.relative_to(ROOT)}.")
            failed.append(tool.name)
            continue
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover",
             "-s", str(tests), "-t", str(tests), "-p", "test_*.py"],
            cwd=str(ROOT),
        )
        if result.returncode != 0:
            failed.append(tool.name)
    if failed:
        sys.exit("\nTests failed for: " + ", ".join(failed))
    print(f"\nAll tests passed for {len(tools)} tool(s).")


if __name__ == "__main__":
    main()
