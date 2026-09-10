from dispensa.domain.diffing import (
    FieldDiff,
    diff_against_recipe,
    diff_payloads,
)
from dispensa.domain.editing import (
    EXTRACTION_FIELDS,
    PROTECTED_FIELDS,
    promote,
)
from dispensa.domain.enums import (
    Course,
    CuisineType,
    Difficulty,
    DishType,
    MealType,
    MedCategory,
    ProteinTier,
    RecipeSource,
)
from dispensa.domain.errors import (
    ConfigurationError,
    DispensaError,
    ExtractionError,
    InstagramFetchError,
    StorageError,
)
from dispensa.domain.hashing import (
    caption_hash,
    document_hash,
    normalize_caption,
)
from dispensa.domain.models import (
    CategoryServing,
    ExtractedCategoryServing,
    ExtractedRecipe,
    Extraction,
    MappedRecipe,
    Recipe,
    UserState,
)
from dispensa.domain.pantry import KitchenMatch, PantryItem, kitchen_match
from dispensa.domain.planning import (
    DEFAULT_TARGETS,
    CategoryStatus,
    CategoryTarget,
    PlannedMeal,
    WeekPlan,
    gap_suggestions,
    oily_fish_count,
    week_balance,
)
from dispensa.domain.proteins import (
    PROTEIN_WORDS,
    TIERS,
    categories_for,
    facets_for,
    tier_for,
)
from dispensa.domain.shopping import AisleGroup, ShoppingItem, shopping_list
from dispensa.domain.synonyms import (
    SYNONYM_GROUPS,
    canonical_term,
    expand_term,
)

__all__ = [
    "DEFAULT_TARGETS",
    "EXTRACTION_FIELDS",
    "PROTECTED_FIELDS",
    "PROTEIN_WORDS",
    "SYNONYM_GROUPS",
    "TIERS",
    "AisleGroup",
    "CategoryServing",
    "CategoryStatus",
    "CategoryTarget",
    "ConfigurationError",
    "Course",
    "CuisineType",
    "Difficulty",
    "DishType",
    "DispensaError",
    "ExtractedCategoryServing",
    "ExtractedRecipe",
    "Extraction",
    "ExtractionError",
    "FieldDiff",
    "InstagramFetchError",
    "KitchenMatch",
    "MappedRecipe",
    "MealType",
    "MedCategory",
    "PantryItem",
    "PlannedMeal",
    "ProteinTier",
    "Recipe",
    "RecipeSource",
    "ShoppingItem",
    "StorageError",
    "UserState",
    "WeekPlan",
    "canonical_term",
    "caption_hash",
    "categories_for",
    "diff_against_recipe",
    "diff_payloads",
    "document_hash",
    "expand_term",
    "facets_for",
    "gap_suggestions",
    "kitchen_match",
    "normalize_caption",
    "oily_fish_count",
    "promote",
    "shopping_list",
    "tier_for",
    "week_balance",
]
