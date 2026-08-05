from enum import StrEnum


class MealType(StrEnum):
    """When a recipe is typically eaten."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    DESSERT = "dessert"
    APPETIZER = "appetizer"
    UNKNOWN = "unknown"


class DishType(StrEnum):
    """The kind of dish a recipe produces."""

    SOUP = "soup"
    SALAD = "salad"
    MAIN_COURSE = "main_course"
    SIDE_DISH = "side_dish"
    DESSERT = "dessert"
    BEVERAGE = "beverage"
    BREAD = "bread"
    SAUCE = "sauce"
    SNACK = "snack"
    PASTA = "pasta"
    RISOTTO = "risotto"
    PIZZA = "pizza"
    SANDWICH = "sandwich"
    PASTRY = "pastry"
    UNKNOWN = "unknown"


class MedCategory(StrEnum):
    """Mediterranean-diet tracked category (the 7-colour key)."""

    FISH = "fish"
    LEGUMES = "legumes"
    POULTRY = "poultry"
    EGGS = "eggs"
    DAIRY = "dairy"
    RED_MEAT = "red_meat"
    PROCESSED_MEAT = "processed_meat"


class ProteinCategory(StrEnum):
    """Protein group a recipe's free protein words map to.

    The seven MedCategory names repeat here with identical values, plus
    PLANT_PROTEIN. The two answer different questions: MedCategory carries the
    LLM-assigned servings the weekly balance counts, while this is derived from
    the protein word list to drive the Browse facets.
    """

    FISH = "fish"
    LEGUMES = "legumes"
    PLANT_PROTEIN = "plant_protein"
    POULTRY = "poultry"
    EGGS = "eggs"
    DAIRY = "dairy"
    RED_MEAT = "red_meat"
    PROCESSED_MEAT = "processed_meat"


class ProteinTier(StrEnum):
    """How often a protein group belongs in a Mediterranean week."""

    EAT_FREELY = "eat_freely"
    MODERATE = "moderate"
    OCCASIONAL = "occasional"


class RecipeSource(StrEnum):
    """Where a recipe originated."""

    INSTAGRAM = "instagram"
    MANUAL = "manual"


class Course(StrEnum):
    """Italian meal-structure grouping — Browse shelf order."""

    ANTIPASTO = "antipasto"
    PRIMO = "primo"
    SECONDO = "secondo"
    CONTORNO = "contorno"
    DOLCE = "dolce"
    LIEVITATI = "lievitati"
    COLAZIONE = "colazione"
    OTHER = "other"
    UNKNOWN = "unknown"


class CuisineType(StrEnum):
    """The culinary tradition a recipe belongs to."""

    ITALIAN = "italian"
    ASIAN = "asian"
    KOREAN = "korean"
    MEXICAN = "mexican"
    MEDITERRANEAN = "mediterranean"
    AMERICAN = "american"
    FRENCH = "french"
    FUSION = "fusion"
    OTHER = "other"
    UNKNOWN = "unknown"


class Difficulty(StrEnum):
    """How hard a recipe is to make."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    UNKNOWN = "unknown"
