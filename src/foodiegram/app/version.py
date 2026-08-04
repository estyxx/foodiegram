import functools
import importlib.metadata
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_PACKAGE = "foodiegram"
_SHORT_SHA_LEN = 7
_UNKNOWN = "unknown"
# app/version.py -> app -> foodiegram -> src -> repo root.
_ROOT = Path(__file__).resolve().parents[3]


class VersionInfo(BaseModel):
    """The deployed application version and its source commit."""

    model_config = ConfigDict(frozen=True)

    version: str
    commit: str


def _package_version() -> str:
    """Return the installed package version, or 0.0.0 when unavailable."""
    try:
        return importlib.metadata.version(_PACKAGE)
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


def _read_git_commit(root: Path) -> str | None:
    """Read the current commit SHA from a .git directory, if one is present."""
    git_dir = root / ".git"
    head = git_dir / "HEAD"
    if not head.exists():
        return None
    content = head.read_text(encoding="utf-8").strip()
    if not content.startswith("ref:"):
        return content
    ref = content.removeprefix("ref:").strip()
    ref_file = git_dir / ref
    if ref_file.exists():
        return ref_file.read_text(encoding="utf-8").strip()
    packed = git_dir / "packed-refs"
    if packed.exists():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith(("#", "^")) and line.endswith(ref):
                return line.split(" ", 1)[0]
    return None


@functools.cache
def resolve_version(git_sha: str) -> VersionInfo:
    """Resolve the app version; git_sha wins, then .git, then unknown."""
    commit = git_sha or _read_git_commit(_ROOT) or _UNKNOWN
    short = commit if commit == _UNKNOWN else commit[:_SHORT_SHA_LEN]
    return VersionInfo(version=_package_version(), commit=short)
