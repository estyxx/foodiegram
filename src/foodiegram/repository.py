"""Repository pattern implementation for data persistence."""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from foodiegram.domain import Recipe
from foodiegram.types import Collection

logger = logging.getLogger(__name__)


class Repository[T](ABC):
    """Abstract base class for repositories."""

    def __init__(self, data_dir: Path) -> None:
        """Initialize repository with data directory."""
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def save(self, entity: T) -> None:
        """Save an entity."""

    @abstractmethod
    def get(self, entity_id: str) -> T | None:
        """Get an entity by ID."""

    @abstractmethod
    def list_all(self) -> list[T]:
        """List all entities."""

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """Delete an entity by ID."""


class RecipeRepository(Repository[Recipe]):
    """Repository for managing individual recipe files."""

    def __init__(self, data_dir: Path = Path("data")) -> None:
        """Initialize recipe repository."""
        super().__init__(data_dir)
        self.recipes_dir = self.data_dir / "recipes"
        self.recipes_dir.mkdir(parents=True, exist_ok=True)

    def save(self, recipe: Recipe) -> None:
        """Save a recipe to an individual JSON file keyed by its shortcode."""
        recipe_file = self.recipes_dir / f"{recipe.code}.json"
        recipe_file.write_text(recipe.model_dump_json(indent=2))
        logger.info("Saved recipe %s to %s", recipe.code, recipe_file)

    def get(self, recipe_id: str) -> Recipe | None:
        """Get a recipe by shortcode."""
        recipe_file = self.recipes_dir / f"{recipe_id}.json"
        if not recipe_file.exists():
            return None
        try:
            data = json.loads(recipe_file.read_text())
            data.pop("_metadata", None)
            return Recipe.model_validate(data)
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.exception("Error loading recipe %s", recipe_id)
            return None

    def list_all(self) -> list[Recipe]:
        """List all recipes."""
        recipes = []
        for recipe_file in self.recipes_dir.glob("*.json"):
            try:
                recipe = self.get(recipe_file.stem)
                if recipe:
                    recipes.append(recipe)
            except (json.JSONDecodeError, ValueError, KeyError):
                logger.exception("Error loading recipe from %s", recipe_file)
        return recipes

    def delete(self, recipe_id: str) -> bool:
        """Delete a recipe by shortcode."""
        recipe_file = self.recipes_dir / f"{recipe_id}.json"
        if recipe_file.exists():
            recipe_file.unlink()
            logger.info("Deleted recipe %s", recipe_id)
            return True
        return False

    def get_by_cuisine(self, cuisine_type: str) -> list[Recipe]:
        """Get recipes by cuisine type."""
        return [r for r in self.list_all() if r.cuisine_type == cuisine_type]

    def get_by_difficulty(self, difficulty: str) -> list[Recipe]:
        """Get recipes by difficulty level."""
        return [r for r in self.list_all() if r.difficulty == difficulty]

    def search_by_ingredients(self, ingredients: list[str]) -> list[Recipe]:
        """Search recipes containing specific ingredients."""
        results = []
        for recipe in self.list_all():
            recipe_ingredients = [ing.lower() for ing in recipe.ingredients]
            if any(ing.lower() in recipe_ingredients for ing in ingredients):
                results.append(recipe)
        return results


class CollectionRepository(Repository[Collection]):
    """Repository for managing collection files."""

    def __init__(self, data_dir: Path = Path("data")) -> None:
        """Initialize collection repository."""
        super().__init__(data_dir)
        self.collections_dir = self.data_dir / "collections"
        self.collections_dir.mkdir(parents=True, exist_ok=True)

    def _collection_file(self, collection_id: str) -> Path:
        """Return the path for a collection file."""
        return self.collections_dir / f"instagram_collection_{collection_id}.json"

    def save(self, collection: Collection) -> None:
        """Save a collection to JSON file."""
        collection_file = self._collection_file(str(collection.id))
        collection_data = collection.model_dump()
        collection_data["_metadata"] = {"file_path": str(collection_file)}
        collection_file.write_text(
            json.dumps(collection_data, indent=2, ensure_ascii=False),
        )
        logger.info("Saved collection %s to %s", collection.id, collection_file)

    def get(self, collection_id: str) -> Collection | None:
        """Get a collection by ID."""
        collection_file = self._collection_file(collection_id)
        if not collection_file.exists():
            return None
        try:
            data = json.loads(collection_file.read_text())
            data.pop("_metadata", None)
            return Collection.model_validate(data)
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.exception("Error loading collection %s", collection_id)
            return None

    def list_all(self) -> list[Collection]:
        """List all collections."""
        collections = []
        for collection_file in self.collections_dir.glob(
            "instagram_collection_*.json",
        ):
            try:
                collection_id = collection_file.stem.replace(
                    "instagram_collection_",
                    "",
                )
                collection = self.get(collection_id)
                if collection:
                    collections.append(collection)
            except (json.JSONDecodeError, ValueError, KeyError):
                logger.exception(
                    "Error loading collection from %s",
                    collection_file,
                )
        return collections

    def delete(self, collection_id: str) -> bool:
        """Delete a collection by ID."""
        collection_file = self._collection_file(collection_id)
        if collection_file.exists():
            collection_file.unlink()
            logger.info("Deleted collection %s", collection_id)
            return True
        return False


