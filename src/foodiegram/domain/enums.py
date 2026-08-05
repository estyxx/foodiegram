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
    """Mediterranean protein group — the colour key, the facets, and the balance.

    One vocabulary for all three readings: the LLM assigns these per recipe with
    servings, proteins.py derives them from a recipe's free protein words, and
    the weekly balance grades the ones that have a target. PLANT_PROTEIN is
    newer than the rest and has no weekly target yet, so the balance leaves it
    untracked while the Browse facets already filter on it.
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
