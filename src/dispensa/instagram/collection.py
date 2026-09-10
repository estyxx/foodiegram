from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from instagrapi.types import Media


class Collection(BaseModel):
    """Data model for an Instagram collection."""

    id: int | str
    post_pks: list[str] = []
    last_media_pk: int = 0
    name: str = ""
    type: str = ""
    media_count: int | None = None

    def append_posts(self, posts: list[Media]) -> None:
        """Append new posts to the collection."""
        self.post_pks.extend(str(post.pk) for post in posts)
        if posts:
            self.last_media_pk = int(posts[-1].pk)
