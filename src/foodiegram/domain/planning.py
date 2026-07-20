from pydantic import BaseModel, ConfigDict

from foodiegram.domain.enums import MedCategory


class CategoryTarget(BaseModel):
    """Weekly serving target range for one Mediterranean category."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: MedCategory
    min_servings: float
    max_servings: float


# Default weekly targets from the Mediterranean engine table (§2). User-editable
# later; seeded into the targets table when it is empty.
DEFAULT_TARGETS: tuple[CategoryTarget, ...] = (
    CategoryTarget(category=MedCategory.FISH, min_servings=2, max_servings=3),
    CategoryTarget(category=MedCategory.LEGUMES, min_servings=2, max_servings=3),
    CategoryTarget(category=MedCategory.POULTRY, min_servings=1, max_servings=2),
    CategoryTarget(category=MedCategory.EGGS, min_servings=2, max_servings=4),
    CategoryTarget(category=MedCategory.DAIRY, min_servings=0, max_servings=7),
    CategoryTarget(category=MedCategory.RED_MEAT, min_servings=0, max_servings=2),
    CategoryTarget(
        category=MedCategory.PROCESSED_MEAT,
        min_servings=0,
        max_servings=1,
    ),
)
