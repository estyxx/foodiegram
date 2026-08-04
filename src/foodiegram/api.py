import functools
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from foodiegram.api_auth import BasicAuthMiddleware
from foodiegram.deps import AuthConfig, Deps, auth_from_settings, build_deps
from foodiegram.routers import pantry, plans, recipes, targets
from foodiegram.settings import Settings

logger = logging.getLogger(__name__)

_FRONTEND = Path(__file__).parent.parent.parent / "frontend"


def create_app(
    *,
    deps: Deps,
    auth: AuthConfig | None = None,
    cors_origins: list[str] | None = None,
    frontend_dir: Path | None = None,
) -> FastAPI:
    """Build a FastAPI app wired to deps, behind Basic auth and optional CORS."""
    auth = auth or AuthConfig()
    frontend = frontend_dir or _FRONTEND
    app = FastAPI(title="Foodiegram API")
    app.state.deps = deps

    app.add_middleware(
        BasicAuthMiddleware,
        username=auth.username,
        password=auth.password,
    )
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

    @app.get("/")
    async def serve_index() -> FileResponse:
        """Serve the frontend SPA."""
        return FileResponse(frontend / "index.html")

    app.mount("/", StaticFiles(directory=frontend), name="static")
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
        "foodiegram.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
