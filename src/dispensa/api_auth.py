import base64
import binascii
import hashlib
import hmac
import re
import secrets
import time
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_401_UNAUTHORIZED

from dispensa.api_session import (
    LOGIN_COOKIE,
    SESSION_SECONDS,
    LoginConfig,
    LoginSession,
    issue_login_session,
    read_login_session,
    set_session_cookie,
)

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
_SESSION_SECONDS = SESSION_SECONDS
# Where the SPA sends a signed-out visitor when the web login is on.
LOGIN_PATH = "/auth/login"
LOGOUT_PATH = "/auth/logout"
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
# The fixed routes under /api/recipes/ share the single-segment shape of a
# recipe code but are not one: count (aggregate stats), index (the whole slim
# library, D27) and semantic (an OpenAI-billed search) all stay private. No
# Instagram shortcode or m-{slug}-{suffix} code can collide with these names.
_RECIPE_DETAIL = re.compile(r"^/api/recipes/([^/]+)$")
_RESERVED_RECIPE_ROUTES = frozenset({"count", "index", "semantic"})
_HEALTH_PATH = "/api/health"


def _is_public(request: Request) -> bool:
    """Return True for the SPA shell, the shallow health check, and a recipe GET."""
    if request.method != "GET":
        return False
    path = request.url.path
    if not path.startswith("/api/"):
        return True
    # Liveness stays open; the deep (DB-reading) health check does not.
    if path == _HEALTH_PATH and request.query_params.get("deep") in (None, "", "0"):
        return True
    match = _RECIPE_DETAIL.match(path)
    return match is not None and match.group(1) not in _RESERVED_RECIPE_ROUTES


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


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Require a web-login session or HTTP Basic auth, except on public pages."""

    def __init__(
        self,
        app: object,
        *,
        username: str,
        password: str,
        login: LoginConfig | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Wrap app, enforcing auth when a username or a login config is given.

        clock is injectable so tests can move time; production uses wall time.
        """
        super().__init__(app)  # type: ignore[arg-type]  # reason: Starlette ASGIApp
        self._username = username
        self._password = password
        self._login = login
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
        if (not self._username and self._login is None) or _is_public(request):
            return await call_next(request)
        now = self._clock()
        session = self._signed_in(request, now=now)
        if self._login is not None and session is not None:
            response = await call_next(request)
            if request.url.path == LOGOUT_PATH:
                # Renewing here would undo the sign-out the route just did.
                return response
            # Sliding expiry: an app opened at least monthly stays signed in.
            set_session_cookie(
                response,
                name=LOGIN_COOKIE,
                value=issue_login_session(
                    secret=self._login.session_secret,
                    session=session,
                    now=now,
                ),
                request=request,
            )
            return response
        if not self._basic_ok(request, now=now):
            return self._unauthorized()
        response = await call_next(request)
        # Renew the Basic remember-me cookie on any authenticated request.
        set_session_cookie(
            response,
            name=_COOKIE_NAME,
            value=_issue_session(self._key, now=now),
            request=request,
        )
        return response

    def _signed_in(self, request: Request, *, now: float) -> LoginSession | None:
        """Return the request's login session when its subject is allow-listed.

        The allow-list is checked on every request, so removing a subject signs
        that person out at once.
        """
        if self._login is None:
            return None
        session = read_login_session(
            request.cookies.get(LOGIN_COOKIE),
            secret=self._login.session_secret,
            now=now,
        )
        if session is None or session.subject not in self._login.allowed_subjects:
            return None
        return session

    def _basic_ok(self, request: Request, *, now: float) -> bool:
        """Return True for valid Basic credentials or their remember-me cookie."""
        if not self._username:
            return False
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
        return basic_ok or cookie_ok

    def _unauthorized(self) -> Response:
        """Answer 401: point at the web login when it is on, else challenge Basic.

        With the web login on there is no Basic challenge header, so the browser
        never pops its password prompt; explicit Basic credentials still work.
        """
        if self._login is not None:
            return JSONResponse(
                {"detail": "Sign in required", "login_url": LOGIN_PATH},
                status_code=HTTP_401_UNAUTHORIZED,
            )
        return Response(
            status_code=HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": _REALM},
        )
