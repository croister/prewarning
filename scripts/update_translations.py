"""Extract strings, update PO files, and compile translations."""

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


def main():
    print("1/3 Extracting strings from source...")
    subprocess.run(
        [
            "uv",
            "run",
            "pybabel",
            "extract",
            "-F",
            "config/babel.cfg",
            "-o",
            "locales/prewarning.pot",
            ".",
        ],
        cwd=str(PROJECT_DIR),
        check=True,
    )

    print("2/3 Updating PO files...")
    subprocess.run(
        [
            "uv",
            "run",
            "pybabel",
            "update",
            "-i",
            "locales/prewarning.pot",
            "-d",
            "locales",
            "-D",
            "prewarning",
        ],
        cwd=str(PROJECT_DIR),
        check=True,
    )

    print("3/3 Compiling MO files...")
    subprocess.run(
        [
            "uv",
            "run",
            "pybabel",
            "compile",
            "-d",
            "locales",
            "-D",
            "prewarning",
        ],
        cwd=str(PROJECT_DIR),
        check=True,
    )

    print("\nDone. Review and translate any new/fuzzy entries in the .po files.")


if __name__ == "__main__":
    sys.exit(main())