class MetadataIndex:
    """Manages metadata index for search and discovery."""

    def __init__(self, data_dir: Path = Path("data")) -> None:
        """Initialize metadata index."""
        self.data_dir = data_dir
        self.index_file = data_dir / "index.json"
        self._load_index()

    def _load_index(self) -> None:
        """Load existing index or create new one."""
        if self.index_file.exists():
            try:
                self.index: dict[str, Any] = json.loads(
                    self.index_file.read_text(),
                )
            except (json.JSONDecodeError, ValueError):
                logger.exception("Error loading index")
                self.index = self._create_empty_index()
        else:
            self.index = self._create_empty_index()

    def _create_empty_index(self) -> dict[str, Any]:
        """Create empty index structure."""
        return {
            "version": "1.0",
            "created_at": None,
            "last_updated": None,
            "total_recipes": 0,
            "total_collections": 0,
            "recipes": {},
            "collections": {},
            "search_index": {
                "cuisines": {},
                "difficulties": {},
                "dietary_tags": {},
                "ingredients": {},
                "cooking_methods": {},
            },
        }

    def add_recipe(self, recipe: Recipe) -> None:
        """Add recipe to index."""
        recipe_id = recipe.code
        self.index["recipes"][recipe_id] = {
            "code": recipe.code,
            "pk": recipe.pk,
            "title": recipe.title,
            "cuisine_type": recipe.cuisine_type,
            "difficulty": recipe.difficulty,
            "dietary_tags": recipe.dietary_tags,
            "ingredients": recipe.ingredients,
            "cooking_methods": recipe.cooking_methods,
            "post_url": recipe.post_url,
            "saved_at": None,
        }
        self._update_search_index(recipe)
        self.index["total_recipes"] = len(self.index["recipes"])
        self.index["last_updated"] = None

    def add_collection(self, collection: Collection) -> None:
        """Add collection to index."""
        collection_id = str(collection.id)
        self.index["collections"][collection_id] = {
            "id": collection.id,
            "name": collection.name,
            "type": collection.type,
            "media_count": collection.media_count,
            "post_count": len(collection.post_pks),
            "saved_at": None,
        }
        self.index["total_collections"] = len(self.index["collections"])
        self.index["last_updated"] = None

    def _index_list_field(
        self,
        bucket: str,
        keys: list[str],
        recipe_id: str,
    ) -> None:
        """Add recipe_id to each key's list in the given search_index bucket."""
        for key in keys:
            ids: list[str] = self.index["search_index"][bucket].setdefault(
                key,
                [],
            )
            if recipe_id not in ids:
                ids.append(recipe_id)

    def _update_search_index(self, recipe: Recipe) -> None:
        """Update search index with recipe data."""
        recipe_id = recipe.code
        self._index_list_field("cuisines", [recipe.cuisine_type], recipe_id)
        self._index_list_field("difficulties", [recipe.difficulty], recipe_id)
        self._index_list_field("dietary_tags", recipe.dietary_tags, recipe_id)
        self._index_list_field(
            "ingredients",
            [i.lower() for i in recipe.ingredients],
            recipe_id,
        )
        self._index_list_field(
            "cooking_methods",
            recipe.cooking_methods,
            recipe_id,
        )

    def save(self) -> None:
        """Save index to file."""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        if not self.index["created_at"]:
            self.index["created_at"] = now
        self.index["last_updated"] = now
        self.index_file.write_text(
            json.dumps(self.index, indent=2, ensure_ascii=False),
        )
        logger.info("Saved metadata index to %s", self.index_file)

    def search_recipes(self, **filters: str) -> list[str]:
        """Search for recipe IDs based on filters."""
        recipe_ids = set(self.index["recipes"].keys())
        bucket_map = {
            "cuisine": "cuisines",
            "difficulty": "difficulties",
            "dietary_tag": "dietary_tags",
            "cooking_method": "cooking_methods",
        }
        for filter_key, bucket in bucket_map.items():
            if filter_key in filters:
                recipe_ids &= set(
                    self.index["search_index"][bucket].get(
                        filters[filter_key],
                        [],
                    ),
                )
        if "ingredient" in filters:
            recipe_ids &= set(
                self.index["search_index"]["ingredients"].get(
                    filters["ingredient"].lower(),
                    [],
                ),
            )
        return list(recipe_ids)

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        si = self.index["search_index"]
        return {
            "total_recipes": self.index["total_recipes"],
            "total_collections": self.index["total_collections"],
            "cuisines": list(si["cuisines"].keys()),
            "difficulties": list(si["difficulties"].keys()),
            "dietary_tags": list(si["dietary_tags"].keys()),
            "unique_ingredients": len(si["ingredients"]),
            "cooking_methods": list(si["cooking_methods"].keys()),
        }
