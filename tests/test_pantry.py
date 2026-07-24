from foodiegram.domain.pantry import PantryItem, kitchen_match


def test_synonym_and_cross_language_matching() -> None:
    """A pantry item matches ingredient lines via synonyms in either language."""
    pantry = [
        PantryItem(name="courgette", kind="fresh"),
        PantryItem(name="parmesan", kind="staple"),
    ]
    ingredients = ["200g zucchine", "50g parmigiano", "2 eggs", "salt"]

    match = kitchen_match(ingredients, pantry)

    assert match.have == ["200g zucchine", "50g parmigiano"]
    assert match.missing == ["2 eggs", "salt"]


def test_empty_pantry_leaves_everything_missing() -> None:
    """With no pantry, every line is missing and none are on hand."""
    match = kitchen_match(["water", "flour"], [])

    assert match.have == []
    assert match.missing == ["water", "flour"]


def test_matching_respects_word_boundaries() -> None:
    """A pantry name does not match when it only appears inside another word."""
    pantry = [PantryItem(name="oil", kind="staple")]

    match = kitchen_match(["boil the pasta", "2 tbsp oil"], pantry)

    assert match.have == ["2 tbsp oil"]
    assert match.missing == ["boil the pasta"]
