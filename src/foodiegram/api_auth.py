import base64
import binascii
import secrets
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.status import HTTP_401_UNAUTHORIZED

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request

_SCHEME = "Basic "
_REALM = 'Basic realm="dispensa"'


def _authorized(header: str | None, *, username: str, password: str) -> bool:
    """Return True if the Authorization header carries the expected credentials."""
    if header is None or not header.startswith(_SCHEME):
        return False
    try:
        decoded = base64.b64decode(header.removeprefix(_SCHEME), validate=True)
        candidate = decoded.decode("utf-8")
    except (binascii.Error, ValueError):
        return False
    got_user, sep, got_password = candidate.partition(":")
    if not sep:
        return False
    # Compute both comparisons before combining so timing does not leak which
    # half was wrong.
    user_ok = secrets.compare_digest(got_user, username)
    password_ok = secrets.compare_digest(got_password, password)
    return user_ok and password_ok


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Require HTTP Basic auth on every request when a username is configured."""

    def __init__(
        self,
        app: object,
        *,
        username: str,
        password: str,
    ) -> None:
        """Wrap app, enforcing credentials only when username is non-empty."""
        super().__init__(app)  # type: ignore[arg-type]  # reason: Starlette ASGIApp
        self._username = username
        self._password = password

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Pass through when auth is disabled, else demand valid credentials."""
        if not self._username:
            return await call_next(request)
        header = request.headers.get("Authorization")
        if not _authorized(
            header,
            username=self._username,
            password=self._password,
        ):
            return Response(
                status_code=HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": _REALM},
            )
        return await call_next(request)
