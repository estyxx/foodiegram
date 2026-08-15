import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from foodiegram.domain.hashing import caption_hash
from foodiegram.domain.models import Recipe
from foodiegram.images import is_valid_image_ref

if TYPE_CHECKING:
    from pathlib import Path

    from foodiegram.images import UploadedImage
    from foodiegram.storage.recipes_db import RecipeRepository

logger = logging.getLogger(__name__)

# The public, non-expiring thumbnail endpoint for a shortcode. Instagram CDN
# URLs expire; this one resolves to a fresh image every time and is what we
# hand to Cloudinary as the upload source.
STABLE_MEDIA_URL = "https://www.instagram.com/p/{code}/media/?size=l"
POST_URL = "https://instagram.com/p/{code}/"
_OK_STATUSES = frozenset({"ok", "dry_run"})
_URL_MARKERS = ("/p/", "/reel/", "/tv/")


class ThumbnailUploader(Protocol):
    """Uploads one image to durable hosting and returns its stored copy."""

    def __call__(
        self,
        *,
        shortcode: str,
        source_url_or_path: str,
        overwrite: bool = ...,
    ) -> UploadedImage:
        """Upload the source image for shortcode and return the durable copy."""
        ...


@dataclass(frozen=True)
class FoodItem:
    """One reconciled entry parsed from an IGbulkDL food.json log."""

    shortcode: str
    pk: str | None
    author: str | None
    caption: str | None
    title: str | None
    thumbnail_url: str


def shortcode_from_url(url: str) -> str | None:
    """Return the Instagram shortcode embedded in a post/reel URL, or None."""
    for marker in _URL_MARKERS:
        if marker in url:
            tail = url.split(marker, 1)[1]
            code = tail.split("/", 1)[0].split("?", 1)[0].strip()
            return code or None
    return None


def parse_food_items(*, path: Path) -> list[FoodItem]:
    """Parse an IGbulkDL food.json log into reconcilable items (status ok only)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    items: list[FoodItem] = []
    for entry in raw.get("items", []):
        if entry.get("status") not in _OK_STATUSES:
            continue
        shortcode = entry["shortcode"]
        items.append(
            FoodItem(
                shortcode=shortcode,
                pk=str(entry["username"]) if entry.get("username") else None,
                author=entry.get("author") or None,
                caption=entry.get("caption") or None,
                title=entry.get("title") or None,
                thumbnail_url=STABLE_MEDIA_URL.format(code=shortcode),
            ),
        )
    return items


@dataclass(frozen=True)
class DedupeReport:
    """Outcome of cleaning an IGbulkCollector links file against the DB."""

    read: int
    unique: int
    already_in_db: int
    written_urls: tuple[str, ...]

    @property
    def written(self) -> int:
        """Number of URLs kept in the cleaned output file."""
        return len(self.written_urls)


def dedupe_links(*, links_file: Path, known_codes: set[str]) -> DedupeReport:
    """Drop duplicate and already-stored shortcodes from a links file.

    Keeps the first URL seen per shortcode, drops later duplicates, and drops
    any shortcode already present in the database. Pure over its two inputs.
    """
    lines = [
        line.strip()
        for line in links_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    seen: set[str] = set()
    written: list[str] = []
    already_in_db = 0
    for url in lines:
        code = shortcode_from_url(url)
        if code is None or code in seen:
            continue
        seen.add(code)
        if code in known_codes:
            already_in_db += 1
            continue
        written.append(url)
    return DedupeReport(
        read=len(lines),
        unique=len(seen),
        already_in_db=already_in_db,
        written_urls=tuple(written),
    )


@dataclass(frozen=True)
class IngestItemResult:
    """What ingest did (or would do, under dry-run) for one food.json item."""

    code: str
    is_new: bool
    caption_changed: bool
    image_fixed: bool

    @property
    def unchanged(self) -> bool:
        """True when the item needed no create, caption, or image action."""
        return not (self.is_new or self.caption_changed or self.image_fixed)


@dataclass(frozen=True)
class IngestReport:
    """Per-item results and roll-up counts for one ingest run."""

    results: tuple[IngestItemResult, ...]

    @property
    def new(self) -> int:
        """Count of newly created recipe stubs."""
        return sum(1 for r in self.results if r.is_new)

    @property
    def caption_changed(self) -> int:
        """Count of known recipes whose caption was refreshed."""
        return sum(1 for r in self.results if r.caption_changed and not r.is_new)

    @property
    def image_fixed(self) -> int:
        """Count of recipes whose durable image was (re)uploaded."""
        return sum(1 for r in self.results if r.image_fixed)

    @property
    def unchanged(self) -> int:
        """Count of items that needed no action."""
        return sum(1 for r in self.results if r.unchanged)

    @property
    def codes_needing_extraction(self) -> list[str]:
        """New or caption-changed codes to feed the extraction stage next."""
        return [r.code for r in self.results if r.is_new or r.caption_changed]


def _stub(item: FoodItem) -> Recipe:
    """Build a minimal recipe stub for a not-yet-seen food.json item."""
    return Recipe(
        code=item.shortcode,
        pk=item.pk,
        post_url=POST_URL.format(code=item.shortcode),
        caption=item.caption,
        author_username=item.author,
        title=item.title,
        ingredients=[],
        instructions=[],
        thumbnail_url=item.thumbnail_url,
        model_used="imported",
    )


def _reconcile_item(
    *,
    recipes: RecipeRepository,
    item: FoodItem,
    upload: ThumbnailUploader,
    dry_run: bool,
) -> IngestItemResult:
    """Compute independent new/caption/image flags for one item and apply them."""
    existing = recipes.get(item.shortcode)
    is_new = existing is None

    if existing is None:
        recipe = _stub(item)
        caption_changed = False
    else:
        recipe = existing
        caption_changed = caption_hash(item.caption) != caption_hash(existing.caption)
        if caption_changed:
            recipe = recipe.model_copy(update={"caption": item.caption})

    image_fixed = not is_valid_image_ref(recipe.cloudinary_url)
    if image_fixed and not dry_run:
        source = STABLE_MEDIA_URL.format(code=item.shortcode)
        uploaded = upload(shortcode=item.shortcode, source_url_or_path=source)
        recipe = recipe.model_copy(
            update={"cloudinary_url": uploaded.secure_url, "thumbnail_url": source},
        )

    if not dry_run and (is_new or caption_changed or image_fixed):
        recipes.save(recipe)

    return IngestItemResult(
        code=item.shortcode,
        is_new=is_new,
        caption_changed=caption_changed,
        image_fixed=image_fixed,
    )


def ingest_food_json(
    *,
    recipes: RecipeRepository,
    items: list[FoodItem],
    upload: ThumbnailUploader,
    dry_run: bool = False,
) -> IngestReport:
    """Reconcile food.json items against the DB, upserting stubs and fixing images.

    Each item gets three independent flags: new (create a stub, persisting the
    author), caption_changed (refresh caption + hash when it differs), and
    image_missing_or_broken (upload a durable copy via the injected uploader).
    """
    results = [
        _reconcile_item(recipes=recipes, item=item, upload=upload, dry_run=dry_run)
        for item in items
    ]
    return IngestReport(results=tuple(results))
