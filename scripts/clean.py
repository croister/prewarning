import shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DIRS_TO_CLEAN = ["build", "dist", "__pycache__"]
PATTERNS_TO_CLEAN = ["*.pyc"]


def main():
    for dir_name in DIRS_TO_CLEAN:
        path = PROJECT_DIR / dir_name
        if path.exists():
            print(f"Removing {path}...")
            shutil.rmtree(path, ignore_errors=True)

    for pattern in PATTERNS_TO_CLEAN:
        for path in PROJECT_DIR.glob(pattern):
            print(f"Removing {path}...")
            path.unlink()

    for pycache in PROJECT_DIR.rglob("__pycache__"):
        if pycache.is_dir() and ".venv" not in pycache.parts:
            print(f"Removing {pycache}...")
            shutil.rmtree(pycache, ignore_errors=True)

    print("Done.")


if __name__ == "__main__":
    main()
