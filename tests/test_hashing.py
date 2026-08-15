from foodiegram.ai.embeddings import recipe_document
from foodiegram.domain.hashing import caption_hash, document_hash
from foodiegram.domain.models import Recipe


def _recipe(
    *,
    title: str = "Torta di mele",
    proteins: list[str] | None = None,
) -> Recipe:
    """Build a minimal recipe for document-hash tests."""
    return Recipe(
        code="ABC",
        pk="1",
        post_url=None,
        caption=None,
        title=title,
        ingredients=["mele", "farina"],
        instructions=["mescola"],
        proteins=proteins or [],
    )


def test_caption_hash_none_and_empty_return_none() -> None:
    """Null, empty, and whitespace-only captions have no hash."""
    assert caption_hash(None) is None
    assert caption_hash("") is None
    assert caption_hash("   \n\t ") is None


def test_caption_hash_ignores_surrounding_whitespace() -> None:
    """Captions differing only by surrounding whitespace hash identically."""
    assert caption_hash("Pasta al forno") == caption_hash("  Pasta al forno\n")


def test_caption_hash_differs_for_different_captions() -> None:
    """Genuinely different captions produce different hashes."""
    assert caption_hash("Carbonara") != caption_hash("Amatriciana")


def test_document_hash_is_stable_for_identical_input() -> None:
    """The same document string always hashes to the same digest."""
    document = "Title\npasta lunch\neggs"
    assert document_hash(document) == document_hash(document)


def test_document_hash_changes_when_document_string_changes() -> None:
    """A changed document string yields a different digest."""
    assert document_hash("Title\npasta lunch\neggs") != document_hash(
        "Title\npasta dinner\neggs",
    )


def test_document_hash_tracks_recipe_document_changes() -> None:
    """A re-extraction changing tags (same caption) changes the document hash."""
    before = _recipe(proteins=["eggs"])
    after = before.model_copy(update={"proteins": ["eggs", "milk"]})

    assert document_hash(recipe_document(before)) != document_hash(
        recipe_document(after),
    )
