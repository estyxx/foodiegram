from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine

from dispensa.app.queue import look_up_caption, queue_link, set_queued_caption
from dispensa.domain.enums import MedCategory, PendingStatus
from dispensa.domain.errors import LinkAlreadyKnownError, PendingLinkNotFoundError
from dispensa.domain.models import CategoryServing, Recipe
from dispensa.instagram import CaptionFetch, CaptionOutcome
from dispensa.storage.pending_db import PendingLinkRepository
from dispensa.storage.recipes_db import RecipeRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_URL = "https://www.instagram.com/p/ABC123/"


def _recipe(code: str) -> Recipe:
    """Build a minimal fish recipe already in the library."""
    return Recipe(
        code=code,
        pk="1",
        post_url=f"https://instagram.com/p/{code}/",
        caption=None,
        title=f"Recipe {code}",
        ingredients=["200g salmon"],
        instructions=["cook"],
        mediterranean_categories=[CategoryServing(category=MedCategory.FISH)],
    )


def test_queue_link_adds_a_new_pending_link(db_engine: Engine) -> None:
    """A fresh Instagram URL becomes a new queued link, keyed by shortcode."""
    link = queue_link(
        url=_URL,
        now=_NOW,
        pending=PendingLinkRepository(db_engine),
        recipes=RecipeRepository(db_engine),
    )

    assert link.code == "ABC123"
    assert link.status == PendingStatus.NEW
    assert link.caption is None


def test_queue_link_is_idempotent(db_engine: Engine) -> None:
    """Queuing the same link twice leaves one item."""
    pending = PendingLinkRepository(db_engine)
    recipes = RecipeRepository(db_engine)
    queue_link(url=_URL, now=_NOW, pending=pending, recipes=recipes)
    queue_link(url=_URL, now=_NOW, pending=pending, recipes=recipes)

    assert [link.code for link in pending.list_all()] == ["ABC123"]


def test_queue_link_rejects_a_non_instagram_url(db_engine: Engine) -> None:
    """A URL with no shortcode is rejected."""
    with pytest.raises(ValueError, match="Instagram"):
        queue_link(
            url="https://example.com/foo",
            now=_NOW,
            pending=PendingLinkRepository(db_engine),
            recipes=RecipeRepository(db_engine),
        )


def test_queue_link_rejects_a_post_already_in_the_library(db_engine: Engine) -> None:
    """A post that is already a recipe is not queued."""
    recipes = RecipeRepository(db_engine)
    recipes.save(_recipe("ABC123"))

    with pytest.raises(LinkAlreadyKnownError):
        queue_link(
            url=_URL,
            now=_NOW,
            pending=PendingLinkRepository(db_engine),
            recipes=recipes,
        )


def test_paste_caption_marks_the_link_ready(db_engine: Engine) -> None:
    """Pasting a caption stores it and moves the link to 'ready'."""
    pending = PendingLinkRepository(db_engine)
    queue_link(url=_URL, now=_NOW, pending=pending, recipes=RecipeRepository(db_engine))

    link = set_queued_caption(
        code="ABC123", caption="Ricetta della nonna", pending=pending
    )

    assert link.caption == "Ricetta della nonna"
    assert link.status == PendingStatus.READY


def test_paste_caption_on_an_unknown_link_raises(db_engine: Engine) -> None:
    """Pasting onto a link that is not queued is a clear error."""
    with pytest.raises(PendingLinkNotFoundError):
        set_queued_caption(
            code="NOPE",
            caption="x",
            pending=PendingLinkRepository(db_engine),
        )


class _Fetcher:
    """Stand in for Instagram: answers one fixed result and counts the calls."""

    def __init__(self, result: CaptionFetch) -> None:
        self.result = result
        self.calls: list[str] = []

    def __call__(self, code: str, /) -> CaptionFetch:
        """Record the lookup and return the fixed result."""
        self.calls.append(code)
        return self.result


def _queued(engine: Engine) -> PendingLinkRepository:
    """Queue the test link and return the repository holding it."""
    pending = PendingLinkRepository(engine)
    queue_link(url=_URL, now=_NOW, pending=pending, recipes=RecipeRepository(engine))
    return pending


