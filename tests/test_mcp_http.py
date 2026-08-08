from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from foodiegram.asgi import build_asgi_app
from foodiegram.domain.errors import ConfigurationError
from foodiegram.mcp_server.http import BearerTokenMiddleware
from foodiegram.settings import Settings

if TYPE_CHECKING:
    from starlette.types import Receive, Scope, Send

_TOKEN = "s3cret-token"


async def _ok(scope: Scope, receive: Receive, send: Send) -> None:
    """Return 200 once auth has passed (a trivial downstream ASGI app)."""
    await JSONResponse({"ok": True})(scope, receive, send)


def _client(token: str) -> TestClient:
    """Build a one-route app whose endpoint sits behind the Bearer middleware."""
    guarded = BearerTokenMiddleware(_ok, token=token)
    app = Starlette(routes=[Route("/mcp", endpoint=guarded)])
    return TestClient(app)


def test_missing_authorization_header_is_rejected() -> None:
    """No Authorization header yields a 401 with a JSON body and the challenge."""
    response = _client(_TOKEN).get("/mcp")
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"error": "unauthorized"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_wrong_token_is_rejected() -> None:
    """A Bearer header with the wrong token is rejected."""
    response = _client(_TOKEN).get("/mcp", headers={"Authorization": "Bearer nope"})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_non_bearer_scheme_is_rejected() -> None:
    """A non-Bearer scheme (e.g. Basic) is rejected even with the right value."""
    response = _client(_TOKEN).get("/mcp", headers={"Authorization": f"Basic {_TOKEN}"})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_valid_token_passes_through() -> None:
    """A correct Bearer token reaches the downstream app."""
    response = _client(_TOKEN).get("/mcp", headers={"Authorization": f"Bearer {_TOKEN}"})
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"ok": True}


def test_build_asgi_app_requires_token(tmp_path: Path) -> None:
    """Assembling the composed app fails fast when MCP_AUTH_TOKEN is unset."""
    settings = Settings(
        mcp_auth_token="",
        database_url=f"sqlite:///{tmp_path / 'dispensa.db'}",
    )
    with pytest.raises(ConfigurationError, match="MCP_AUTH_TOKEN"):
        build_asgi_app(settings=settings)


def test_composed_app_gates_mcp_but_not_api(tmp_path: Path) -> None:
    """/mcp requires the Bearer token; the API surface does not."""
    settings = Settings(
        mcp_auth_token=_TOKEN,
        database_url=f"sqlite:///{tmp_path / 'dispensa.db'}",
    )
    app = build_asgi_app(settings=settings)
    with TestClient(app) as client:
        # /mcp is Bearer-gated: the middleware answers 401 before the transport.
        unauth = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert unauth.status_code == HTTPStatus.UNAUTHORIZED
        # The API surface (here the SPA index) is reachable without a Bearer token.
        index = client.get("/")
        assert index.status_code == HTTPStatus.OK
