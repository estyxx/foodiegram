import functools
import importlib.metadata
import logging
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_PACKAGE = "dispensa"
_SHORT_SHA_LEN = 6
_SHORT_DEPLOY_LEN = 8
# app/version.py -> app -> dispensa -> src -> repo root.
_ROOT = Path(__file__).resolve().parents[3]

logger = logging.getLogger(__name__)

# Env-var name fragments that might carry a commit or build id, for the probe.
_SOURCE_HINTS = (
    "FASTAPI",
    "DEPLOY",
    "COMMIT",
    "SHA",
    "GIT",
    "BUILD",
    "SOURCE",
    "VERSION",
)


class VersionInfo(BaseModel):
    """The deployed application version, source commit, and deployment id."""

    model_config = ConfigDict(frozen=True)

    version: str
    commit: str
    deployment: str


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
def resolve_version(git_sha: str, deployment_id: str = "") -> VersionInfo:
    """Resolve the version: commit from git_sha then .git (else empty), plus the id.

    An empty commit beats a guessed one — when the deploy ships without .git and
    no GIT_SHA is set, the footer falls back to the deployment id.
    """
    commit = git_sha or _read_git_commit(_ROOT) or ""
    return VersionInfo(
        version=_package_version(),
        commit=commit[:_SHORT_SHA_LEN],
        deployment=deployment_id[:_SHORT_DEPLOY_LEN],
    )


def log_runtime_probe() -> None:
    """Log (names only, never values) which platform env vars and markers show.

    Lets the operator read from one deploy's logs whether the platform exposes a
    commit SHA; if it does, set GIT_SHA from it and the footer shows the commit.
    """
    names = sorted(os.environ)
    source_like = [n for n in names if any(h in n.upper() for h in _SOURCE_HINTS)]
    logger.info(
        "runtime probe: %d env vars; source/commit-like names: %s; .git present: %s",
        len(names),
        source_like,
        (_ROOT / ".git").exists(),
    )
