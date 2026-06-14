# extract.py - Improved version with proper caching
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from instagrapi import Client
from instagrapi.exceptions import ClientError

from foodiegram._auth import login_client
from foodiegram.cache_manager import CacheManager
from foodiegram.domain import Collection
from foodiegram.domain.errors import InstagramFetchError
from foodiegram.settings import Settings

if TYPE_CHECKING:
    from instagrapi.types import Media

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path("cache")
_DEFAULT_GQL_DELAY = 1.5


class InstagramExtractor:
    """Class to handle extraction of saved posts from Instagram."""

    _settings: Settings
    cache_manager: CacheManager
    _client: Client | None = None

    def __init__(
        self,
        settings: Settings,
        cache_dir: Path = _DEFAULT_CACHE_DIR,
    ) -> None:
        """Initialize the extractor with settings and cache manager."""
        self._settings = settings
        self.cache_manager = CacheManager(cache_dir=cache_dir)

    @property
    def client(self) -> Client:
        """Lazy-load the Instagram client using the best-practices session pattern."""
        if self._client is not None:
            return self._client
        self._client = login_client(self._settings)
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
        collection_id: str,
        limit: int = 100,
        last_media_pk: int = 0,
    ) -> list[Media]:
        """Fetch posts from Instagram with pagination support and incremental caching."""
        logger.info("Fetching up to %d posts from collection %s", limit, collection_id)

        try:
            medias: list[Media] = self.client.collection_medias(
                collection_pk=collection_id,
                amount=limit,
                last_media_pk=last_media_pk,
            )
        except Exception:
            logger.exception("Error fetching batch")
            return []
        else:
            return medias

    @staticmethod
    def _make_public_client() -> Client:
        """Return an unauthenticated Client for public endpoint calls."""
        return Client()

    def _fetch_media(self, pk: str) -> Media:
        """Fetch fresh media info trying all available endpoints in order.

        Chain (instagrapi 2.10+):
          1. media_info_gql  — public; auto-falls-back query_hash → doc_id
          2. media_info_v1   — private mobile API (skipped if auth unavailable)
          3. media_info_v2   — private discover endpoint (last resort)

        Raises InstagramFetchError if every endpoint fails.
        """
        public_client = self._make_public_client()
        errors: list[str] = []

        logger.info("[%s] trying media_info_gql (public: query_hash→doc_id)", pk)
        try:
            media = public_client.media_info_gql(pk)
        except ClientError as exc:
            errors.append(f"media_info_gql: {exc}")
            logger.warning(
                "[%s] media_info_gql failed (%s: %s)",
                pk,
                type(exc).__name__,
                exc,
            )
        else:
            logger.info("[%s] media_info_gql succeeded", pk)
            return media

        # Private endpoints — only attempted when an authenticated client
        # is available; auth failure is not a hard error here.
        logger.info("[%s] public exhausted — attempting auth for private endpoints", pk)
        try:
            auth_client = self.client
        except Exception as exc:  # noqa: BLE001 — login_client raises many undocumented types
            logger.warning(
                "[%s] auth failed (%s: %s) — skipping private endpoints",
                pk,
                type(exc).__name__,
                exc,
            )
            msg = f"All public endpoints failed for PK {pk}: {'; '.join(errors)}"
            raise InstagramFetchError(msg) from None

        for method in ("media_info_v1", "media_info_v2"):
            logger.info("[%s] trying %s (private)", pk, method)
            try:
                media = getattr(auth_client, method)(pk)
            except ClientError as exc:
                errors.append(f"{method}: {exc}")
                logger.warning(
                    "[%s] %s failed (%s: %s)",
                    pk,
                    method,
                    type(exc).__name__,
                    exc,
                )
            else:
                logger.info("[%s] %s succeeded", pk, method)
                return media

        msg = f"All endpoints failed for PK {pk}: {'; '.join(errors)}"
        raise InstagramFetchError(msg)

    def fetch_posts_by_pks(
        self,
        pks: list[str],
        delay: float = _DEFAULT_GQL_DELAY,
    ) -> tuple[int, int, list[str]]:
        """Fetch media info for each uncached PK; skip ones already in cache.

        Tries gql (doc_id fallback) → v1 → v2. Returns (fetched, skipped, failed_pks).
        """
        total = len(pks)
        fetched = 0
        skipped = 0
        failed: list[str] = []

        for i, pk in enumerate(pks, start=1):
            if self.cache_manager.get_post(pk) is not None:
                skipped += 1
                logger.debug("[%d/%d] %s already cached — skipping", i, total, pk)
                continue
            logger.info(
                "[%d/%d] fetching pk=%s  (fetched=%d failed=%d)",
                i,
                total,
                pk,
                fetched,
                len(failed),
            )
            try:
                media: Media = self._fetch_media(pk)
                self.cache_manager.save_post(media)
                fetched += 1
                logger.info("[%d/%d] saved pk=%s", i, total, pk)
            except (InstagramFetchError, ClientError):
                logger.exception("[%d/%d] failed pk=%s", i, total, pk)
                failed.append(pk)
            time.sleep(delay)

        return fetched, skipped, failed

    def refresh_cached_posts(
        self,
        delay: float = _DEFAULT_GQL_DELAY,
    ) -> tuple[int, list[str]]:
        """Re-fetch every cached post to renew expired CDN URLs.

        Overwrites each cache file with fresh data. Returns (refreshed,
        failed_pks).
        """
        pks = [
            f.stem for f in self.cache_manager.posts_dir.iterdir() if f.suffix == ".json"
        ]
        total = len(pks)
        logger.info("Refreshing %d cached posts", total)
        refreshed = 0
        failed: list[str] = []

        for i, pk in enumerate(pks, start=1):
            logger.info(
                "[%d/%d] refreshing pk=%s  (ok=%d failed=%d)",
                i,
                total,
                pk,
                refreshed,
                len(failed),
            )
            try:
                media: Media = self._fetch_media(pk)
                self.cache_manager.save_post(media)
                refreshed += 1
                logger.info("[%d/%d] refreshed pk=%s", i, total, pk)
            except (InstagramFetchError, ClientError):
                logger.exception("[%d/%d] failed to refresh pk=%s", i, total, pk)
                failed.append(pk)
            time.sleep(delay)

        return refreshed, failed

    # Keep old name as alias so existing callers don't break.
    fetch_posts_by_pks_gql = fetch_posts_by_pks


def load_or_fetch_collection(
    environment: Settings,
    collection_id: str,
    limit: int = 100,
    cache_dir: Path = _DEFAULT_CACHE_DIR,
) -> Collection:
    """Load posts from cache or fetch from Instagram with smart caching."""
    logger.info("Fetching posts from Instagram for collection %s", collection_id)
    cache_manager = CacheManager(cache_dir=cache_dir)

    if collection := cache_manager.get_collection(collection_id):
        logger.info("Loaded collection %s from cache", collection_id)
        return collection

    extractor = InstagramExtractor(environment, cache_dir=cache_dir)

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
        "Successfully fetched/loaded %d posts for collection %s",
        len(posts),
        collection_id,
    )
    return collection
