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
