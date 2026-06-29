"""Check that all .po files have complete translations (no empty msgstr)."""

import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOCALES_DIR = PROJECT_DIR / "locales"
POT_FILE = LOCALES_DIR / "prewarning.pot"


def _extract_msgids(path: Path) -> set[str]:
    """Extract all non-empty msgid strings from a PO/POT file."""
    msgids: set[str] = set()
    current_msgid = ""
    in_msgid = False

    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("msgid "):
                if current_msgid:
                    msgids.add(current_msgid)
                current_msgid = line.split('"', 1)[1].rsplit('"', 1)[0]
                in_msgid = True
            elif line.startswith("msgstr "):
                if current_msgid:
                    msgids.add(current_msgid)
                current_msgid = ""
                in_msgid = False
            elif line.startswith('"') and in_msgid:
                current_msgid += line.split('"', 1)[1].rsplit('"', 1)[0]

    if current_msgid:
        msgids.add(current_msgid)

    msgids.discard("")
    return msgids


def check_pot_freshness() -> list[str]:
    """Re-extract strings and check if any are missing from the committed POT."""
    with tempfile.NamedTemporaryFile(suffix=".pot", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "pybabel",
                "extract",
                "-F",
                "config/babel.cfg",
                "-o",
                str(tmp_path),
                ".",
            ],
            cwd=str(PROJECT_DIR),
            capture_output=True,
        )
        if result.returncode != 0:
            return ["Failed to run pybabel extract."]

        fresh_msgids = _extract_msgids(tmp_path)
        committed_msgids = _extract_msgids(POT_FILE) if POT_FILE.exists() else set()

        missing = sorted(fresh_msgids - committed_msgids)
        return missing
    finally:
        tmp_path.unlink(missing_ok=True)


def check_po_file(po_path: Path) -> tuple[list[str], list[str], int]:
    """Return (untranslated, fuzzy, obsolete_count) for a .po file."""
    untranslated: list[str] = []
    fuzzy: list[str] = []
    obsolete_count = 0

    current_msgid = ""
    current_msgstr = ""
    current_is_fuzzy = False
    in_msgid = False
    in_msgstr = False

    def save_entry():
        # Only save if msgid is not empty (skips header)
        if current_msgid and not current_msgstr:
            untranslated.append(current_msgid)
        elif current_msgid and current_is_fuzzy:
            fuzzy.append(current_msgid)

    with po_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Count obsolete entries
            if line.startswith("#~ msgid "):
                obsolete_count += 1
                continue

            # Skip other obsolete continuation lines
            if line.startswith("#~"):
                continue

            # Track fuzzy flag
            if line.startswith("#,") and "fuzzy" in line:
                current_is_fuzzy = True
                continue

            # Skip other comments and empty lines
            if not line or line.startswith("#"):
                continue

            if line.startswith("msgid "):
                # We hit a new block, save the previous one first
                save_entry()
                current_msgid = line.split('"', 1)[1].rsplit('"', 1)[0]
                current_msgstr = ""
                current_is_fuzzy = False
                in_msgid = True
                in_msgstr = False

            elif line.startswith("msgstr "):
                current_msgstr = line.split('"', 1)[1].rsplit('"', 1)[0]
                in_msgid = False
                in_msgstr = True

            elif line.startswith('"'):
                # Safely extract text between the first and last quote of this line
                str_content = line.split('"', 1)[1].rsplit('"', 1)[0]
                if in_msgid:
                    current_msgid += str_content
                elif in_msgstr:
                    current_msgstr += str_content

        # Save the final entry at the end of the file
        save_entry()

    return untranslated, fuzzy, obsolete_count


def main() -> int:
    po_files = list(LOCALES_DIR.rglob("*.po"))
    if not po_files:
        print("No .po files found.")
        return 1

    errors = 0

    # Check that the POT file is up to date with source code
    missing_from_pot = check_pot_freshness()
    if missing_from_pot:
        print(
            f"POT file is stale — {len(missing_from_pot)} string(s) in source but not in POT:"
        )
        for msgid in missing_from_pot:
            print(f"  - {msgid[:80]}")
        print(
            "  Run: uv run pybabel extract -F config/babel.cfg -o locales/prewarning.pot ."
        )
        errors += len(missing_from_pot)

    for po_file in sorted(po_files):
        rel = po_file.relative_to(LOCALES_DIR.parent)

        # Check for untranslated, fuzzy, and obsolete strings
        untranslated, fuzzy, obsolete_count = check_po_file(po_file)
        if untranslated:
            print(f"{rel}: {len(untranslated)} untranslated string(s):")
            for msgid in untranslated:
                print(f"  - {msgid[:80]}")
            errors += len(untranslated)
        if fuzzy:
            print(f"{rel}: {len(fuzzy)} fuzzy string(s) (need review):")
            for msgid in fuzzy:
                print(f"  - {msgid[:80]}")
            errors += len(fuzzy)
        if obsolete_count:
            print(
                f"{rel}: {obsolete_count} obsolete (#~) entry/entries"
                " (run: uv run scripts/update_translations.py to clean up)"
            )
            errors += obsolete_count

        # Check that a compiled .mo file exists and is not older than the .po
        mo_file = po_file.with_suffix(".mo")
        if not mo_file.exists():
            print(
                f"{rel}: compiled .mo file is missing"
                " (run: pybabel compile -d locales -D prewarning)"
            )
            errors += 1
        elif mo_file.stat().st_mtime < po_file.stat().st_mtime:
            print(
                f"{rel}: .mo file is outdated"
                " (run: pybabel compile -d locales -D prewarning)"
            )
            errors += 1

    if errors:
        print(f"\nFAILED: {errors} translation issue(s) found.")
        return 1

    print("All translations complete and compiled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
