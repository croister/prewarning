import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
YAMLLINT_CONFIG = PROJECT_DIR / ".yamllint"


def _run_step(
    step: int, total: int, title: str, cmd: list[str], success_msg: str | None = None
) -> None:
    print(f"\n=== {step}/{total} {title} ===")
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR))
    if result.returncode != 0:
        print(f"FAILED: {title}")
        sys.exit(result.returncode)
    if success_msg:
        print(success_msg)


def _yamllint_cmd() -> list[str]:
    base_config = YAMLLINT_CONFIG.read_text("utf-8")
    newline_type = "dos" if sys.platform == "win32" else "unix"
    config = base_config + f"  new-lines:\n    type: {newline_type}\n"
    return ["uvx", "yamllint", "--config-data", config, ".github/workflows/"]


def main():
    total = 8

    _run_step(1, total, "YAML Lint", _yamllint_cmd(), "No YAML issues found.")
    _run_step(
        2,
        total,
        "Spelling",
        success_msg="No spelling mistakes found.",
        cmd=[
            "uvx",
            "codespell",
            "--skip=.git,uv.lock,dist,__pycache__,logs,build,startlists,test_data,**country_dict_by_ioc*,locales",
            "--ignore-words-list=datas",
        ],
    )
    _run_step(3, total, "Ruff Check", ["uvx", "ruff", "check", "."])
    _run_step(4, total, "Ruff Format", ["uvx", "ruff", "format", "--check", "."])
    _run_step(
        5, total, "Security Audit", ["uv", "audit", "--preview-features", "audit"]
    )
    _run_step(
        6,
        total,
        "Type Check",
        [
            "uv",
            "run",
            "mypy",
            "--check-untyped-defs",
            "prewarning.py",
            "utils",
            "validators",
            "punchsources",
            "startlistsources",
        ],
    )
    _run_step(
        7,
        total,
        "Translations",
        ["uv", "run", "python", "scripts/check_translations.py"],
    )
    _run_step(8, total, "Tests", ["uv", "run", "pytest", "-q"])

    print("\nAll checks passed!")


if __name__ == "__main__":
    main()
