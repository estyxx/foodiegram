from pathlib import Path

from foodiegram.app.version import _read_git_commit, resolve_version

_FULL_SHA = "abcdef1234567890abcdef1234567890abcdef12"
_SHORT_SHA = "abcdef1"


def test_resolve_version_prefers_explicit_sha() -> None:
    """An explicit git SHA is shortened to seven chars and wins."""
    info = resolve_version(_FULL_SHA)
    assert info.commit == _SHORT_SHA


def test_resolve_version_reports_package_version() -> None:
    """The installed package version is populated, not the 0.0.0 fallback."""
    info = resolve_version("deadbeefcafebabe0000")
    assert info.version != "0.0.0"
    assert "." in info.version


def test_read_git_commit_follows_symbolic_ref(tmp_path: Path) -> None:
    """A HEAD pointing at a branch ref resolves to that ref's SHA."""
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "refs" / "heads" / "main").write_text(f"{_FULL_SHA}\n", encoding="utf-8")

    assert _read_git_commit(tmp_path) == _FULL_SHA


def test_read_git_commit_reads_packed_refs(tmp_path: Path) -> None:
    """A ref only present in packed-refs is still resolved."""
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "packed-refs").write_text(
        f"# pack-refs with: peeled fully-peeled sorted\n{_FULL_SHA} refs/heads/main\n",
        encoding="utf-8",
    )

    assert _read_git_commit(tmp_path) == _FULL_SHA


def test_read_git_commit_handles_detached_head(tmp_path: Path) -> None:
    """A detached HEAD storing a raw SHA returns it directly."""
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text(f"{_FULL_SHA}\n", encoding="utf-8")

    assert _read_git_commit(tmp_path) == _FULL_SHA


def test_read_git_commit_missing_returns_none(tmp_path: Path) -> None:
    """Without a .git directory the reader returns None."""
    assert _read_git_commit(tmp_path) is None
