import pytest

from foodiegram.domain.enums import MedCategory, ProteinTier
from foodiegram.domain.proteins import (
    PROTEIN_WORDS,
    TIERS,
    categories_for,
    tier_for,
)


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("tofu", MedCategory.PLANT_PROTEIN),
        ("seitan", MedCategory.PLANT_PROTEIN),
        ("mozzarella", MedCategory.DAIRY),
        ("ricotta", MedCategory.DAIRY),
        ("cheese", MedCategory.DAIRY),
        ("chicken", MedCategory.POULTRY),
        ("beef", MedCategory.RED_MEAT),
        ("pork", MedCategory.RED_MEAT),
        ("guanciale", MedCategory.PROCESSED_MEAT),
        ("prosciutto", MedCategory.PROCESSED_MEAT),
        ("ceci", MedCategory.LEGUMES),
        ("lenticchie", MedCategory.LEGUMES),
        ("beans", MedCategory.LEGUMES),
        ("seafood", MedCategory.FISH),
        ("eggs", MedCategory.EGGS),
    ],
)
def test_word_maps_to_its_category(word: str, expected: MedCategory) -> None:
    """Each protein word lands in the group the mapping table assigns it."""
    assert categories_for([word]) == {expected}


def test_unknown_word_is_skipped_not_an_error() -> None:
    """An unmapped word yields no category and never raises."""
    assert categories_for(["quinoa"]) == set()
    assert categories_for(["tofu", "quinoa"]) == {MedCategory.PLANT_PROTEIN}


def test_nuts_are_not_a_protein_category() -> None:
    """Nuts are a fats-and-snacks group, deliberately outside the balance."""
    assert categories_for(["nuts"]) == set()


def test_words_are_matched_case_and_whitespace_insensitively() -> None:
    """Extraction casing and stray spacing do not change the mapping."""
    assert categories_for([" Tofu ", "CHEESE"]) == {
        MedCategory.PLANT_PROTEIN,
        MedCategory.DAIRY,
    }


def test_several_words_collapse_to_the_set_of_their_categories() -> None:
    """Repeated categories dedupe; distinct ones accumulate."""
    assert categories_for(["fish", "seafood", "chicken"]) == {
        MedCategory.FISH,
        MedCategory.POULTRY,
    }


def test_empty_input_yields_no_categories() -> None:
    """A recipe with no protein words maps to no categories."""
    assert categories_for([]) == set()


def test_cured_meat_outranks_red_meat() -> None:
    """Cured pork reads as processed, not as red meat."""
    assert categories_for(["guanciale", "pancetta", "speck"]) == {
        MedCategory.PROCESSED_MEAT,
    }


def test_plant_protein_stays_separate_from_legumes() -> None:
    """Soy foods and pulses are filterable independently."""
    assert categories_for(["tofu", "beans"]) == {
        MedCategory.PLANT_PROTEIN,
        MedCategory.LEGUMES,
    }


def test_italian_and_english_words_agree() -> None:
    """The same food in either language reaches the same category."""
    pairs = [("chicken", "pollo"), ("beef", "manzo"), ("milk", "latte")]
    for english, italian in pairs:
        assert categories_for([english]) == categories_for([italian])


def test_every_category_has_exactly_one_tier() -> None:
    """TIERS partitions the eight categories, so tier_for is always defined."""
    tiered = [category for categories in TIERS.values() for category in categories]

    assert sorted(tiered) == sorted(MedCategory)
    assert len(tiered) == len(set(tiered))
    for category in MedCategory:
        assert tier_for(category) in ProteinTier


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        (MedCategory.FISH, ProteinTier.EAT_FREELY),
        (MedCategory.PLANT_PROTEIN, ProteinTier.EAT_FREELY),
        (MedCategory.DAIRY, ProteinTier.MODERATE),
        (MedCategory.PROCESSED_MEAT, ProteinTier.OCCASIONAL),
    ],
)
def test_tier_for_places_the_category(
    category: MedCategory,
    expected: ProteinTier,
) -> None:
    """Each category sits in its Mediterranean tier."""
    assert tier_for(category) == expected


def test_mapping_keys_are_normalised() -> None:
    """Every key is lower-cased and trimmed, or lookups would silently miss."""
    assert all(word == word.strip().lower() for word in PROTEIN_WORDS)
