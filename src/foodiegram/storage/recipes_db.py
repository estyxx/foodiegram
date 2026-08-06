from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlmodel import select

from foodiegram.domain.models import Recipe
from foodiegram.domain.proteins import facets_for
from foodiegram.domain.synonyms import expand_term
from foodiegram.storage._tables import RecipeRow
from foodiegram.storage.db import ensure_utc, get_session

if TYPE_CHECKING:
    from sqlalchemy import Engine

    from foodiegram.domain.enums import (
        CuisineType,
        Difficulty,
        DishType,
        MealType,
        MedCategory,
    )


def _to_row(recipe: Recipe, *, created_at: datetime, updated_at: datetime) -> RecipeRow:
    """Map a domain Recipe to a storage row, serialising JSON fields."""
    dump = recipe.model_dump(mode="json")
    return RecipeRow(
        code=recipe.code,
        source=recipe.source.value,
        pk=recipe.pk,
        post_url=recipe.post_url,
        caption=recipe.caption,
        author_username=recipe.author_username,
        # The column is NOT NULL on every deployed database; empty is how it
        # spells absence, and the domain validator reads it back as None.
        title=recipe.title or "",
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
            "author_username": row.author_username,
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


def _matches_term(recipe: Recipe, term: str) -> bool:
    """Return True if term or a synonym appears in title, ingredients, or caption."""
    needles = {s.lower() for s in expand_term(term)}
    title = recipe.title or ""
    return (
        any(needle in title.lower() for needle in needles)
        or any(
            needle in ingredient.lower()
            for needle in needles
            for ingredient in recipe.ingredients
        )
        or (
            recipe.caption is not None
            and any(needle in recipe.caption.lower() for needle in needles)
        )
    )


def _filter_attributes(
    recipes: list[Recipe],
    *,
    cuisine: CuisineType | None,
    meal_type: MealType | None,
    dish_type: DishType | None,
    difficulty: Difficulty | None,
    is_recipe: bool | None,
) -> list[Recipe]:
    """Narrow recipes by whichever scalar attribute filters are set."""
    if cuisine is not None:
        recipes = [r for r in recipes if r.cuisine_type == cuisine]
    if meal_type is not None:
        recipes = [r for r in recipes if r.meal_type == meal_type]
    if dish_type is not None:
        recipes = [r for r in recipes if r.dish_type == dish_type]
    if difficulty is not None:
        recipes = [r for r in recipes if r.difficulty == difficulty]
    if is_recipe is not None:
        recipes = [r for r in recipes if r.is_recipe == is_recipe]
    return recipes


class RecipeRepository:
    """DB-backed store for Recipe objects, keyed by recipe code."""

    def __init__(self, engine: Engine) -> None:
        """Bind the repository to a database engine."""
        self._engine = engine
        # Prod is effectively read-only between deploys, so we cache the full,
        # deserialised recipe set for the process lifetime and rebuild it lazily
        # after any write. This turns repeated list/find calls (the browse page
        # loads every recipe) from a full table scan + Pydantic revalidation into
        # an in-memory read.
        self._all_cache: list[Recipe] | None = None

    def _invalidate(self) -> None:
        """Drop the cached recipe list so the next read reloads from the DB."""
        self._all_cache = None

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
        """Return every stored recipe, ordered by code (cached per process)."""
        if self._all_cache is None:
            with get_session(self._engine) as session:
                rows = session.exec(select(RecipeRow).order_by(RecipeRow.code)).all()
                self._all_cache = [_to_domain(row) for row in rows]
        # Return a shallow copy so callers can filter/sort without mutating the
        # cache; the Recipe elements themselves are frozen and safe to share.
        return list(self._all_cache)

    def save(self, recipe: Recipe) -> None:
        """Insert or update recipe, preserving created_at and user edits.

        If the stored copy has edited_by_user=True, its editing bookkeeping is
        kept — AI re-extraction must never overwrite a user's edits.
        """
        now = datetime.now(tz=UTC)
        with get_session(self._engine) as session:
            existing = session.get(RecipeRow, recipe.code)
            if existing is not None and existing.edited_by_user:
                recipe = recipe.model_copy(
                    update={
                        "edited_by_user": existing.edited_by_user,
                        "edited_fields": frozenset(existing.edited_fields),
                    },
                )
            created_at = existing.created_at if existing is not None else now
            session.merge(_to_row(recipe, created_at=created_at, updated_at=now))
            session.commit()
        self._invalidate()

    def delete(self, code: str) -> bool:
        """Delete the recipe for code; return True if deleted, False if absent."""
        with get_session(self._engine) as session:
            row = session.get(RecipeRow, code)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            self._invalidate()
            return True

    def find(
        self,
        *,
        cuisine: CuisineType | None = None,
        meal_type: MealType | None = None,
        dish_type: DishType | None = None,
        difficulty: Difficulty | None = None,
        is_recipe: bool | None = None,
        protein_categories: list[MedCategory] | None = None,
        dietary_tags: list[str] | None = None,
        proteins: list[str] | None = None,
        ingredients: list[str] | None = None,
        q: str | None = None,
    ) -> list[Recipe]:
        """Return recipes matching all non-None criteria.

        dietary_tags and proteins use ANY-match: a recipe passes if it contains
        at least one of the requested values (case-insensitive), with synonym
        expansion so e.g. "courgette" matches recipes tagged "zucchini".
        q is a case-insensitive substring match on title, caption, and
        ingredients, expanded via synonyms so "courgette" finds "zucchini" too.
        ingredients matches the same way but AND-wise: every term must appear,
        which is what the search chips send. An empty list means no filter.
        is_recipe=None keeps both real recipes and inspiration-only saves.
        protein_categories also ANY-matches, against the groups from
        proteins.facets_for. An empty list means no protein filter, as does None.
        """
        results = _filter_attributes(
            self.list_all(),
            cuisine=cuisine,
            meal_type=meal_type,
            dish_type=dish_type,
            difficulty=difficulty,
            is_recipe=is_recipe,
        )

        if protein_categories:
            wanted = set(protein_categories)
            results = [r for r in results if facets_for(r) & wanted]
        if dietary_tags is not None:
            expanded_tags = {s.lower() for t in dietary_tags for s in expand_term(t)}
            results = [
                r for r in results if expanded_tags & {t.lower() for t in r.dietary_tags}
            ]
        if proteins is not None:
            expanded_proteins = {s.lower() for p in proteins for s in expand_term(p)}
            results = [
                r for r in results if expanded_proteins & {p.lower() for p in r.proteins}
            ]
        if ingredients:
            results = [
                r for r in results if all(_matches_term(r, term) for term in ingredients)
            ]
        if q is not None:
            results = [r for r in results if _matches_term(r, q)]

        return results
