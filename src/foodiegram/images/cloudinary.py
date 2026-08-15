import logging
from typing import TYPE_CHECKING

import cloudinary
import cloudinary.uploader
from pydantic import BaseModel, ConfigDict

from foodiegram.domain.errors import ImageUploadError

if TYPE_CHECKING:
    from foodiegram.settings import CloudinaryConfig

# All durable copies live in one Cloudinary folder; the public_id is the
# Instagram shortcode, so re-uploading a shortcode REPLACES its asset.
CLOUDINARY_FOLDER = "foodiegram"

# Instagram's signed CDN URLs (scontent-*.cdninstagram.*) are time-limited and
# stop resolving once the signature expires. A thumbnail_url starting with this
# prefix is "broken" and must be re-hosted. This is the single shared definition
# of a broken image reference; both image scripts and (later) `sync ingest`
# route their broken-detection through is_valid_image_ref / is_expired_cdn_url.
_EXPIRED_CDN_PREFIX = "https://scontent-man2-1.cdninstagram."

logger = logging.getLogger(__name__)


class UploadedImage(BaseModel):
    """Durable image copy returned by a Cloudinary upload."""

    model_config = ConfigDict(frozen=True)

    public_id: str
    secure_url: str


def configure(*, config: CloudinaryConfig) -> None:
    """Configure the Cloudinary SDK from the app's credential source."""
    cloudinary.config(
        cloud_name=config.cloud_name,
        api_key=config.api_key,
        api_secret=config.api_secret,
    )


def is_expired_cdn_url(ref: str) -> bool:
    """Return True when ref is a time-limited Instagram CDN URL that expires."""
    return ref.startswith(_EXPIRED_CDN_PREFIX)


def is_valid_image_ref(ref: str | None) -> bool:
    """Return True when ref is a usable image: present and not an expired CDN URL."""
    if ref is None or not ref.strip():
        return False
    return not is_expired_cdn_url(ref)


def upload_thumbnail(
    *,
    shortcode: str,
    source_url_or_path: str,
    overwrite: bool = True,
) -> UploadedImage:
    """Upload one image under a deterministic public_id and return the durable copy."""
    try:
        result: dict[str, object] = cloudinary.uploader.upload(
            source_url_or_path,
            public_id=shortcode,
            folder=CLOUDINARY_FOLDER,
            overwrite=overwrite,
            resource_type="image",
        )
    except Exception as exc:  # reason: cloudinary SDK raises heterogeneous errors
        msg = f"Cloudinary upload failed for {shortcode}: {exc}"
        raise ImageUploadError(msg) from exc

    secure_url = result.get("secure_url")
    public_id = result.get("public_id")
    if not isinstance(secure_url, str) or not isinstance(public_id, str):
        msg = f"Cloudinary response for {shortcode} missing secure_url/public_id"
        raise ImageUploadError(msg)

    return UploadedImage(public_id=public_id, secure_url=secure_url)
