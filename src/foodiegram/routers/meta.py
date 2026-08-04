from typing import cast

from fastapi import APIRouter
from starlette.requests import Request

from foodiegram.app.version import VersionInfo, resolve_version

router = APIRouter(prefix="/api")


@router.get("/version")
async def get_version(request: Request) -> VersionInfo:
    """Return the deployed application version and source commit."""
    git_sha = cast("str", request.app.state.git_sha)
    return resolve_version(git_sha)
