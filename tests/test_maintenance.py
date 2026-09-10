import pytest

from dispensa.storage.db import looks_like_prod
from dispensa.storage.maintenance import (
    refuse_destructive_on_prod,
    require_confirmation,
)

_PROD_URL = "postgresql+psycopg2://u:p@ep-x-pooler.eu-west-2.aws.neon.tech/neondb"
_BUILD_URL = "postgresql+psycopg2://u:p@db.neon.build/neondb"
_LOCAL_URL = "postgresql+psycopg2://dispensa:dispensa@localhost:5432/dispensa"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (_PROD_URL, True),
        (_BUILD_URL, True),
        (_PROD_URL.upper(), True),
        (_LOCAL_URL, False),
        ("postgresql+psycopg2://u:p@127.0.0.1:5432/dispensa", False),
    ],
)
def test_looks_like_prod(url: str, *, expected: bool) -> None:
    """Only Neon-hosted URLs read as production, case-insensitively."""
    assert looks_like_prod(url) is expected


def test_refuse_destructive_on_prod_raises_for_neon() -> None:
    """A destructive action against a Neon host is refused, naming the action."""
    with pytest.raises(ValueError, match="reset") as excinfo:
        refuse_destructive_on_prod(database_url=_PROD_URL, action="reset")
    assert "neon.tech" in str(excinfo.value)


def test_refuse_destructive_on_prod_allows_local() -> None:
    """A local host passes the guard silently (no exception)."""
    refuse_destructive_on_prod(database_url=_LOCAL_URL, action="reset")


def test_require_confirmation_raises_without_yes() -> None:
    """An unconfirmed destructive action is refused, naming the action."""
    with pytest.raises(ValueError, match="restore"):
        require_confirmation(
            confirmed=False,
            action="restore",
            database_url=_LOCAL_URL,
        )


def test_require_confirmation_passes_when_confirmed() -> None:
    """Passing --yes (confirmed=True) clears the guard (no exception)."""
    require_confirmation(confirmed=True, action="restore", database_url=_LOCAL_URL)
