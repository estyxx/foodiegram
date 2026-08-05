from foodiegram.domain.enums import MedCategory, ProteinTier

# Free protein words mapped to their group; keys are lower-cased. Extraction
# emits a closed English vocabulary today (cheese, eggs, beans, fish, seafood,
# nuts, chicken, tofu, pork, beef, dairy). The Italian and long-tail English
# entries below are for the re-extraction that widens it, so most of them match
# nothing yet.
#
# Four deliberate calls, all meant to be reviewed by eye:
#   - "nuts" is absent. In the Mediterranean frame nuts are a fats-and-snacks
#     group, not a weekly protein target; counting them would inflate the
#     legume and plant-protein numbers.
#   - Plant protein is its own group rather than part of legumes, so "beans"
#     and "tofu" stay independently filterable.
#   - Cured meats are processed_meat, not red_meat: guanciale in a carbonara
#     should read as occasional.
#   - "pepperoni" is absent on purpose. Italian "peperoni" means bell peppers
#     (see synonyms.py) and the two spellings are too easy to confuse; a cured
#     sausage is better caught by "salame".
PROTEIN_WORDS: dict[str, MedCategory] = {
    # Fish and seafood
    "fish": MedCategory.FISH,
    "pesce": MedCategory.FISH,
    "seafood": MedCategory.FISH,
    "salmon": MedCategory.FISH,
    "salmone": MedCategory.FISH,
    "tuna": MedCategory.FISH,
    "tonno": MedCategory.FISH,
    "shrimp": MedCategory.FISH,
    "gamberi": MedCategory.FISH,
    "cod": MedCategory.FISH,
    "merluzzo": MedCategory.FISH,
    # Legumes
    "beans": MedCategory.LEGUMES,
    "fagioli": MedCategory.LEGUMES,
    "chickpeas": MedCategory.LEGUMES,
    "ceci": MedCategory.LEGUMES,
    "lentils": MedCategory.LEGUMES,
    "lenticchie": MedCategory.LEGUMES,
    "peas": MedCategory.LEGUMES,
    "piselli": MedCategory.LEGUMES,
    # Plant protein
    "tofu": MedCategory.PLANT_PROTEIN,
    "tempeh": MedCategory.PLANT_PROTEIN,
    "edamame": MedCategory.PLANT_PROTEIN,
    "seitan": MedCategory.PLANT_PROTEIN,
    "soy": MedCategory.PLANT_PROTEIN,
    "soia": MedCategory.PLANT_PROTEIN,
    # Poultry
    "chicken": MedCategory.POULTRY,
    "pollo": MedCategory.POULTRY,
    "turkey": MedCategory.POULTRY,
    "tacchino": MedCategory.POULTRY,
    # Eggs
    "eggs": MedCategory.EGGS,
    "uova": MedCategory.EGGS,
    # Dairy
    "dairy": MedCategory.DAIRY,
    "cheese": MedCategory.DAIRY,
    "formaggio": MedCategory.DAIRY,
    "mozzarella": MedCategory.DAIRY,
    "ricotta": MedCategory.DAIRY,
    "parmesan": MedCategory.DAIRY,
    "parmigiano": MedCategory.DAIRY,
    "yogurt": MedCategory.DAIRY,
    "milk": MedCategory.DAIRY,
    "latte": MedCategory.DAIRY,
    # Red meat
    "beef": MedCategory.RED_MEAT,
    "manzo": MedCategory.RED_MEAT,
    "pork": MedCategory.RED_MEAT,
    "maiale": MedCategory.RED_MEAT,
    "lamb": MedCategory.RED_MEAT,
    "agnello": MedCategory.RED_MEAT,
    "veal": MedCategory.RED_MEAT,
    "vitello": MedCategory.RED_MEAT,
    # Processed and cured meat
    "salame": MedCategory.PROCESSED_MEAT,
    "salami": MedCategory.PROCESSED_MEAT,
    "prosciutto": MedCategory.PROCESSED_MEAT,
    "pancetta": MedCategory.PROCESSED_MEAT,
    "guanciale": MedCategory.PROCESSED_MEAT,
    "wurstel": MedCategory.PROCESSED_MEAT,
    "bacon": MedCategory.PROCESSED_MEAT,
    "speck": MedCategory.PROCESSED_MEAT,
}

# The Mediterranean tiers, in the order the Browse facets and the balance panel
# read them. This is the single grouping both must share, so neither invents its
# own and disagrees with the other on the same screen. Every MedCategory belongs
# to exactly one tier, which tests/test_proteins.py pins.
TIERS: dict[ProteinTier, tuple[MedCategory, ...]] = {
    ProteinTier.EAT_FREELY: (
        MedCategory.FISH,
        MedCategory.LEGUMES,
        MedCategory.PLANT_PROTEIN,
    ),
    ProteinTier.MODERATE: (
        MedCategory.POULTRY,
        MedCategory.EGGS,
        MedCategory.DAIRY,
    ),
    ProteinTier.OCCASIONAL: (
        MedCategory.RED_MEAT,
        MedCategory.PROCESSED_MEAT,
    ),
}

_TIER_BY_CATEGORY: dict[MedCategory, ProteinTier] = {
    category: tier for tier, categories in TIERS.items() for category in categories
}


def categories_for(proteins: list[str]) -> set[MedCategory]:
    """Return the protein groups these words belong to, skipping unknown ones."""
    return {
        PROTEIN_WORDS[word]
        for raw in proteins
        if (word := raw.strip().lower()) in PROTEIN_WORDS
    }


def tier_for(category: MedCategory) -> ProteinTier:
    """Return the Mediterranean tier a protein category belongs to."""
    return _TIER_BY_CATEGORY[category]
