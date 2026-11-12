from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from dispensa.api_models import (
    PendingLinkOut,
    QueueCaption,
    QueueExtractResult,
    QueueLinkCreate,
)
from dispensa.app.queue import queue_link, set_queued_caption
from dispensa.app.queue_extraction import launch_queue_extraction
from dispensa.app.queue_import import import_finished_queue
from dispensa.deps import DepsDep, SettingsDep
from dispensa.domain.errors import (
    ConfigurationError,
    LinkAlreadyKnownError,
    PendingLinkNotFoundError,
)
from dispensa.domain.pending import PendingLink

router = APIRouter(prefix="/api/instagram")


def _to_out(link: PendingLink) -> PendingLinkOut:
    """Shape a domain pending link into its API response."""
    return PendingLinkOut(
        code=link.code,
        url=link.url,
        caption=link.caption,
        thumbnail_url=link.thumbnail_url,
        status=link.status.value,
        created_at=link.created_at,
    )


@router.get("/queue")
async def list_queue(deps: DepsDep) -> list[PendingLinkOut]:
    """Return every link in the capture queue, newest first."""
    return [_to_out(link) for link in deps.pending.list_all()]


@router.post("/queue", status_code=201)
async def add_to_queue(body: QueueLinkCreate, deps: DepsDep) -> PendingLinkOut:
    """Queue a shared Instagram URL; idempotent per shortcode."""
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
    return _to_out(link)


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


@router.post("/queue/import")
async def import_queue(deps: DepsDep, settings: SettingsDep) -> QueueExtractResult:
    """Import a finished batch into recipes and mark the links imported. Count back."""
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
    return QueueExtractResult(count=imported)


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
