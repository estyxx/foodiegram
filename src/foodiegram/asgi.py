import functools
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
from mcp.server.auth.middleware.bearer_auth import (
    BearerAuthBackend,
    RequireAuthMiddleware,
)
from mcp.server.auth.routes import (
    build_resource_metadata_url,
    create_protected_resource_routes,
)
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.routing import Mount, Route

from foodiegram.api import create_app
from foodiegram.deps import auth_from_settings, build_deps
from foodiegram.mcp_server import mcp
from foodiegram.mcp_server.auth import JwtTokenVerifier, oauth_config
from foodiegram.settings import Settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from mcp.server.auth.provider import TokenVerifier

# One exact path, served as a Route (not a Mount): a Mount would 307-redirect
# "/mcp" to "/mcp/", and that redirect hop can drop the Authorization header.
_MCP_PATH = "/mcp"


def build_asgi_app(
    *,
    settings: Settings,
    token_verifier: TokenVerifier | None = None,
) -> Starlette:
    """Assemble the served app: the API under Basic auth, plus /mcp under OAuth 2.1.

    A bare root mounts two self-contained apps. The API app keeps its own Basic
    auth and gzip; the root carries neither, so /mcp is gated only by the bearer
    JWT and is never buffered or compressed. Refuses to build unless the OAuth env
    is set, so an unauthenticated MCP surface cannot ship. token_verifier is
    injectable for tests; production builds a JWKS-backed verifier from settings.
    """
    oauth = oauth_config(settings)
    verifier = token_verifier or JwtTokenVerifier(
        jwks_uri=oauth.jwks_uri,
        issuer=oauth.issuer,
        audience=oauth.resource_url,
    )
    resource_url = AnyHttpUrl(oauth.resource_url)
    resource_metadata_url = build_resource_metadata_url(resource_url)

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
    # protection is off because the JWT audience, not a Host allow-list, guards
    # this endpoint (TLS terminates at the platform edge).
    mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )
    session_manager = mcp.session_manager

    # The same chain the SDK's own authed app builds, but wrapped around our single
    # Route so we keep the no-307/stateless guarantees: authenticate the bearer
    # (header-only) -> expose it to tools -> require a valid token, answering 401
    # with a WWW-Authenticate pointing at the protected-resource metadata.
    guarded_mcp = AuthenticationMiddleware(
        AuthContextMiddleware(
            RequireAuthMiddleware(
                session_manager.handle_request,
                oauth.required_scopes,
                resource_metadata_url,
            ),
        ),
        backend=BearerAuthBackend(verifier),
    )

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
            Route(_MCP_PATH, endpoint=guarded_mcp),
            # Public metadata, so it sits before the api mount (outside Basic auth)
            # and resolves at the origin root: /.well-known/oauth-protected-resource/mcp.
            *create_protected_resource_routes(
                resource_url=resource_url,
                authorization_servers=[AnyHttpUrl(oauth.issuer)],
                scopes_supported=oauth.required_scopes or None,
            ),
            Mount("/", app=api_app),
        ],
        lifespan=lifespan,
    )


@functools.cache
def _default_app() -> Starlette:
    """Build the composed app once from environment settings."""
    return build_asgi_app(settings=Settings())


def __getattr__(name: str) -> object:
    """Expose a lazily-built `app` so import needs neither the env nor a DB."""
    if name == "app":
        return _default_app()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
