from __future__ import annotations

import json
import logging
from pathlib import Path

from instagrapi.types import Media

from foodiegram.types import Collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching of Instagram posts and collections."""

    def __init__(self, cache_dir: Path = Path("cache")) -> None:
        """Initialize cache directories."""
        self.cache_dir = cache_dir
        # Create directories if they don't exist
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        self.collections_dir.mkdir(parents=True, exist_ok=True)

    @property
    def posts_dir(self) -> Path:
        """Directory where posts are cached."""
        return self.cache_dir / "posts"

    @property
    def collections_dir(self) -> Path:
        """Directory where collections are cached."""
        return self.cache_dir / "collections"

    def get_post(self, post_pk: str) -> Media | None:
        """Get a single cached post by pk."""
        post_file = self.posts_dir / f"{post_pk}.json"
        if post_file.exists():
            try:
                return Media.model_validate_json(post_file.read_text())
            except Exception:
                logger.exception("Error loading cached post %s:", post_pk)
                return None
        return None

    def save_post(self, post: Media) -> None:
        """Save a single post to cache."""
        post_file = self.posts_dir / f"{post.pk}.json"
        post_file.write_text(post.model_dump_json())

    def get_collection(self, collection_id: int | str) -> Collection | None:
        """Get all posts in a collection."""
        collection_file = self.collections_dir / f"{collection_id}.json"

        if collection_file.exists():
            try:
                data = json.loads(collection_file.read_text())
                return Collection(**data)
            except Exception:
                logger.exception("Error loading collection %d:", collection_id)
                return None
        return None

    def save_collection(
        self,
        collection_id: int | str,
        posts: list[Media] | None = None,
        name: str = "",
        type_: str = "",
        media_count: int | None = None,
    ) -> Collection:
        """Save a collection of posts with metadata."""
        posts = posts or []
        if collection := self.get_collection(collection_id):
            if posts:
                collection.append_posts(posts)
            collection.name = name or collection.name
            collection.type = type_ or collection.type
            collection.media_count = media_count or collection.media_count
        else:
            collection = Collection(
                id=collection_id,
                post_pks=[str(post.pk) for post in posts],
                name=name,
                type=type_,
                media_count=media_count,
            )

        collection_file = self.collections_dir / f"{collection_id}.json"
        collection_file.write_text(collection.model_dump_json(indent=2))

        self.save_posts(posts)
        return collection

    def save_posts(self, posts: list[Media]) -> None:
        """Save multiple posts to cache."""
        for post in posts:
            self.save_post(post)
