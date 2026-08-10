"""Check for available dependency updates.

Reports two categories:
- Compatible upgrades: can be applied by running the upgrade script
  (updates the exact pins in pyproject.toml to the latest version).
- Incompatible upgrades: require a manual pin change in pyproject.toml
  because the latest version has a different major version.

Only directly pinned packages (those with == pins in pyproject.toml) are
reported. Transitive dependencies are managed by the lockfile.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
PYTHON_VERSION_FILE = PROJECT_DIR / ".python-version"
PYPROJECT_FILE = PROJECT_DIR / "pyproject.toml"


def _check_python_version() -> str | None:
    """Check if a newer Python patch version is available. Returns message or None."""
    pinned = PYTHON_VERSION_FILE.read_text("utf-8").strip()

    # Get installed version
    result = subprocess.run(
        ["uv", "run", "python", "--version"],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    installed = result.stdout.strip().split()[-1]  # "Python 3.14.6" -> "3.14.6"

    # Get all available versions for the pinned series
    result = subprocess.run(
        ["uv", "python", "list", "--all-versions"],
        capture_output=True,
        text=True,
        check=False,
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
        return f"Python {installed} -> {latest}"
    return None


def _get_pinned_packages() -> set[str]:
    """Extract package names that are directly pinned (==) in pyproject.toml."""
    content = PYPROJECT_FILE.read_text("utf-8")
    # Match "package-name==version" in dependency arrays
    return {
        m.group(1).lower()
        for m in re.finditer(r'"([a-zA-Z0-9_-]+)(?:\[[^\]]*\])?(?:==|>=)', content)
    }


def _major_version(version: str) -> str:
    """Extract the major version component for compatibility comparison."""
    parts = version.split(".")
    return parts[0] if parts else version


def _is_compatible_upgrade(current: str, latest: str) -> bool:
    """Determine if an upgrade is compatible (same major version)."""
    return _major_version(current) == _major_version(latest)


def _get_outdated_packages() -> list[dict] | None:
    """Get list of outdated packages from uv."""
    result = subprocess.run(
        ["uv", "pip", "list", "--outdated", "--format", "json"],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    if not output:
        return []
    return json.loads(output)


def main() -> int:
    print("Checking for updates...\n")
    has_updates = False

    # Check Python version
    python_msg = _check_python_version()
    if python_msg:
        print(f"  Python: {python_msg}")
        has_updates = True

    # Check package versions
    packages = _get_outdated_packages()
    if packages is None:
        print("Failed to check for package updates.")
        return 1

    # Only report packages that are directly pinned in pyproject.toml
    pinned_names = _get_pinned_packages()
    direct_packages = [p for p in packages if p["name"].lower() in pinned_names]

    compatible: list[dict] = []
    incompatible: list[dict] = []

    for pkg in direct_packages:
        if _is_compatible_upgrade(pkg["version"], pkg["latest_version"]):
            compatible.append(pkg)
        else:
            incompatible.append(pkg)

    if compatible:
        has_updates = True
        print("\nCompatible upgrades available (same major version):")
        print(f"  {'Package':<20} {'Current':<16} {'Latest':<16}")
        print(f"  {'-' * 20} {'-' * 16} {'-' * 16}")
        for pkg in compatible:
            print(
                f"  {pkg['name']:<20} {pkg['version']:<16} {pkg['latest_version']:<16}"
            )
        print("\n  Run: uv run scripts/upgrade_dependencies.py")

    if incompatible:
        has_updates = True
        print("\nIncompatible upgrades available (major version change):")
        print(f"  {'Package':<20} {'Current':<16} {'Latest':<16}")
        print(f"  {'-' * 20} {'-' * 16} {'-' * 16}")
        for pkg in incompatible:
            print(
                f"  {pkg['name']:<20} {pkg['version']:<16} {pkg['latest_version']:<16}"
            )
        print("\n  These require manually updating the pin in pyproject.toml:")
        for pkg in incompatible:
            print(f"    {pkg['name']}=={pkg['latest_version']}")
        print("  Then run: uv lock && uv sync")

    if not has_updates:
        print("All packages and Python are up to date.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
