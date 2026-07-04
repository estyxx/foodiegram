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
