import hmac
from typing import TYPE_CHECKING

from starlette.responses import JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

_SCHEME = "Bearer "


def _presented_token(scope: Scope) -> str | None:
    """Return the Bearer credential from the ASGI scope headers, or None.

    Reads only the header list on the scope; it never touches the receive stream,
    so the wrapped transport can still parse the request body itself.
    """
    for key, value in scope["headers"]:
        if key == b"authorization":
            header = value.decode("latin-1")
            return header.removeprefix(_SCHEME) if header.startswith(_SCHEME) else None
    return None


def _matches(presented: str | None, expected: str) -> bool:
    """Constant-time compare a presented token against the expected one."""
    if presented is None:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


class BearerTokenMiddleware:
    """ASGI middleware gating a single mount behind a static Bearer token.

    Header-only by design: it inspects `Authorization` and nothing else, so it
    never consumes the request body and cannot disturb the streamable-HTTP
    transport's own body parsing downstream.
    """

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        """Wrap app, requiring `Authorization: Bearer <token>` on HTTP requests."""
        self._app = app
        self._token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass HTTP requests through only with a valid token; otherwise 401."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        if not _matches(_presented_token(scope), self._token):
            response = JSONResponse(
                {"error": "unauthorized"},
                status_code=HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)
