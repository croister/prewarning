import re
from importlib.metadata import version as _metadata_version
from pathlib import Path


def _get_commit_sha(git_dir: Path | None = None) -> str | None:
    if git_dir is None:
        git_dir = Path(__file__).resolve().parent.parent / ".git"
    try:
        head = git_dir.joinpath("HEAD").read_text("utf-8").strip()
        if head.startswith("ref: "):
            ref_path = head[5:]
            return git_dir.joinpath(ref_path).read_text("utf-8").strip()[:7]
        return head[:7]
    except Exception:  # noqa: BLE001 - broad catch intentional; libraries raise diverse exceptions
        return None


def _get_package_version() -> str:
    return re.sub(r"\.dev\d+", "-dev", _metadata_version("prewarning"))


def _compute_version() -> str:
    version = _get_package_version()
    commit_sha = _get_commit_sha()
    if commit_sha and "-dev" in version and "+" not in version:
        version = f"{version}+{commit_sha}"
    return version


__version__ = _compute_version()
