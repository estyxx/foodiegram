# extract.py - Improved version with proper caching
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from instagrapi import Client

from foodiegram.cache_manager import CacheManager
from foodiegram.types import Collection

if TYPE_CHECKING:
    from instagrapi.types import Media

    from foodiegram import env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InstagramExtractor:
    """Class to handle extraction of saved posts from Instagram."""

    _client: Client = None
    username: str
    password: str
    cache_manager: CacheManager

    def __init__(
        self,
        username: str,
        password: str,
    ) -> None:
        """Initialize the extractor with credentials and cache manager."""
        self.username = username
        self.password = password
        self.cache_manager = CacheManager()

    @property
    def client(self) -> Client:
        """Lazy load the Instagram client."""
        if getattr(self, "_client", None):
            return self._client

        self._client = Client()
        self._client.login(self.username, self.password)
        return self._client

    def fetch_collections(self) -> list[Collection]:
        """Fetch all collections from Instagram."""
        logger.info("Fetching collections from Instagram")
        collections: list[Collection] = []
        try:
            collections_data = self.client.collections()
            for collection_data in collections_data:
                logger.info(
                    "Found collection: %s (ID: %s) with %s items",
                    collection_data.name,
                    str(collection_data.id),
                    str(collection_data.media_count),
                )

                collection = Collection(
                    id=collection_data.id,
                    name=collection_data.name,
                    type=collection_data.type,
                    media_count=int(collection_data.media_count)
                    if collection_data.media_count
                    else None,
                )

                self.cache_manager.save_collection(
                    collection_id=collection.id,
                    posts=[],
                    name=collection.name,
                    type_=collection.type,
                    media_count=collection.media_count,
                )
                collections.append(collection)
        except Exception:
            logger.exception("Error fetching collections")
            return []
        else:
            return collections

    def fetch_collection_posts(
        self,
        collection_id: int,
        limit: int = 100,
        last_media_pk: int = 0,
    ) -> list[Media]:
        """Fetch posts from Instagram with pagination support and incremental caching."""
        logger.info("Fetching up to %d posts from collection %d", limit, collection_id)

        try:
            return self.client.collection_medias(
                collection_pk=collection_id,
                amount=limit,
                last_media_pk=last_media_pk,
            )
        except Exception:
            logger.exception("Error fetching batch")
            return []

        return []


def load_or_fetch_collection(
    environment: env.Env,
    collection_id: int,
    limit: int = 100,
) -> Collection:
    """Load posts from cache or fetch from Instagram with smart caching."""
    logger.info("Fetching posts from Instagram for collection %d", collection_id)
    cache_manager = CacheManager()

    if collection := cache_manager.get_collection(collection_id):
        logger.info("Loaded collection %d from cache", collection_id)
        return collection

    extractor = InstagramExtractor(
        username=environment.INSTAGRAM_USERNAME,
        password=environment.INSTAGRAM_PASSWORD,
    )

    posts = []
    fetched = 0
    # Fetch posts from Instagram
    if not (collection := cache_manager.get_collection(collection_id)):
        collection = Collection(id=collection_id, post_pks=[])

    while fetched < limit:
        batch_limit = min(1000, limit - fetched)
        batch = extractor.fetch_collection_posts(
            collection_id=collection_id,
            limit=batch_limit,
        )
        if not batch:
            break
        posts.extend(batch)
        fetched += len(batch)
        collection = cache_manager.save_collection(collection_id, batch)

    logger.info(
        "Successfully fetched/loaded %d posts for collection %d",
        len(posts),
        collection_id,
    )
    return collection
