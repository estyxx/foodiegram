# in extract.py
from __future__ import annotations

import json
from pathlib import Path

from instagrapi import Client, Media
from pydantic import BaseModel

from cookstagram import env
from cookstagram.analyzer import RecipeAnalyzer
from cookstagram.types import Recipe


class InstagramExtractor(BaseModel):
    """Class to handle extraction of saved posts from Instagram."""

    _client: Client = None
    username: str
    password: str

    @property
    def client(self) -> Client:
        """Lazy load the Instagram client."""
        if getattr(self, "_client", None):
            return self._client

        self._client = Client()
        self._client.login(self.username, self.password)
        return self._client

    def extract_saved_posts(self, collection_id: int, limit: int = 10) -> list[Media]:
        """Extract saved posts from the user's Instagram account."""
        return self.client.collection_medias(collection_pk=collection_id, amount=limit)


def load_or_fetch_posts(collection_id: int, limit: int = 10) -> list[Media]:
    """Load posts from cache or fetch from Instagram."""
    cache_file = Path("posts_cache.json")
    if cache_file.exists():
        cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
        return [Media(**item) for item in cache.get(str(collection_id), [])]

    # If no cache exists, fetch new posts
    environment = env.Env.get_env()
    cl = InstagramExtractor(
        username=environment.INSTAGRAM_USERNAME,
        password=environment.INSTAGRAM_PASSWORD,
    )
    posts = cl.extract_saved_posts(collection_id=collection_id, limit=limit)

    Path("posts_cache.json").write_text(
        json.dumps([post.model_dump_json() for post in posts]),
    )
    return posts


def analyze_collection_recipes(
    environment: env.Env,
    collection_id: int,
    limit: int = 10,
) -> list[Recipe]:
    """Extract and analyze recipes from an Instagram collection."""
    # Get the posts
    posts = load_or_fetch_posts(collection_id, limit=limit)

    # Initialize analyzer
    analyzer = RecipeAnalyzer(openai_api_key=environment.OPENAI_API_KEY)

    # Analyze all posts
    recipes = analyzer.analyze_posts_batch(posts)

    # Save results
    output_file = Path("analyzed_recipes.json")
    recipes_data = [recipe.model_dump() for recipe in recipes]
    output_file.write_text(json.dumps(recipes_data, indent=2, default=str))

    print(f"Analysis complete! Results saved to {output_file}")
    print(
        f"Found {len([r for r in recipes if r.is_recipe])} recipes out of {len(posts)} posts",
    )

    return recipes


if __name__ == "__main__":
    environment = env.Env.get_env()
    analyze_collection_recipes(
        environment=environment,
        collection_id=environment.INSTAGRAM_COLLECTION_ID,
        limit=10,
    )
