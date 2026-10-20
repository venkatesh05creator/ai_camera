#!/usr/bin/env python3
"""Run the complete local security check suite.

    python scripts/security_check.py

The script executes, in this order:

1. ``ruff``          - linting (also a light SAST pass, ``S`` rules)
2. ``bandit``        - static analysis for known insecure patterns
3. ``pip-audit``     - known vulnerabilities in the declared dependencies
4. ``pytest``        - the functional and regression test-suite

Every step prints its own result; the exit code is non-zero if a step fails.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STEPS = [
    ("ruff (lint + SAST rules)", [sys.executable, "-m", "ruff", "check", "ownerai", "tests", "app.py"]),
    ("bandit (static analysis)", [sys.executable, "-m", "bandit", "-r", "ownerai", "-q"]),
    (
        "pip-audit (server dependencies)",
        [sys.executable, "-m", "pip_audit", "-r", "requirements-server.txt", "--progress-spinner=off"],
    ),
    ("pytest (test-suite)", [sys.executable, "-m", "pytest", "tests", "-q"]),
]


def run(title: str, command: list[str]) -> bool:
    print(f"\n=== {title} ===")
    print("$ " + " ".join(command))
    result = subprocess.run(command, cwd=str(ROOT))
    ok = result.returncode == 0
    print(f"--- {title}: {'PASSED' if ok else 'FAILED'} (exit {result.returncode})")
    return ok


def main() -> int:
    results = []
    for title, command in STEPS:
        results.append((title, run(title, command)))

    print("\n=== Summary ===")
    for title, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {title}")
    failed = [title for title, ok in results if not ok]
    if failed:
        print(f"\n{len(failed)} check(s) failed.")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
