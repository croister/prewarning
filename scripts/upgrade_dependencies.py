"""Upgrade all dependencies to their latest compatible versions."""

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
PYTHON_VERSION_FILE = PROJECT_DIR / ".python-version"


def main() -> int:
    pinned = PYTHON_VERSION_FILE.read_text("utf-8").strip()

    print(f"1/3 Upgrading Python ({pinned} series)...")
    result = subprocess.run(
        ["uv", "python", "install", pinned],
        cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        print("Failed to upgrade Python.")
        return 1

    print("2/3 Upgrading lockfile...")
    result = subprocess.run(
        ["uv", "lock", "--upgrade"],
        cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        print("Failed to upgrade lockfile.")
        return 1

    print("3/3 Syncing environment...")
    result = subprocess.run(
        ["uv", "sync"],
        cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        print("Failed to sync environment.")
        return 1

    print("\nDone. Run the precommit checks to verify nothing is broken:")
    print("  uv run scripts/precommit.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
