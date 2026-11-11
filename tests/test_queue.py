from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine

from dispensa.app.queue import queue_link, set_queued_caption
from dispensa.domain.enums import MedCategory, PendingStatus
from dispensa.domain.errors import LinkAlreadyKnownError, PendingLinkNotFoundError
from dispensa.domain.models import CategoryServing, Recipe
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
