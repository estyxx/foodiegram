from datetime import date, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class RecipeRow(SQLModel, table=True):
    """Canonical mutable recipe row. JSON columns hold list/complex fields."""

    __tablename__ = "recipes"

    code: str = Field(primary_key=True)
    source: str
    pk: str | None = None
    post_url: str | None = None
    caption: str | None = None
    author_username: str | None = None

    title: str
    meal_type: str
    dish_type: str
    cuisine_type: str
    difficulty: str
    course: str

    prep_time: str | None = None
    cook_time: str | None = None
    total_time: str | None = None
    servings: str | None = None
    base_servings: int | None = None
    temperature: str | None = None
    skill_level: str | None = None

    cloudinary_url: str | None = None
    thumbnail_url: str | None = None

    archived: bool = False
    edited_by_user: bool = False
    is_recipe: bool = True
    confidence: float = 1.0
    extracted_at: datetime | None = None
    model_used: str | None = None
    prompt_version: str | None = None

    created_at: datetime
    updated_at: datetime

    ingredients: list[str] = Field(sa_column=Column(JSON))
    instructions: list[str] = Field(sa_column=Column(JSON))
    mediterranean_categories: list[dict[str, object]] = Field(sa_column=Column(JSON))
    proteins: list[str] = Field(sa_column=Column(JSON))
    vegetables: list[str] = Field(sa_column=Column(JSON))
    grains_starches: list[str] = Field(sa_column=Column(JSON))
    herbs_spices: list[str] = Field(sa_column=Column(JSON))
    cooking_methods: list[str] = Field(sa_column=Column(JSON))
    equipment: list[str] = Field(sa_column=Column(JSON))
    texture: list[str] = Field(sa_column=Column(JSON))
    flavor_profile: list[str] = Field(sa_column=Column(JSON))
    dietary_tags: list[str] = Field(sa_column=Column(JSON))
    health_tags: list[str] = Field(sa_column=Column(JSON))
    season: list[str] = Field(sa_column=Column(JSON))
    occasion: list[str] = Field(sa_column=Column(JSON))
    style_tags: list[str] = Field(sa_column=Column(JSON))
    prep_style: list[str] = Field(sa_column=Column(JSON))
    edited_fields: list[str] = Field(sa_column=Column(JSON))


class ExtractionRow(SQLModel, table=True):
    """Append-only immutable LLM extraction run for one recipe."""

    __tablename__ = "extractions"

    id: int | None = Field(default=None, primary_key=True)
    recipe_code: str = Field(foreign_key="recipes.code", ondelete="CASCADE")
    prompt_version: str
    model: str
    batch_id: str | None = None
    kind: str
    extracted_at: datetime
    payload: dict[str, object] = Field(sa_column=Column(JSON))


class RecipeEmbeddingRow(SQLModel, table=True):
    """One embedding vector per recipe for semantic similarity search."""

    __tablename__ = "recipe_embeddings"

    recipe_code: str = Field(
        primary_key=True,
        foreign_key="recipes.code",
        ondelete="CASCADE",
    )
    model: str
    embedding: list[float] = Field(sa_column=Column(JSON))
    created_at: datetime


class PostRow(SQLModel, table=True):
    """Staging row for an ingested Instagram post."""

    __tablename__ = "posts"

    code: str = Field(primary_key=True)
    caption: str | None = None
    taken_at: datetime | None = None
    collection_names: list[str] = Field(sa_column=Column(JSON))
    ingested_at: datetime


class WeekPlanRow(SQLModel, table=True):
    """A planned week, keyed by its (Monday) start date."""

    __tablename__ = "week_plans"

    id: int | None = Field(default=None, primary_key=True)
    week_start: date = Field(unique=True)


class PlannedMealRow(SQLModel, table=True):
    """One meal slot within a week plan."""

    __tablename__ = "planned_meals"

    id: int | None = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="week_plans.id", ondelete="CASCADE")
    day: date
    meal: str
    recipe_code: str
    portions: int = 2


class PantryItemRow(SQLModel, table=True):
    """A pantry entry: name + staple/fresh + optional expiry."""

    __tablename__ = "pantry_items"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    kind: str
    expires: date | None = None


class UserStateRow(SQLModel, table=True):
    """Per-recipe app state (favourite / notes), keyed by recipe code."""

    __tablename__ = "user_state"

    recipe_code: str = Field(primary_key=True)
    is_favorite: bool = False
    user_notes: str | None = None
    updated_at: datetime


class TargetRow(SQLModel, table=True):
    """Weekly serving target for one Mediterranean category."""

    __tablename__ = "targets"

    category: str = Field(primary_key=True)
    min_servings: float
    max_servings: float
