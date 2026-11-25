import importlib
from typing import TYPE_CHECKING

from dispensa.instagram.public_caption import (
    CaptionFetch,
    CaptionOutcome,
    classify_refusal,
    fetch_public_caption,
)

if TYPE_CHECKING:
    from dispensa.instagram._auth import login_client
    from dispensa.instagram.cache_manager import CacheManager
    from dispensa.instagram.collection import Collection
    from dispensa.instagram.extractor import InstagramExtractor

# The logged-in tools need instagrapi, an optional extra the server does not
# install. They load on first use, so the server can import the public caption
# reader from this package without it.
_LOGGED_IN = {
    "login_client": "dispensa.instagram._auth",
    "CacheManager": "dispensa.instagram.cache_manager",
    "Collection": "dispensa.instagram.collection",
    "InstagramExtractor": "dispensa.instagram.extractor",
}

__all__ = [
    "CacheManager",
    "CaptionFetch",
    "CaptionOutcome",
    "Collection",
    "InstagramExtractor",
    "classify_refusal",
    "fetch_public_caption",
    "login_client",
]


def __getattr__(name: str) -> object:
    """Load a logged-in tool (and instagrapi) only when it is asked for."""
    module = _LOGGED_IN.get(name)
    if module is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    return getattr(importlib.import_module(module), name)
