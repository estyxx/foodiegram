from foodiegram.domain.enums import ProteinCategory, ProteinTier

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
PROTEIN_WORDS: dict[str, ProteinCategory] = {
    # Fish and seafood
    "fish": ProteinCategory.FISH,
    "pesce": ProteinCategory.FISH,
    "seafood": ProteinCategory.FISH,
    "salmon": ProteinCategory.FISH,
    "salmone": ProteinCategory.FISH,
    "tuna": ProteinCategory.FISH,
    "tonno": ProteinCategory.FISH,
    "shrimp": ProteinCategory.FISH,
    "gamberi": ProteinCategory.FISH,
    "cod": ProteinCategory.FISH,
    "merluzzo": ProteinCategory.FISH,
    # Legumes
    "beans": ProteinCategory.LEGUMES,
    "fagioli": ProteinCategory.LEGUMES,
    "chickpeas": ProteinCategory.LEGUMES,
    "ceci": ProteinCategory.LEGUMES,
    "lentils": ProteinCategory.LEGUMES,
    "lenticchie": ProteinCategory.LEGUMES,
    "peas": ProteinCategory.LEGUMES,
    "piselli": ProteinCategory.LEGUMES,
    # Plant protein
    "tofu": ProteinCategory.PLANT_PROTEIN,
    "tempeh": ProteinCategory.PLANT_PROTEIN,
    "edamame": ProteinCategory.PLANT_PROTEIN,
    "seitan": ProteinCategory.PLANT_PROTEIN,
    "soy": ProteinCategory.PLANT_PROTEIN,
    "soia": ProteinCategory.PLANT_PROTEIN,
    # Poultry
    "chicken": ProteinCategory.POULTRY,
    "pollo": ProteinCategory.POULTRY,
    "turkey": ProteinCategory.POULTRY,
    "tacchino": ProteinCategory.POULTRY,
    # Eggs
    "eggs": ProteinCategory.EGGS,
    "uova": ProteinCategory.EGGS,
    # Dairy
    "dairy": ProteinCategory.DAIRY,
    "cheese": ProteinCategory.DAIRY,
    "formaggio": ProteinCategory.DAIRY,
    "mozzarella": ProteinCategory.DAIRY,
    "ricotta": ProteinCategory.DAIRY,
    "parmesan": ProteinCategory.DAIRY,
    "parmigiano": ProteinCategory.DAIRY,
    "yogurt": ProteinCategory.DAIRY,
    "milk": ProteinCategory.DAIRY,
    "latte": ProteinCategory.DAIRY,
    # Red meat
    "beef": ProteinCategory.RED_MEAT,
    "manzo": ProteinCategory.RED_MEAT,
    "pork": ProteinCategory.RED_MEAT,
    "maiale": ProteinCategory.RED_MEAT,
    "lamb": ProteinCategory.RED_MEAT,
    "agnello": ProteinCategory.RED_MEAT,
    "veal": ProteinCategory.RED_MEAT,
    "vitello": ProteinCategory.RED_MEAT,
    # Processed and cured meat
    "salame": ProteinCategory.PROCESSED_MEAT,
    "salami": ProteinCategory.PROCESSED_MEAT,
    "prosciutto": ProteinCategory.PROCESSED_MEAT,
    "pancetta": ProteinCategory.PROCESSED_MEAT,
    "guanciale": ProteinCategory.PROCESSED_MEAT,
    "wurstel": ProteinCategory.PROCESSED_MEAT,
    "bacon": ProteinCategory.PROCESSED_MEAT,
    "speck": ProteinCategory.PROCESSED_MEAT,
}

# The Mediterranean tiers, in the order the Browse facets and the balance panel
# read them. This is the single grouping both must share, so neither invents its
# own and disagrees with the other on the same screen.
TIERS: dict[ProteinTier, tuple[ProteinCategory, ...]] = {
    ProteinTier.EAT_FREELY: (
        ProteinCategory.FISH,
        ProteinCategory.LEGUMES,
        ProteinCategory.PLANT_PROTEIN,
    ),
    ProteinTier.MODERATE: (
        ProteinCategory.POULTRY,
        ProteinCategory.EGGS,
        ProteinCategory.DAIRY,
    ),
    ProteinTier.OCCASIONAL: (
        ProteinCategory.RED_MEAT,
        ProteinCategory.PROCESSED_MEAT,
    ),
}

_TIER_BY_CATEGORY: dict[ProteinCategory, ProteinTier] = {
    category: tier for tier, categories in TIERS.items() for category in categories
}


def categories_for(proteins: list[str]) -> set[ProteinCategory]:
    """Return the protein groups these words belong to, skipping unknown ones."""
    return {
        PROTEIN_WORDS[word]
        for raw in proteins
        if (word := raw.strip().lower()) in PROTEIN_WORDS
    }


def tier_for(category: ProteinCategory) -> ProteinTier:
    """Return the Mediterranean tier a protein category belongs to."""
    return _TIER_BY_CATEGORY[category]
