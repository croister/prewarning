import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SPEC_FILE = PROJECT_DIR / "prewarning.spec"


def main():
    print(f"Building PreWarning from {SPEC_FILE}...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(SPEC_FILE)],
        cwd=str(PROJECT_DIR),
        check=False,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
