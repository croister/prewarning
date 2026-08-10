"""Upgrade all dependencies to their latest compatible versions.

This script:
1. Upgrades Python to the latest patch in the pinned series.
2. Checks for outdated packages with compatible upgrades (same major version).
3. Updates the exact pins in pyproject.toml to the latest compatible versions.
4. Re-locks and syncs the environment.

Packages with incompatible upgrades (different major version) are reported
but not upgraded. Use the check_updates.py script to see those.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
PYTHON_VERSION_FILE = PROJECT_DIR / ".python-version"
PYPROJECT_FILE = PROJECT_DIR / "pyproject.toml"


def _major_version(version: str) -> str:
    """Extract the major version component for compatibility comparison."""
    parts = version.split(".")
    return parts[0] if parts else version


def _is_compatible_upgrade(current: str, latest: str) -> bool:
    """Determine if an upgrade is compatible (same major version)."""
    return _major_version(current) == _major_version(latest)


def _get_pinned_packages() -> set[str]:
    """Extract package names that are directly pinned in pyproject.toml."""
    content = PYPROJECT_FILE.read_text("utf-8")
    return {
        m.group(1).lower()
        for m in re.finditer(r'"([a-zA-Z0-9_-]+)(?:\[[^\]]*\])?(?:==|>=)', content)
    }


def _upgrade_python() -> bool:
    """Upgrade Python to the latest patch version. Returns True on success."""
    pinned = PYTHON_VERSION_FILE.read_text("utf-8").strip()
    print(f"1/4 Upgrading Python ({pinned} series)...")
    result = subprocess.run(
        ["uv", "python", "install", pinned],
        cwd=str(PROJECT_DIR),
        check=False,
    )
    return result.returncode == 0


def _get_compatible_upgrades() -> list[dict]:
    """Get list of directly pinned packages with compatible upgrades available."""
    result = subprocess.run(
        ["uv", "pip", "list", "--outdated", "--format", "json"],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []

    packages = json.loads(result.stdout)
    pinned_names = _get_pinned_packages()
    return [
        pkg
        for pkg in packages
        if pkg["name"].lower() in pinned_names
        and _is_compatible_upgrade(pkg["version"], pkg["latest_version"])
    ]


def _update_pyproject_pins(upgrades: list[dict]) -> int:
    """Update version pins in pyproject.toml. Returns count of updates."""
    content = PYPROJECT_FILE.read_text("utf-8")
    updated_count = 0

    for pkg in upgrades:
        name = pkg["name"]
        latest = pkg["latest_version"]

        # Match the dependency pin line with any version specifier (==, >=, etc.)
        # Handles both "package==1.0.0" and "package[extra]>=1.0.0"
        pattern = re.compile(
            rf'(?i)(\s*"{re.escape(name)}(?:\[[^\]]*\])?)(?:==|>=)[^"]*"'
        )
        new_content = pattern.sub(rf'\1=={latest}"', content)
        if new_content != content:
            content = new_content
            updated_count += 1
            print(f"  {name}: {pkg['version']} -> {latest}")

    if updated_count > 0:
        PYPROJECT_FILE.write_text(content, "utf-8")

    return updated_count


def _lock_and_sync() -> bool:
    """Re-lock and sync the environment. Returns True on success."""
    print("3/4 Locking dependencies...")
    result = subprocess.run(
        ["uv", "lock"],
        cwd=str(PROJECT_DIR),
        check=False,
    )
    if result.returncode != 0:
        print("Failed to lock dependencies.")
        return False

    print("4/4 Syncing environment...")
    result = subprocess.run(
        ["uv", "sync"],
        cwd=str(PROJECT_DIR),
        check=False,
    )
    if result.returncode != 0:
        print("Failed to sync environment.")
        return False

    return True


def main() -> int:
    if not _upgrade_python():
        print("Warning: Failed to upgrade Python, continuing with packages.\n")

    print("2/4 Checking for compatible upgrades...")
    upgrades = _get_compatible_upgrades()

    if not upgrades:
        print("  All packages are at their latest compatible versions.")
        print("\nDone. Run check_updates.py to see if incompatible upgrades exist.")
        return 0

    print(f"\n  Upgrading {len(upgrades)} package(s) in pyproject.toml:")
    updated = _update_pyproject_pins(upgrades)

    if updated == 0:
        print("  No pins were updated (packages may not be directly pinned).")
        return 0

    print()
    if not _lock_and_sync():
        return 1

    print("\nDone. Run the precommit checks to verify nothing is broken:")
    print("  uv run scripts/precommit.py")
    print("\nRun check_updates.py to see if incompatible upgrades exist:")
    print("  uv run scripts/check_updates.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
