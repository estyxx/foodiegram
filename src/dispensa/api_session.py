import hashlib
import hmac
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

LOGIN_COOKIE = "dispensa_login"
SESSION_SECONDS = 30 * 24 * 60 * 60
# A session secret shorter than this is refused at startup: the cookie's HMAC is
# only as strong as its key.
MIN_SECRET_LENGTH = 32
# subject.expires.signature
_TOKEN_PARTS = 3


class LoginConfig(BaseModel):
    """Everything the WorkOS web login needs; built only when fully configured."""

    model_config = ConfigDict(frozen=True)

    client_id: str
    api_key: str
    redirect_uri: str
    session_secret: str
    allowed_subjects: frozenset[str]


def _sign(*, secret: str, payload: str) -> str:
    """Return the hex HMAC-SHA256 of payload under the session secret."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue_login_session(*, secret: str, subject: str, now: float) -> str:
    """Return a signed token naming subject, valid for SESSION_SECONDS from now."""
    payload = f"{subject}.{int(now) + SESSION_SECONDS}"
    return f"{payload}.{_sign(secret=secret, payload=payload)}"


def login_subject(token: str | None, *, secret: str, now: float) -> str | None:
    """Return the subject of a genuine, unexpired session token, else None."""
    if not token:
        return None
    parts = token.rsplit(".", 2)
    if len(parts) != _TOKEN_PARTS:
        return None
    subject, expires_text, signature = parts
    expected = _sign(secret=secret, payload=f"{subject}.{expires_text}")
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        expires = int(expires_text)
    except ValueError:
        return None
    return subject if expires > now else None


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
