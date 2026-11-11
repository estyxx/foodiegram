from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, Query
from starlette.requests import Request

from dispensa.app.version import VersionInfo, resolve_version
from dispensa.deps import DepsDep

router = APIRouter(prefix="/api")


@router.get("/version")
async def get_version(request: Request) -> VersionInfo:
    """Return the deployed application version and source commit."""
    git_sha = cast("str", request.app.state.git_sha)
    return resolve_version(git_sha)


@router.get("/health")
async def health(
    deps: DepsDep,
    deep: Annotated[int, Query()] = 0,
) -> dict[str, str]:
    """Report liveness; with deep=1, also that the database answers.

    The shallow check is public and touches nothing, so a free uptime monitor can
    poll it often. The deep check does one DB read and sits behind auth, so it
    neither exposes the database nor wakes it on every anonymous request.
    """
    if not deep:
        return {"status": "ok"}
    if not deps.targets.ping():
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ok", "database": "ok"}
