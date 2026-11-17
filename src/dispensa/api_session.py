import base64
import hashlib
import hmac
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, ValidationError

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

LOGIN_COOKIE = "dispensa_login"
SESSION_SECONDS = 30 * 24 * 60 * 60
# A session secret shorter than this is refused at startup: the cookie's HMAC is
# only as strong as its key.
MIN_SECRET_LENGTH = 32


class LoginConfig(BaseModel):
    """Everything the WorkOS web login needs; built only when fully configured."""

    model_config = ConfigDict(frozen=True)

    client_id: str
    api_key: str
    redirect_uri: str
    session_secret: str
    allowed_subjects: frozenset[str]


class LoginSession(BaseModel):
    """Who a session cookie belongs to: the WorkOS user id and their email."""

    model_config = ConfigDict(frozen=True)

    subject: str
    # Shown in the account menu only; access is decided by subject.
    email: str = ""


class _SessionClaims(BaseModel):
    """The signed cookie payload."""

    model_config = ConfigDict(frozen=True)

    sub: str
    email: str = ""
    exp: int


def _sign(*, secret: str, payload: str) -> str:
    """Return the hex HMAC-SHA256 of payload under the session secret."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue_login_session(*, secret: str, session: LoginSession, now: float) -> str:
    """Return a signed token for session, valid for SESSION_SECONDS from now."""
    claims = _SessionClaims(
        sub=session.subject,
        email=session.email,
        exp=int(now) + SESSION_SECONDS,
    )
    payload = base64.urlsafe_b64encode(claims.model_dump_json().encode()).decode()
    return f"{payload}.{_sign(secret=secret, payload=payload)}"


def read_login_session(
    token: str | None,
    *,
    secret: str,
    now: float,
) -> LoginSession | None:
    """Return the session of a genuine, unexpired token, else None."""
    if not token:
        return None
    payload, sep, signature = token.partition(".")
    if not sep:
        return None
    if not hmac.compare_digest(signature, _sign(secret=secret, payload=payload)):
        return None
    try:
        claims = _SessionClaims.model_validate_json(base64.urlsafe_b64decode(payload))
    except (ValueError, ValidationError):
        return None
    if claims.exp <= now:
        return None
    return LoginSession(subject=claims.sub, email=claims.email)


def is_https(request: Request) -> bool:
    """Return True when the client reached us over TLS, directly or via a proxy."""
    forwarded = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip()
    return request.url.scheme == "https" or forwarded == "https"


def set_session_cookie(
    response: Response,
    *,
    name: str,
    value: str,
    request: Request,
) -> None:
    """Set a 30-day HttpOnly cookie that never rides a cross-site request."""
    response.set_cookie(
        name,
        value,
        max_age=SESSION_SECONDS,
        httponly=True,
        samesite="strict",
        secure=is_https(request),
    )
