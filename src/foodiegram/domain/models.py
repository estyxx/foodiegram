from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from foodiegram.domain.enums import CuisineType, Difficulty, DishType, MealType


class Recipe(BaseModel):
    """A structured, richly tagged recipe extracted from an Instagram post."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Identity (all Instagram IDs are strings; key by `code`, the shortcode).
    code: str
    pk: str
    caption: str

    # Core content. `ingredients_original` preserves the language as written.
    title: str
    ingredients: list[str] = Field(default_factory=list)
    ingredients_original: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)

    # Closed-set classifications.
    meal_type: MealType = MealType.UNKNOWN
    dish_type: DishType = DishType.UNKNOWN
    cuisine_type: CuisineType = CuisineType.UNKNOWN
    difficulty: Difficulty = Difficulty.UNKNOWN

    # Open, growing tag lists (normalized English; do not enum these).
    proteins: list[str] = Field(default_factory=list)
    vegetables: list[str] = Field(default_factory=list)
    grains_starches: list[str] = Field(default_factory=list)
    herbs_spices: list[str] = Field(default_factory=list)
    cooking_methods: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    dietary_tags: list[str] = Field(default_factory=list)
    health_tags: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    prep_style: list[str] = Field(default_factory=list)
    season: list[str] = Field(default_factory=list)
    occasion: list[str] = Field(default_factory=list)

    # Experience tags (open sets kept from the extractor).
    temperature: str = "unknown"
    texture: list[str] = Field(default_factory=list)
    flavor_profile: list[str] = Field(default_factory=list)
    skill_level: str = "unknown"

    # Times and serving.
    prep_time: str = "unknown"
    cook_time: str = "unknown"
    total_time: str = "unknown"
    servings: str = "unknown"

    # Media (durable Cloudinary URL is the source of truth; IG URLs expire).
    image_url: str | None = None
    image_public_id: str | None = None
    thumbnail_url: str | None = None

    # Provenance.
    is_recipe: bool = True
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extracted_at: datetime | None = None
    model_used: str | None = None
    edited_by_user: bool = False

    @property
    def post_url(self) -> str:
        """Return the canonical Instagram URL for this post."""
        return f"https://www.instagram.com/p/{self.code}/"
