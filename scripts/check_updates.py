"""Check for available dependency updates."""

import re
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
PYTHON_VERSION_FILE = PROJECT_DIR / ".python-version"


def _check_python_version() -> str | None:
    """Check if a newer Python patch version is available. Returns message or None."""
    pinned = PYTHON_VERSION_FILE.read_text("utf-8").strip()

    # Get installed version
    result = subprocess.run(
        ["uv", "run", "python", "--version"],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    installed = result.stdout.strip().split()[-1]  # "Python 3.14.6" -> "3.14.6"

    # Get all available versions for the pinned series
    result = subprocess.run(
        ["uv", "python", "list", "--all-versions"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    # Find the latest available version in the pinned series
    pattern = re.compile(rf"cpython-({re.escape(pinned)}\.\d+)-")
    versions: list[str] = []
    for line in result.stdout.splitlines():
        match = pattern.search(line)
        if match:
            versions.append(match.group(1))

    if not versions:
        return None

    latest = max(versions, key=lambda v: tuple(int(x) for x in v.split(".")))

    if latest != installed:
        return f"Python {installed} installed, {latest} available (run: uv python install {pinned})"
    return None


def main() -> int:
    print("Checking for updates...\n")

    # Check Python version
    python_msg = _check_python_version()
    if python_msg:
        print(f"Python: {python_msg}\n")

    # Check package versions
    result = subprocess.run(
        ["uv", "pip", "list", "--outdated"],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Failed to check for package updates.")
        print(result.stderr)
        return 1

    output = result.stdout.strip()
    if not output or output.count("\n") <= 1:
        if not python_msg:
            print("All packages and Python are up to date.")
    else:
        print(output)
        print("\nTo upgrade all dependencies to their latest compatible versions:")
        print("  uv run scripts/upgrade_dependencies.py")
        print("\nTo upgrade a single package:")
        print("  uv lock --upgrade-package <package>")
        print("  uv sync")

    return 0


if __name__ == "__main__":
    sys.exit(main())
