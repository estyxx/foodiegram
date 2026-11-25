from http import HTTPStatus

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from dispensa.api import create_app
from dispensa.api_headers import CONTENT_SECURITY_POLICY
from dispensa.deps import AuthConfig, Deps
from dispensa.storage.batches_db import BatchRepository
from dispensa.storage.exercise_log_db import ExerciseLogRepository
from dispensa.storage.extractions_db import ExtractionRepository
from dispensa.storage.pantry_db import PantryRepository
from dispensa.storage.pending_db import PendingLinkRepository
from dispensa.storage.plans_db import PlanRepository
from dispensa.storage.recipes_db import RecipeRepository
from dispensa.storage.targets_db import TargetRepository
from dispensa.storage.user_state_db import UserStateRepository


def _client(
    engine: Engine,
    *,
    base_url: str = "http://testserver",
    auth: AuthConfig | None = None,
) -> TestClient:
    """Build a client over the full app, auth off unless given."""
    deps = Deps(
        recipes=RecipeRepository(engine),
        extractions=ExtractionRepository(engine),
        user_state=UserStateRepository(engine),
        plans=PlanRepository(engine),
        pantry=PantryRepository(engine),
        targets=TargetRepository(engine),
        exercise_log=ExerciseLogRepository(engine),
        pending=PendingLinkRepository(engine),
        batches=BatchRepository(engine),
    )
    return TestClient(create_app(deps=deps, auth=auth), base_url=base_url)


def test_pages_and_api_carry_the_security_headers(db_engine: Engine) -> None:
    """The SPA shell, a static file and an API response all get the headers."""
    client = _client(db_engine)

    for path in ("/", "/css/shell.css", "/api/targets"):
        headers = client.get(path).headers
        assert headers["Content-Security-Policy"] == CONTENT_SECURITY_POLICY, path
        assert headers["X-Content-Type-Options"] == "nosniff", path
        assert headers["X-Frame-Options"] == "DENY", path
        assert headers["Referrer-Policy"] == "same-origin", path
        assert "camera=()" in headers["Permissions-Policy"], path


def test_policy_forbids_inline_code_and_framing() -> None:
    """No 'unsafe-inline' anywhere, and the app cannot be framed."""
    assert "unsafe" not in CONTENT_SECURITY_POLICY
    assert "frame-ancestors 'none'" in CONTENT_SECURITY_POLICY
    assert "script-src 'self'" in CONTENT_SECURITY_POLICY


def test_hsts_only_over_https(db_engine: Engine) -> None:
    """HSTS is sent over TLS, or behind a proxy that says so, never on plain http."""
    plain = _client(db_engine).get("/")
    tls = _client(db_engine, base_url="https://testserver").get("/")
    proxied = _client(db_engine).get("/", headers={"X-Forwarded-Proto": "https"})

    assert "Strict-Transport-Security" not in plain.headers
    assert tls.headers["Strict-Transport-Security"] == "max-age=31536000"
    assert proxied.headers["Strict-Transport-Security"] == "max-age=31536000"


def test_a_refused_request_still_gets_the_headers(db_engine: Engine) -> None:
    """The 401 from the auth layer is covered too."""
    client = _client(db_engine, auth=AuthConfig(username="user", password="pass"))

    response = client.get("/api/targets")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.headers["X-Frame-Options"] == "DENY"


def test_api_docs_are_closed(db_engine: Engine) -> None:
    """The generated docs and schema are not served."""
    client = _client(db_engine)

    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == HTTPStatus.NOT_FOUND, path
