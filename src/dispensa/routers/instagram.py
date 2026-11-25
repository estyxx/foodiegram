from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from dispensa.api_models import (
    PendingLinkOut,
    QueueCaption,
    QueueExtractResult,
    QueueLinkCreate,
)
from dispensa.app.queue import (
    QueuedLink,
    look_up_caption,
    queue_link,
    set_queued_caption,
)
from dispensa.app.queue_extraction import launch_queue_extraction
from dispensa.app.queue_import import (
    embed_imported,
    import_finished_queue,
    upload_imported_images,
)
from dispensa.app.queue_reextract import reextract_queued
from dispensa.deps import (
    CaptionFetcherDep,
    DepsDep,
    OpenAIClientDep,
    RecipeExtractorDep,
    SettingsDep,
    ThumbnailUploaderDep,
)
from dispensa.domain.errors import (
    ConfigurationError,
    ExtractionError,
    LinkAlreadyKnownError,
    PendingLinkNotFoundError,
)
from dispensa.domain.pending import PendingLink

router = APIRouter(prefix="/api/instagram")


def _to_out(link: PendingLink, *, lookup: str | None = None) -> PendingLinkOut:
    """Shape a domain pending link into its API response."""
    return PendingLinkOut(
        code=link.code,
        url=link.url,
        caption=link.caption,
        thumbnail_url=link.thumbnail_url,
        status=link.status.value,
        created_at=link.created_at,
        imported_at=link.imported_at,
        caption_lookup=lookup,
    )


def _queued_out(queued: QueuedLink) -> PendingLinkOut:
    """Shape a queued link with the outcome of its caption lookup."""
    lookup = queued.lookup.value if queued.lookup is not None else None
    return _to_out(queued.link, lookup=lookup)


async def _look_up(
    code: str,
    *,
    deps: DepsDep,
    fetch: CaptionFetcherDep,
) -> PendingLinkOut:
    """Run the caption lookup off the event loop: it waits on Instagram."""
    queued = await run_in_threadpool(
        look_up_caption,
        code=code,
        pending=deps.pending,
        fetch=fetch,
    )
    return _queued_out(queued)


@router.get("/queue")
async def list_queue(deps: DepsDep) -> list[PendingLinkOut]:
    """Return every link in the capture queue, newest first."""
    return [_to_out(link) for link in deps.pending.list_all()]


@router.post("/queue", status_code=201)
async def add_to_queue(
    body: QueueLinkCreate,
    deps: DepsDep,
    fetch: CaptionFetcherDep,
) -> PendingLinkOut:
    """Queue a shared Instagram URL and try to read its caption (D57).

    Idempotent per shortcode. A caption sent with the link is stored as is;
    otherwise the public post is read once, and the link waits for a pasted
    caption when Instagram refuses.
    """
    try:
        link = queue_link(
            url=body.url,
            now=datetime.now(tz=UTC),
            pending=deps.pending,
            recipes=deps.recipes,
        )
    except LinkAlreadyKnownError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if link.caption:
        return _to_out(link)
    if body.caption and body.caption.strip():
        pasted = set_queued_caption(
            code=link.code,
            caption=body.caption.strip(),
            pending=deps.pending,
        )
        return _to_out(pasted)
    if not body.read_caption:
        return _to_out(link)
    return await _look_up(link.code, deps=deps, fetch=fetch)


@router.post("/queue/{code}/caption-lookup")
async def retry_caption_lookup(
    code: str,
    deps: DepsDep,
    fetch: CaptionFetcherDep,
) -> PendingLinkOut:
    """Try reading a queued link's caption from Instagram again; 404 if unknown."""
    try:
        return await _look_up(code, deps=deps, fetch=fetch)
    except PendingLinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/queue/extract")
async def extract_queue(deps: DepsDep, settings: SettingsDep) -> QueueExtractResult:
    """Submit an OpenAI batch for the ready queue items (D56). Returns the count."""
    try:
        submitted = launch_queue_extraction(
            settings,
            pending=deps.pending,
            batches=deps.batches,
            now=datetime.now(tz=UTC),
        )
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return QueueExtractResult(count=submitted)


async def _finish_imports(
    *,
    deps: DepsDep,
    client: OpenAIClientDep,
    upload: ThumbnailUploaderDep,
    codes: set[str] | None = None,
) -> None:
    """Make imported recipes findable (embedding) and pictured (Cloudinary)."""
    await run_in_threadpool(
        embed_imported,
        pending=deps.pending,
        recipes=deps.recipes,
        client=client,
    )
    if upload is not None:
        await run_in_threadpool(
            upload_imported_images,
            pending=deps.pending,
            recipes=deps.recipes,
            upload=upload,
            codes=codes,
        )


@router.post("/queue/import")
async def import_queue(
    deps: DepsDep,
    settings: SettingsDep,
    client: OpenAIClientDep,
    upload: ThumbnailUploaderDep,
) -> QueueExtractResult:
    """Import a finished batch into recipes and mark the links imported. Count back.

    Then embeds the imported recipes, so semantic search and Claude can find
    them, and gives them a Cloudinary image; both also catch up on imports from
    before they were wired here.
    """
    try:
        imported = import_finished_queue(
            settings,
            pending=deps.pending,
            recipes=deps.recipes,
            extractions=deps.extractions,
            batches=deps.batches,
            now=datetime.now(tz=UTC),
        )
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await _finish_imports(deps=deps, client=client, upload=upload)
    return QueueExtractResult(count=imported)


@router.post("/queue/{code}/reextract")
async def reextract(
    code: str,
    body: QueueCaption,
    deps: DepsDep,
    extract: RecipeExtractorDep,
    client: OpenAIClientDep,
    upload: ThumbnailUploaderDep,
) -> PendingLinkOut:
    """Extract a queued link's recipe now from the given text, and embed it.

    The text replaces the caption: the post's own, or notes with the recipe
    from the comments or a website. Fields edited by hand keep their values.
    """
    try:
        link = await run_in_threadpool(
            reextract_queued,
            code=code,
            caption=body.caption,
            now=datetime.now(tz=UTC),
            pending=deps.pending,
            recipes=deps.recipes,
            extractions=deps.extractions,
            extract=extract,
        )
    except PendingLinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await _finish_imports(deps=deps, client=client, upload=upload, codes={code})
    return _to_out(link)


@router.patch("/queue/{code}")
async def paste_caption(code: str, body: QueueCaption, deps: DepsDep) -> PendingLinkOut:
    """Store the pasted caption on a queued link and mark it ready."""
    try:
        link = set_queued_caption(code=code, caption=body.caption, pending=deps.pending)
    except PendingLinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_out(link)


@router.delete("/queue/{code}", status_code=204)
async def remove_from_queue(code: str, deps: DepsDep) -> Response:
    """Remove a link from the capture queue; 404 if it is not queued."""
    if not deps.pending.delete(code):
        raise HTTPException(status_code=404, detail=f"No queued link {code!r}")
    return Response(status_code=204)
