from typing import TYPE_CHECKING

from foodiegram.ai.embeddings import EMBEDDING_MODEL, embed_texts

if TYPE_CHECKING:
    from openai import OpenAI

    from foodiegram.domain.enums import (
        CuisineType,
        Difficulty,
        DishType,
        MealType,
        MedCategory,
    )
    from foodiegram.domain.models import Recipe
    from foodiegram.storage.recipes_db import RecipeRepository


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
