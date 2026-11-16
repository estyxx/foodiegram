from http import HTTPStatus
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from dispensa.api import create_app
from dispensa.api_login import LoginExchangeError, LoginUser
from dispensa.api_session import LoginConfig
from dispensa.deps import AuthConfig, Deps, login_from_settings
from dispensa.domain.errors import ConfigurationError
from dispensa.settings import Settings
from dispensa.storage.batches_db import BatchRepository
from dispensa.storage.exercise_log_db import ExerciseLogRepository
from dispensa.storage.extractions_db import ExtractionRepository
from dispensa.storage.pantry_db import PantryRepository
from dispensa.storage.pending_db import PendingLinkRepository
from dispensa.storage.plans_db import PlanRepository
from dispensa.storage.recipes_db import RecipeRepository
from dispensa.storage.targets_db import TargetRepository
from dispensa.storage.user_state_db import UserStateRepository

_SECRET = "s" * 40
_OWNER = "user_owner"
_THIRTY_DAYS = 30 * 24 * 60 * 60
_CONFIG = LoginConfig(
    client_id="client_123",
    api_key="sk_test",
    redirect_uri="https://dispensa.example/auth/callback",
    session_secret=_SECRET,
    allowed_subjects=frozenset({_OWNER}),
)


class _FakeExchanger:
    """Stand in for WorkOS: maps known codes to users, refuses the rest."""

    def __init__(self) -> None:
        self.users = {
            "owner-code": LoginUser(id=_OWNER, email="owner@example.com"),
            "stranger-code": LoginUser(id="user_stranger"),
        }

    async def exchange(self, code: str) -> LoginUser:
        """Return the user for a known code; raise for anything else."""
        if code not in self.users:
            msg = "Could not complete the sign-in"
            raise LoginExchangeError(msg)
        return self.users[code]


class _Clock:
    """A movable wall clock, so session expiry is tested without sleeping."""

    def __init__(self) -> None:
        self.now = 1_800_000_000.0

    def __call__(self) -> float:
        """Return the current fake time."""
        return self.now


def _client(
    db_engine: Engine,
    *,
    clock: _Clock | None = None,
    auth: AuthConfig | None = None,
) -> TestClient:
    """Build a login-enabled client that does not follow redirects."""
    app = create_app(
        deps=Deps(
            recipes=RecipeRepository(db_engine),
            extractions=ExtractionRepository(db_engine),
            user_state=UserStateRepository(db_engine),
            plans=PlanRepository(db_engine),
            pantry=PantryRepository(db_engine),
            targets=TargetRepository(db_engine),
            exercise_log=ExerciseLogRepository(db_engine),
            pending=PendingLinkRepository(db_engine),
            batches=BatchRepository(db_engine),
        ),
        auth=auth,
        login=_CONFIG,
        exchanger=_FakeExchanger(),
        clock=clock or _Clock(),
    )
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


def _start(client: TestClient, *, path: str = "/auth/login") -> str:
    """Start a login and return the state WorkOS would echo back."""
    response = client.get(path)
    assert response.status_code == HTTPStatus.SEE_OTHER
    return parse_qs(urlparse(response.headers["location"]).query)["state"][0]


def _sign_in(client: TestClient, *, code: str = "owner-code") -> None:
    """Run the whole login as the owner."""
    state = _start(client)
    response = client.get("/auth/callback", params={"code": code, "state": state})
    assert response.status_code == HTTPStatus.SEE_OTHER


def test_signed_out_api_call_points_at_the_login(db_engine: Engine) -> None:
    """A 401 names the login URL and carries no Basic challenge to pop a prompt."""
    response = _client(db_engine).get("/api/targets")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["login_url"] == "/auth/login"
    assert "WWW-Authenticate" not in response.headers


def test_login_redirects_to_workos_with_a_state_cookie(db_engine: Engine) -> None:
    """Starting a login sends the browser to AuthKit and remembers the state."""
    response = _client(db_engine).get("/auth/login")

    location = urlparse(response.headers["location"])
    query = parse_qs(location.query)
    assert location.netloc == "api.workos.com"
    assert query["client_id"] == ["client_123"]
    assert query["redirect_uri"] == ["https://dispensa.example/auth/callback"]
    assert query["provider"] == ["authkit"]
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" in cookie


def test_owner_signs_in_and_reaches_the_api(db_engine: Engine) -> None:
    """A full login sets a hardened 30-day session that authorizes API calls."""
    client = _client(db_engine)
    state = _start(client)

    response = client.get(
        "/auth/callback", params={"code": "owner-code", "state": state}
    )

    assert response.headers["location"] == "/"
    session = next(
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith("dispensa_login=")
    )
    assert "HttpOnly" in session
    assert "SameSite=strict" in session
    assert "Secure" in session
    assert f"Max-Age={_THIRTY_DAYS}" in session
    assert client.get("/api/targets").status_code == HTTPStatus.OK


