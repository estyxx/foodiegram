from collections.abc import Generator
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import Engine

from dispensa.api_models import PantryItemCreate
from dispensa.domain.enums import PantryLocation
from dispensa.domain.pantry import PantryItem
from dispensa.mcp_server.pantry_tools import (
    add_pantry_items,
    get_pantry,
    remove_pantry_items,
)
from dispensa.storage.pantry_db import PantryRepository


@pytest.fixture
def pantry(db_engine: Engine) -> Generator[PantryRepository]:
    """Point the pantry tools at a clean test pantry."""
    repository = PantryRepository(db_engine)
    with patch("dispensa.mcp_server.pantry_tools.get_deps") as get_deps:
        get_deps.return_value.pantry = repository
        yield repository


def test_add_pantry_items_returns_the_whole_pantry(pantry: PantryRepository) -> None:
    """Added items come back with ids, location, quantity and expiry."""
    pantry.add(PantryItem(name="olio", kind="staple"))

    result = add_pantry_items(
        items=[
            PantryItemCreate(
                name="ceci cotti",
                kind="fresh",
                location=PantryLocation.FRIDGE,
                quantity="mezzo barattolo",
                expires=date(2026, 10, 30),
            ),
            PantryItemCreate(name="pasta corta", kind="staple"),
        ],
    )

    assert [item["name"] for item in result] == ["ceci cotti", "olio", "pasta corta"]
    ceci = result[0]
    assert isinstance(ceci["id"], int)
    assert ceci["location"] == "fridge"
    assert ceci["quantity"] == "mezzo barattolo"
    assert ceci["expires"] == "2026-10-30"
    assert result[2]["location"] == "unknown"
    assert result[2]["quantity"] == ""


def test_get_pantry_lists_stored_items(pantry: PantryRepository) -> None:
    """get_pantry reads what is stored, ordered by name."""
    pantry.add(PantryItem(name="uova", kind="fresh", location=PantryLocation.FRIDGE))
    pantry.add(PantryItem(name="farina", kind="staple"))

    assert [item["name"] for item in get_pantry()] == ["farina", "uova"]


def test_remove_pantry_items_by_id(pantry: PantryRepository) -> None:
    """Removing by id returns what is left."""
    kept = pantry.add(PantryItem(name="olio", kind="staple"))
    used = pantry.add(PantryItem(name="uova", kind="fresh"))
    assert used.id is not None

    result = remove_pantry_items(ids=[used.id])

    assert [item["id"] for item in result] == [kept.id]


def test_remove_pantry_items_is_all_or_nothing(pantry: PantryRepository) -> None:
    """An unknown id fails the whole call and removes nothing."""
    stored = pantry.add(PantryItem(name="olio", kind="staple"))
    assert stored.id is not None

    with pytest.raises(ValueError, match=r"not found: 9999.*get_pantry"):
        remove_pantry_items(ids=[stored.id, 9999])

    assert [item.id for item in pantry.list_all()] == [stored.id]