def test_found_caption_marks_the_link_ready(db_engine: Engine) -> None:
    """A caption read from Instagram is stored and the link is ready."""
    pending = _queued(db_engine)
    fetch = _Fetcher(
        CaptionFetch(
            outcome=CaptionOutcome.FOUND, caption="Pasta e ceci", source="yt-dlp"
        ),
    )

    result = look_up_caption(code="ABC123", pending=pending, fetch=fetch)

    assert result.lookup is CaptionOutcome.FOUND
    assert result.link.caption == "Pasta e ceci"
    assert result.link.status is PendingStatus.READY


def test_a_refusal_leaves_the_link_waiting_for_a_paste(db_engine: Engine) -> None:
    """When Instagram refuses, nothing is stored and the outcome says why."""
    pending = _queued(db_engine)
    fetch = _Fetcher(CaptionFetch(outcome=CaptionOutcome.LOGIN_WALL, source="yt-dlp"))

    result = look_up_caption(code="ABC123", pending=pending, fetch=fetch)

    assert result.lookup is CaptionOutcome.LOGIN_WALL
    assert result.link.caption is None
    assert result.link.status is PendingStatus.NEW


def test_a_post_without_caption_is_not_ready(db_engine: Engine) -> None:
    """An empty caption is not a caption: the link still waits for a paste."""
    pending = _queued(db_engine)
    fetch = _Fetcher(CaptionFetch(outcome=CaptionOutcome.NO_CAPTION, source="yt-dlp"))

    result = look_up_caption(code="ABC123", pending=pending, fetch=fetch)

    assert result.link.status is PendingStatus.NEW


def test_a_caption_already_there_is_never_replaced(db_engine: Engine) -> None:
    """A pasted caption wins: Instagram is not even asked."""
    pending = _queued(db_engine)
    set_queued_caption(code="ABC123", caption="Mine", pending=pending)
    fetch = _Fetcher(CaptionFetch(outcome=CaptionOutcome.FOUND, caption="Theirs"))

    result = look_up_caption(code="ABC123", pending=pending, fetch=fetch)

    assert result.link.caption == "Mine"
    assert result.lookup is None
    assert fetch.calls == []


def test_looking_up_an_unknown_link_raises(db_engine: Engine) -> None:
    """Only a queued link can be looked up."""
    fetch = _Fetcher(CaptionFetch(outcome=CaptionOutcome.FOUND, caption="x"))

    with pytest.raises(PendingLinkNotFoundError):
        look_up_caption(
            code="NOPE", pending=PendingLinkRepository(db_engine), fetch=fetch
        )


def test_queue_lists_work_in_progress_first_then_newest_import(
    db_engine: Engine,
) -> None:
    """Links not yet imported lead; imported ones follow, latest import first."""
    pending = PendingLinkRepository(db_engine)
    recipes = RecipeRepository(db_engine)
    for day, code in enumerate(["OLD", "NEW", "WAIT"], start=1):
        queue_link(
            url=f"https://www.instagram.com/p/{code}/",
            now=datetime(2026, 11, day, tzinfo=UTC),
            pending=pending,
            recipes=recipes,
        )
    pending.mark(
        "OLD", PendingStatus.IMPORTED, imported_at=datetime(2026, 11, 20, tzinfo=UTC)
    )
    pending.mark(
        "NEW", PendingStatus.IMPORTED, imported_at=datetime(2026, 11, 22, tzinfo=UTC)
    )

    assert [link.code for link in pending.list_all()] == ["WAIT", "NEW", "OLD"]


def test_editing_an_imported_caption_keeps_it_imported(db_engine: Engine) -> None:
    """Notes on an imported link do not send it back to the ready column."""
    pending = PendingLinkRepository(db_engine)
    queue_link(url=_URL, now=_NOW, pending=pending, recipes=RecipeRepository(db_engine))
    pending.mark("ABC123", PendingStatus.IMPORTED, imported_at=_NOW)

    link = set_queued_caption(code="ABC123", caption="My notes", pending=pending)

    assert link.caption == "My notes"
    assert link.status is PendingStatus.IMPORTED