def test_a_stranger_is_refused(db_engine: Engine) -> None:
    """A valid WorkOS account that is not on the allow-list gets no session."""
    client = _client(db_engine)
    state = _start(client)

    response = client.get(
        "/auth/callback",
        params={"code": "stranger-code", "state": state},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert client.get("/api/targets").status_code == HTTPStatus.UNAUTHORIZED


def test_callback_rejects_a_wrong_or_missing_state(db_engine: Engine) -> None:
    """The callback only finishes a login this browser started."""
    client = _client(db_engine)
    _start(client)

    forged = client.get("/auth/callback", params={"code": "owner-code", "state": "x"})
    cold = _client(db_engine).get(
        "/auth/callback",
        params={"code": "owner-code", "state": "x"},
    )

    assert forged.status_code == HTTPStatus.BAD_REQUEST
    assert cold.status_code == HTTPStatus.BAD_REQUEST


def test_a_refused_code_is_a_bad_gateway(db_engine: Engine) -> None:
    """When WorkOS rejects the code the login fails without a session."""
    client = _client(db_engine)
    state = _start(client)

    response = client.get("/auth/callback", params={"code": "nope", "state": state})

    assert response.status_code == HTTPStatus.BAD_GATEWAY
    assert client.get("/api/targets").status_code == HTTPStatus.UNAUTHORIZED


def test_session_expires_and_slides(db_engine: Engine) -> None:
    """Use within 30 days renews the session; a longer gap ends it."""
    clock = _Clock()
    client = _client(db_engine, clock=clock)
    _sign_in(client)

    clock.now += _THIRTY_DAYS - 60
    assert client.get("/api/targets").status_code == HTTPStatus.OK
    clock.now += _THIRTY_DAYS - 60
    assert client.get("/api/targets").status_code == HTTPStatus.OK
    clock.now += _THIRTY_DAYS + 60
    assert client.get("/api/targets").status_code == HTTPStatus.UNAUTHORIZED


def test_a_tampered_session_is_refused(db_engine: Engine) -> None:
    """Changing the subject inside the cookie breaks its signature."""
    client = _client(db_engine)
    _sign_in(client)
    genuine = client.cookies.get("dispensa_login") or ""
    client.cookies.clear()
    client.cookies.set("dispensa_login", genuine.replace(_OWNER, "user_other"))

    assert client.get("/api/targets").status_code == HTTPStatus.UNAUTHORIZED


def test_logout_drops_the_session(db_engine: Engine) -> None:
    """Signing out clears the cookie, so the next call is signed out."""
    client = _client(db_engine)
    _sign_in(client)

    assert client.post("/auth/logout").status_code == HTTPStatus.NO_CONTENT
    assert client.get("/api/targets").status_code == HTTPStatus.UNAUTHORIZED


def test_login_returns_only_to_known_pages(db_engine: Engine) -> None:
    """`next` picks a known page; anything else falls back to home."""
    client = _client(db_engine)
    state = _start(client, path="/auth/login?next=/schiena.html")
    known = client.get("/auth/callback", params={"code": "owner-code", "state": state})

    other = _client(db_engine)
    state = _start(other, path="/auth/login?next=https://evil.example/")
    unknown = other.get("/auth/callback", params={"code": "owner-code", "state": state})

    assert known.headers["location"] == "/schiena.html"
    assert unknown.headers["location"] == "/"


def test_share_link_and_shell_stay_public(db_engine: Engine) -> None:
    """The SPA shell and a recipe link need no sign-in, so sharing still works."""
    client = _client(db_engine)

    assert client.get("/").status_code == HTTPStatus.OK
    # Reaches the route (404: no such recipe) rather than stopping at 401.
    assert client.get("/api/recipes/NOPE").status_code == HTTPStatus.NOT_FOUND


def test_basic_auth_still_works_beside_the_login(db_engine: Engine) -> None:
    """During the transition explicit Basic credentials are still accepted."""
    client = _client(db_engine, auth=AuthConfig(username="user", password="pass"))

    assert client.get("/api/targets").status_code == HTTPStatus.UNAUTHORIZED
    ok = client.get("/api/targets", auth=("user", "pass"))
    assert ok.status_code == HTTPStatus.OK


def test_login_settings_are_all_or_nothing() -> None:
    """No WorkOS settings means no login; a partial or weak set refuses to boot."""
    full = {
        "workos_client_id": "client_123",
        "workos_api_key": "sk_test",
        "workos_redirect_uri": "https://dispensa.example/auth/callback",
        "session_secret": _SECRET,
        "mcp_oauth_allowed_subjects": _OWNER,
    }

    assert login_from_settings(Settings(_env_file=None)) is None
    config = login_from_settings(Settings(_env_file=None, **full))
    assert config is not None
    assert config.allowed_subjects == frozenset({_OWNER})
    for dropped in ("workos_api_key", "session_secret", "mcp_oauth_allowed_subjects"):
        partial = {**full, dropped: ""}
        with pytest.raises(ConfigurationError):
            login_from_settings(Settings(_env_file=None, **partial))
    with pytest.raises(ConfigurationError):
        login_from_settings(Settings(_env_file=None, **{**full, "session_secret": "x"}))
