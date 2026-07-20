from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlmodel import select

from foodiegram.domain.models import Recipe
from foodiegram.storage._tables import RecipeRow
from foodiegram.storage.db import ensure_utc, get_session

if TYPE_CHECKING:
    from sqlalchemy import Engine


def _to_row(recipe: Recipe, *, created_at: datetime, updated_at: datetime) -> RecipeRow:
    """Map a domain Recipe to a storage row, serialising JSON fields."""
    dump = recipe.model_dump(mode="json")
    return RecipeRow(
        code=recipe.code,
        source=recipe.source.value,
        pk=recipe.pk,
        post_url=recipe.post_url,
        caption=recipe.caption,
        title=recipe.title,
        meal_type=recipe.meal_type.value,
        dish_type=recipe.dish_type.value,
        cuisine_type=recipe.cuisine_type.value,
        difficulty=recipe.difficulty.value,
        course=recipe.course.value,
        prep_time=recipe.prep_time,
        cook_time=recipe.cook_time,
        total_time=recipe.total_time,
        servings=recipe.servings,
        base_servings=recipe.base_servings,
        temperature=recipe.temperature,
        skill_level=recipe.skill_level,
        cloudinary_url=recipe.cloudinary_url,
        thumbnail_url=recipe.thumbnail_url,
        archived=recipe.archived,
        edited_by_user=recipe.edited_by_user,
        is_recipe=recipe.is_recipe,
        confidence=recipe.confidence,
        extracted_at=recipe.extracted_at,
        model_used=recipe.model_used,
        prompt_version=recipe.prompt_version,
        created_at=created_at,
        updated_at=updated_at,
        ingredients=recipe.ingredients,
        instructions=recipe.instructions,
        mediterranean_categories=dump["mediterranean_categories"],
        proteins=recipe.proteins,
        vegetables=recipe.vegetables,
        grains_starches=recipe.grains_starches,
        herbs_spices=recipe.herbs_spices,
        cooking_methods=recipe.cooking_methods,
        equipment=recipe.equipment,
        texture=recipe.texture,
        flavor_profile=recipe.flavor_profile,
        dietary_tags=recipe.dietary_tags,
        health_tags=recipe.health_tags,
        season=recipe.season,
        occasion=recipe.occasion,
        style_tags=recipe.style_tags,
        prep_style=recipe.prep_style,
        edited_fields=sorted(recipe.edited_fields),
    )


def _to_domain(row: RecipeRow) -> Recipe:
    """Map a storage row back to a domain Recipe, reviving enums and collections."""
    return Recipe.model_validate(
        {
            "code": row.code,
            "source": row.source,
            "pk": row.pk,
            "post_url": row.post_url,
            "caption": row.caption,
            "title": row.title,
            "ingredients": row.ingredients,
            "instructions": row.instructions,
            "meal_type": row.meal_type,
            "dish_type": row.dish_type,
            "cuisine_type": row.cuisine_type,
            "difficulty": row.difficulty,
            "course": row.course,
            "mediterranean_categories": row.mediterranean_categories,
            "proteins": row.proteins,
            "vegetables": row.vegetables,
            "grains_starches": row.grains_starches,
            "herbs_spices": row.herbs_spices,
            "cooking_methods": row.cooking_methods,
            "equipment": row.equipment,
            "prep_time": row.prep_time,
            "cook_time": row.cook_time,
            "total_time": row.total_time,
            "servings": row.servings,
            "base_servings": row.base_servings,
            "temperature": row.temperature,
            "texture": row.texture,
            "flavor_profile": row.flavor_profile,
            "dietary_tags": row.dietary_tags,
            "health_tags": row.health_tags,
            "season": row.season,
            "occasion": row.occasion,
            "skill_level": row.skill_level,
            "style_tags": row.style_tags,
            "prep_style": row.prep_style,
            "cloudinary_url": row.cloudinary_url,
            "thumbnail_url": row.thumbnail_url,
            "edited_fields": row.edited_fields,
            "archived": row.archived,
            "edited_by_user": row.edited_by_user,
            "is_recipe": row.is_recipe,
            "confidence": row.confidence,
            "extracted_at": ensure_utc(row.extracted_at),
            "model_used": row.model_used,
            "prompt_version": row.prompt_version,
        },
    )


class RecipeRepository:
    """DB-backed store for Recipe objects, keyed by recipe code."""

    def __init__(self, engine: Engine) -> None:
        """Bind the repository to a database engine."""
        self._engine = engine

    def get(self, code: str) -> Recipe | None:
        """Return the recipe for code, or None if it does not exist."""
        with get_session(self._engine) as session:
            row = session.get(RecipeRow, code)
            return _to_domain(row) if row is not None else None

    def exists(self, code: str) -> bool:
        """Return True if a recipe with code is stored."""
        with get_session(self._engine) as session:
            return session.get(RecipeRow, code) is not None

    def list_all(self) -> list[Recipe]:
        """Return every stored recipe, ordered by code."""
        with get_session(self._engine) as session:
            rows = session.exec(select(RecipeRow).order_by(RecipeRow.code)).all()
            return [_to_domain(row) for row in rows]

    def save(self, recipe: Recipe) -> None:
        """Insert or update recipe, preserving created_at on update."""
        now = datetime.now(tz=UTC)
        with get_session(self._engine) as session:
            existing = session.get(RecipeRow, recipe.code)
            created_at = existing.created_at if existing is not None else now
            session.merge(_to_row(recipe, created_at=created_at, updated_at=now))
            session.commit()
