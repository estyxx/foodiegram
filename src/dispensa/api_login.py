import logging
import secrets
from typing import TYPE_CHECKING, Annotated, Protocol
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, ValidationError

from dispensa.api_session import (
    LOGIN_COOKIE,
    LoginConfig,
    is_https,
    issue_login_session,
    set_session_cookie,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_AUTHORIZE_URL = "https://api.workos.com/user_management/authorize"
_AUTHENTICATE_URL = "https://api.workos.com/user_management/authenticate"
_EXCHANGE_TIMEOUT_SECONDS = 10.0

# The state cookie ties the callback to the browser that started the login. It
# must survive the cross-site redirect back from WorkOS, hence Lax, not Strict.
_STATE_COOKIE = "dispensa_login_state"
_STATE_SECONDS = 10 * 60
_STATE_SEPARATOR = "|"
# Pages a login may return to. A fixed list, so `next` can never be an open
# redirect to another site.
_RETURN_PATHS = frozenset({"/", "/schiena.html"})
_DEFAULT_RETURN = "/"


class LoginUser(BaseModel):
    """The signed-in person as WorkOS reports them."""

    model_config = ConfigDict(frozen=True)

    id: str
    email: str = ""


class _AuthenticateResponse(BaseModel):
    """The part of the WorkOS authenticate response the login reads."""

    model_config = ConfigDict(frozen=True)

    user: LoginUser


class LoginExchangeError(Exception):
    """WorkOS refused the authorization code, or could not be reached."""


class CodeExchanger(Protocol):
    """Trade a one-time authorization code for the user it was issued to."""

    async def exchange(self, code: str) -> LoginUser:
        """Return the user for code; raise LoginExchangeError on any failure."""
        ...


class WorkOSCodeExchanger:
    """Exchange an AuthKit authorization code with the WorkOS API."""

    def __init__(self, *, client_id: str, api_key: str) -> None:
        """Bind the exchanger to one WorkOS application."""
        self._client_id = client_id
        self._api_key = api_key

    async def exchange(self, code: str) -> LoginUser:
        """Return the user for code; raise LoginExchangeError on any failure."""
        payload = {
            "client_id": self._client_id,
            "client_secret": self._api_key,
            "grant_type": "authorization_code",
            "code": code,
        }
        try:
            async with httpx.AsyncClient(timeout=_EXCHANGE_TIMEOUT_SECONDS) as client:
                response = await client.post(_AUTHENTICATE_URL, json=payload)
            response.raise_for_status()
            return _AuthenticateResponse.model_validate(response.json()).user
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            # The response body is not logged: it can carry tokens.
            logger.warning("WorkOS code exchange failed: %s", type(exc).__name__)
            msg = "Could not complete the sign-in"
            raise LoginExchangeError(msg) from exc


def _return_path(candidate: str | None) -> str:
    """Return candidate when it is a known page, else the home page."""
    return candidate if candidate in _RETURN_PATHS else _DEFAULT_RETURN


def build_login_router(
    *,
    config: LoginConfig,
    exchanger: CodeExchanger,
    clock: Callable[[], float],
) -> APIRouter:
    """Build the /auth routes: start a WorkOS login, finish it, and sign out."""
    router = APIRouter(prefix="/auth")

    @router.get("/login")
    async def login(
        request: Request,
        return_to: Annotated[str | None, Query(alias="next")] = None,
    ) -> Response:
        """Send the browser to the hosted sign-in page, remembering where to return."""
        state = secrets.token_urlsafe(32)
        query = urlencode(
            {
                "response_type": "code",
                "client_id": config.client_id,
                "redirect_uri": config.redirect_uri,
                "provider": "authkit",
                "state": state,
            },
        )
        response = RedirectResponse(f"{_AUTHORIZE_URL}?{query}", status_code=303)
        response.set_cookie(
            _STATE_COOKIE,
            f"{state}{_STATE_SEPARATOR}{_return_path(return_to)}",
            max_age=_STATE_SECONDS,
            httponly=True,
            samesite="lax",
            secure=is_https(request),
            path="/auth",
        )
        return response

    @router.get("/callback")
    async def callback(
        request: Request,
        code: str | None = None,
        state: str | None = None,
    ) -> Response:
        """Finish the login: check the state, exchange the code, set the session."""
        expected, _, return_to = request.cookies.get(_STATE_COOKIE, "").partition(
            _STATE_SEPARATOR,
        )
        if not code or not state or not expected:
            raise HTTPException(status_code=400, detail="Sign-in was not started here")
        if not secrets.compare_digest(state, expected):
            raise HTTPException(status_code=400, detail="Sign-in state does not match")
        try:
            user = await exchanger.exchange(code)
        except LoginExchangeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if user.id not in config.allowed_subjects:
            # The id is an opaque WorkOS user id, not a secret; logging it is how
            # the owner finds the id to add to the allow-list.
            logger.warning("Refused sign-in: user %r is not allowed", user.id)
            raise HTTPException(status_code=403, detail="This account is not allowed")
        response = RedirectResponse(_return_path(return_to), status_code=303)
        response.delete_cookie(_STATE_COOKIE, path="/auth")
        set_session_cookie(
            response,
            name=LOGIN_COOKIE,
            value=issue_login_session(
                secret=config.session_secret,
                subject=user.id,
                now=clock(),
            ),
            request=request,
        )
        return response

    @router.post("/logout", status_code=204)
    async def logout() -> Response:
        """Sign out of this browser by dropping the session cookie."""
        response = Response(status_code=204)
        response.delete_cookie(LOGIN_COOKIE)
        return response

    return router
