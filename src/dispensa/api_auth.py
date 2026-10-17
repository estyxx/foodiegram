import base64
import binascii
import hashlib
import hmac
import re
import secrets
import time
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.status import HTTP_401_UNAUTHORIZED

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request

_SCHEME = "Basic "
_REALM = 'Basic realm="dispensa"'

# Remember-me: phones (iOS home-screen apps especially) drop cached Basic
# credentials, so every reload re-prompts. After one valid Basic login we also set
# a signed cookie, which browsers keep across restarts. It carries only an expiry
# and an HMAC of it; the key is derived from the credentials, so changing the
# password invalidates every outstanding cookie without any new secret to manage.
_COOKIE_NAME = "dispensa_session"
_SESSION_SECONDS = 30 * 24 * 60 * 60
_KEY_SALT = b"dispensa-session-v1"
# scrypt (16 MiB at these settings) makes guessing the password from a leaked
# cookie costly; it runs once at startup, never per request.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_BYTES = 32

# A recipe's own code doubles as its share secret: send someone the
# /#recipe/{code} link and this is the one GET it takes to render it, no
# password required. The static SPA shell has to be exempt too, or the page
# can't even load for a recipient with no credentials. Everything else — the
# recipe list, every mutation, every other endpoint — still needs the password.
# "count" is excluded: /api/recipes/count is the aggregate-stats route, not a
# recipe code, even though it has the same single-segment shape.
_PUBLIC_RECIPE_DETAIL = re.compile(r"^/api/recipes/(?!count$)[^/]+$")


def _is_public(request: Request) -> bool:
    """Return True for the SPA shell and a single recipe's read-only detail GET."""
    if request.method != "GET":
        return False
    path = request.url.path
    return not path.startswith("/api/") or bool(_PUBLIC_RECIPE_DETAIL.match(path))


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


def _session_key(*, username: str, password: str) -> bytes:
    """Derive the cookie-signing key from the credentials."""
    return hashlib.scrypt(
        password.encode(),
        salt=_KEY_SALT + b"|" + username.encode(),
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_BYTES,
    )


def _sign(key: bytes, *, expires: int) -> str:
    """Return the hex HMAC-SHA256 of an expiry timestamp."""
    return hmac.new(key, str(expires).encode(), hashlib.sha256).hexdigest()


def _issue_session(key: bytes, *, now: float) -> str:
    """Return a session token that expires _SESSION_SECONDS after now."""
    expires = int(now) + _SESSION_SECONDS
    return f"{expires}.{_sign(key, expires=expires)}"


def _session_valid(token: str | None, *, key: bytes, now: float) -> bool:
    """Return True if token carries a genuine signature and has not expired."""
    if not token:
        return False
    expires_text, sep, signature = token.partition(".")
    if not sep:
        return False
    try:
        expires = int(expires_text)
    except ValueError:
        return False
    signature_ok = hmac.compare_digest(signature, _sign(key, expires=expires))
    return signature_ok and expires > now


def _is_https(request: Request) -> bool:
    """Return True when the client reached us over TLS, directly or via a proxy."""
    forwarded = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip()
    return request.url.scheme == "https" or forwarded == "https"


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Require HTTP Basic auth, or its remember-me cookie, except on public pages."""

    def __init__(
        self,
        app: object,
        *,
        username: str,
        password: str,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Wrap app, enforcing credentials only when username is non-empty.

        clock is injectable so tests can move time; production uses wall time.
        """
        super().__init__(app)  # type: ignore[arg-type]  # reason: Starlette ASGIApp
        self._username = username
        self._password = password
        self._clock = clock
        self._key = (
            _session_key(username=username, password=password) if username else b""
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Pass through when auth is off or the request is public; else demand creds."""
        if not self._username or _is_public(request):
            return await call_next(request)
        now = self._clock()
        basic_ok = _authorized(
            request.headers.get("Authorization"),
            username=self._username,
            password=self._password,
        )
        cookie_ok = _session_valid(
            request.cookies.get(_COOKIE_NAME),
            key=self._key,
            now=now,
        )
        if not (basic_ok or cookie_ok):
            return Response(
                status_code=HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": _REALM},
            )
        response = await call_next(request)
        if basic_ok:
            # Strict: the SPA is same-origin, so the cookie never needs to ride a
            # cross-site request (which also narrows CSRF compared with Basic).
            response.set_cookie(
                _COOKIE_NAME,
                _issue_session(self._key, now=now),
                max_age=_SESSION_SECONDS,
                httponly=True,
                samesite="strict",
                secure=_is_https(request),
            )
        return response
