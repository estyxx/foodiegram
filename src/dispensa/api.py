import functools
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from dispensa.api_auth import BasicAuthMiddleware
from dispensa.deps import AuthConfig, Deps, auth_from_settings, build_deps
from dispensa.routers import exercise_log, meta, pantry, plans, recipes, targets
from dispensa.settings import Settings

if TYPE_CHECKING:
    import os
    from collections.abc import Callable

    from starlette.responses import Response
    from starlette.types import Scope

logger = logging.getLogger(__name__)

_FRONTEND = Path(__file__).parent.parent.parent / "frontend"

# Static files are not fingerprinted, so a deploy replaces them in place. "no-cache"
# lets the browser keep a copy but check its ETag on every use (a cheap 304, and a
# public request, so it never triggers a login). With no header at all browsers
# guess freshness from Last-Modified and can show a stale page for days.
_REVALIDATE = "no-cache"


class _RevalidatingStaticFiles(StaticFiles):
    """Static files the browser may store but must revalidate on every use."""

    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        """Serve the file with Cache-Control: no-cache (also kept on a 304)."""
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["Cache-Control"] = _REVALIDATE
        return response


def create_app(
    *,
    deps: Deps,
    auth: AuthConfig | None = None,
    cors_origins: list[str] | None = None,
    frontend_dir: Path | None = None,
    git_sha: str = "",
    clock: Callable[[], float] = time.time,
) -> FastAPI:
    """Build a FastAPI app wired to deps, behind Basic auth and optional CORS."""
    auth = auth or AuthConfig()
    frontend = frontend_dir or _FRONTEND
    app = FastAPI(title="Dispensa API")
    app.state.deps = deps
    app.state.git_sha = git_sha

    app.add_middleware(
        BasicAuthMiddleware,
        username=auth.username,
        password=auth.password,
        clock=clock,
    )
    # The all-recipes list is a large JSON payload; compress it (and the JS/CSS)
    # so transfer time doesn't dominate load on slower connections.
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    # The SPA is served same-origin, so CORS stays off unless an explicit
    # allowlist is configured; never pair credentials with a wildcard origin.
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(recipes.router)
    app.include_router(plans.router)
    app.include_router(pantry.router)
    app.include_router(targets.router)
    app.include_router(meta.router)
    app.include_router(exercise_log.router)

    @app.get("/")
    async def serve_index() -> FileResponse:
        """Serve the frontend SPA."""
        return FileResponse(
            frontend / "index.html",
            headers={"Cache-Control": _REVALIDATE},
        )

    app.mount("/", _RevalidatingStaticFiles(directory=frontend), name="static")
    return app


@functools.cache
def _default_app() -> FastAPI:
    """Build the production app from environment settings, once per process."""
    settings = Settings()
    return create_app(
        deps=build_deps(settings.database_url),
        auth=auth_from_settings(settings),
        cors_origins=settings.cors_origins(),
        frontend_dir=settings.frontend_dir,
        git_sha=settings.git_sha,
    )


def __getattr__(name: str) -> object:
    """Expose a lazily-built `app` for uvicorn without import-time side effects."""
    if name == "app":
        return _default_app()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def main() -> None:
    """Start the API server using host/port from Settings."""
    settings = Settings()
    uvicorn.run(
        "dispensa.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
