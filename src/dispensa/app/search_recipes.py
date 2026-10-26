from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from dispensa.ai.embeddings import EMBEDDING_MODEL, embed_texts
from dispensa.domain.models import Recipe
from dispensa.domain.pantry import KitchenMatch, kitchen_match

if TYPE_CHECKING:
    from openai import OpenAI

    from dispensa.domain.enums import (
        CuisineType,
        Difficulty,
        DishType,
        MealType,
        MedCategory,
    )
    from dispensa.storage.pantry_db import PantryRepository
    from dispensa.storage.recipes_db import RecipeRepository


def search_recipes_semantic(
    *,
    recipes: RecipeRepository,
    client: OpenAI,
    query: str,
    cuisine: CuisineType | None = None,
    meal_type: MealType | None = None,
    dish_type: DishType | None = None,
    difficulty: Difficulty | None = None,
    is_recipe: bool | None = None,
    complete: bool | None = None,
    protein_categories: list[MedCategory] | None = None,
    dietary_tags: list[str] | None = None,
    proteins: list[str] | None = None,
    ingredients: list[str] | None = None,
    limit: int = 8,
) -> list[tuple[Recipe, float]]:
    """Rank recipes by semantic similarity to query, optionally filtered by facets."""
    if not query.strip():
        return []

    query_vector = embed_texts([query], client=client, model=EMBEDDING_MODEL)[0]
    return recipes.find_similar(
        query_vector,
        cuisine=cuisine,
        meal_type=meal_type,
        dish_type=dish_type,
        difficulty=difficulty,
        is_recipe=is_recipe,
        complete=complete,
        protein_categories=protein_categories,
        dietary_tags=dietary_tags,
        proteins=proteins,
        ingredients=ingredients,
        limit=limit,
    )


class PlanningHit(BaseModel):
    """A ranked search hit with its ingredient lines split by the pantry."""

    model_config = ConfigDict(frozen=True)

    recipe: Recipe
    score: float
    pantry: KitchenMatch


def search_recipes_for_planning(
    *,
    recipes: RecipeRepository,
    pantry: PantryRepository,
    client: OpenAI,
    query: str,
    category: MedCategory | None,
    pantry_only: bool,
    limit: int,
) -> list[PlanningHit]:
    """Rank real recipes for a planning chat, each with its pantry have/missing split.

    category matches what the weekly balance counts (facets_for). With
    pantry_only, hits that use no pantry item are dropped before the limit is
    applied, so the shortlist is still full when enough recipes qualify; an
    empty pantry therefore yields no hits.
    """
    stock = pantry.list_all()
    ranked = search_recipes_semantic(
        recipes=recipes,
        client=client,
        query=query,
        is_recipe=True,
        protein_categories=[category] if category is not None else None,
        # find_similar scores every candidate anyway; take them all so the
        # pantry filter runs before the cut.
        limit=len(recipes.list_all()) if pantry_only else limit,
    )
    hits = [
        PlanningHit(
            recipe=recipe,
            score=score,
            pantry=kitchen_match(recipe.ingredients, stock),
        )
        for recipe, score in ranked
    ]
    if pantry_only:
        hits = [hit for hit in hits if hit.pantry.have]
    return hits[:limit]
