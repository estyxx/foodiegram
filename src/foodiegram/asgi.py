import functools
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount, Route

from foodiegram.api import create_app
from foodiegram.deps import auth_from_settings, build_deps
from foodiegram.domain.errors import ConfigurationError
from foodiegram.mcp_server import mcp
from foodiegram.mcp_server.http import BearerTokenMiddleware
from foodiegram.settings import Settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# One exact path, served as a Route (not a Mount): a Mount would 307-redirect
# "/mcp" to "/mcp/", and that redirect hop can drop the Authorization header.
_MCP_PATH = "/mcp"


def build_asgi_app(*, settings: Settings) -> Starlette:
    """Assemble the served app: the API under Basic auth, plus /mcp under Bearer.

    A bare root mounts two self-contained apps. The API app keeps its own Basic
    auth and gzip; the root carries neither, so /mcp is gated only by the Bearer
    token and is never buffered or compressed. Refuses to build when
    MCP_AUTH_TOKEN is unset, so an unauthenticated MCP surface cannot ship.
    """
    token = settings.mcp_auth_token
    if not token:
        msg = "MCP_AUTH_TOKEN is required to serve the MCP endpoint over HTTP"
        raise ConfigurationError(msg)

    api_app = create_app(
        deps=build_deps(settings.database_url),
        auth=auth_from_settings(settings),
        cors_origins=settings.cors_origins(),
        frontend_dir=settings.frontend_dir,
        git_sha=settings.git_sha,
    )

    # Called for its side effect: it lazily creates the session manager, reachable
    # afterwards as mcp.session_manager. Stateless + JSON keeps each request
    # self-contained, which survives FastAPI Cloud autoscaling; DNS-rebinding
    # protection is off because the Bearer token, not a Host allow-list, guards
    # this endpoint (TLS terminates at the platform edge).
    mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )
    session_manager = mcp.session_manager
    guarded = BearerTokenMiddleware(session_manager.handle_request, token=token)

    @asynccontextmanager
    async def lifespan(_root: Starlette) -> AsyncIterator[None]:
        # Starlette does not run a mounted sub-app's lifespan, so enter both by
        # hand: the MCP session manager's task group (without it streamable HTTP
        # raises "task group not initialized"), then the API app's own lifespan.
        async with (
            session_manager.run(),
            api_app.router.lifespan_context(api_app),
        ):
            yield

    return Starlette(
        routes=[
            Route(_MCP_PATH, endpoint=guarded),
            Mount("/", app=api_app),
        ],
        lifespan=lifespan,
    )


@functools.cache
def _default_app() -> Starlette:
    """Build the composed app once from environment settings."""
    return build_asgi_app(settings=Settings())


def __getattr__(name: str) -> object:
    """Expose a lazily-built `app` so import needs neither the token nor a DB."""
    if name == "app":
        return _default_app()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
