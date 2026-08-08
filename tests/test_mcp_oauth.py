import time
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace

import anyio
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier
from starlette.testclient import TestClient

from foodiegram.asgi import build_asgi_app
from foodiegram.domain.errors import ConfigurationError
from foodiegram.mcp_server.auth import JwtTokenVerifier
from foodiegram.settings import Settings

_ISSUER = "https://idp.example.com"
_RESOURCE = "https://testserver/mcp"
_WELL_KNOWN = "/.well-known/oauth-protected-resource/mcp"
_ONE_HOUR = 3600


# --- JwtTokenVerifier: audience binding, hermetic (local keypair, no network) ---


@pytest.fixture(scope="module")
def rsa_keys() -> tuple[bytes, rsa.RSAPublicKey]:
    """Return a fresh (private-PEM, public-key) RSA pair for signing test tokens."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return pem, key.public_key()


def _mint(private_pem: bytes, *, audience: str, issuer: str = _ISSUER) -> str:
    """Sign an RS256 JWT with the given audience and issuer."""
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": "tester",
        "scope": "mcp.read",
        "exp": int(time.time()) + _ONE_HOUR,
    }
    return jwt.encode(claims, private_pem, algorithm="RS256")


def _patch_jwks(monkeypatch: pytest.MonkeyPatch, public_key: rsa.RSAPublicKey) -> None:
    """Make PyJWKClient return our local public key instead of fetching JWKS."""

    def _resolve(_self: object, _token: str) -> SimpleNamespace:
        return SimpleNamespace(key=public_key)

    monkeypatch.setattr(PyJWKClient, "get_signing_key_from_jwt", _resolve)


def _verifier() -> JwtTokenVerifier:
    """Build a verifier bound to the test issuer and audience."""
    return JwtTokenVerifier(
        jwks_uri="https://idp.example.com/jwks",
        issuer=_ISSUER,
        audience=_RESOURCE,
    )


def test_valid_token_is_accepted(
    rsa_keys: tuple[bytes, rsa.RSAPublicKey], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A correctly-audienced, correctly-issued token decodes to an AccessToken."""
    private_pem, public_key = rsa_keys
    _patch_jwks(monkeypatch, public_key)
    result = anyio.run(_verifier().verify_token, _mint(private_pem, audience=_RESOURCE))
    assert result is not None
    assert result.subject == "tester"
    assert result.scopes == ["mcp.read"]
    assert result.resource == _RESOURCE


def test_wrong_audience_is_rejected(
    rsa_keys: tuple[bytes, rsa.RSAPublicKey], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A token minted for another resource (audience) is refused."""
    private_pem, public_key = rsa_keys
    _patch_jwks(monkeypatch, public_key)
    token = _mint(private_pem, audience="https://evil.example.com/mcp")
    assert anyio.run(_verifier().verify_token, token) is None


def test_wrong_issuer_is_rejected(
    rsa_keys: tuple[bytes, rsa.RSAPublicKey], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A token from an unexpected issuer is refused."""
    private_pem, public_key = rsa_keys
    _patch_jwks(monkeypatch, public_key)
    token = _mint(private_pem, audience=_RESOURCE, issuer="https://other.example.com")
    assert anyio.run(_verifier().verify_token, token) is None


# --- Composed app: challenge, metadata, pass-through, fail-fast ---


class _FakeVerifier(TokenVerifier):
    """A verifier that accepts exactly one opaque token, for wiring tests."""

    def __init__(self, *, good: str) -> None:
        """Accept only the token equal to good; reject everything else."""
        self._good = good

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return an AccessToken for the known token, else None."""
        if token == self._good:
            return AccessToken(
                token=token,
                client_id="test",
                scopes=[],
                resource=_RESOURCE,
                subject="tester",
                claims={},
            )
        return None


def _settings(tmp_path: Path, *, oauth: bool = True) -> Settings:
    """Build Settings pointing at a tmp DB, with or without the OAuth env."""
    return Settings(
        mcp_oauth_issuer=_ISSUER if oauth else "",
        mcp_oauth_jwks_uri="https://idp.example.com/jwks" if oauth else "",
        mcp_oauth_resource_url=_RESOURCE if oauth else "",
        mcp_oauth_required_scopes="",
        database_url=f"sqlite:///{tmp_path / 'dispensa.db'}",
    )


def _app(tmp_path: Path) -> TestClient:
    """Build the composed app with a fake verifier accepting 'good-token'."""
    app = build_asgi_app(
        settings=_settings(tmp_path),
        token_verifier=_FakeVerifier(good="good-token"),
    )
    return TestClient(app)


def test_build_asgi_app_requires_oauth_env(tmp_path: Path) -> None:
    """Assembling the composed app fails fast when the OAuth env is unset."""
    with pytest.raises(ConfigurationError, match="MCP_OAUTH"):
        build_asgi_app(settings=_settings(tmp_path, oauth=False))


def test_unauthenticated_request_gets_resource_metadata_challenge(
    tmp_path: Path,
) -> None:
    """No token yields 401 with a WWW-Authenticate resource_metadata pointer."""
    with _app(tmp_path) as client:
        response = client.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        challenge = response.headers["www-authenticate"]
        assert "resource_metadata=" in challenge
        assert _WELL_KNOWN in challenge


def test_protected_resource_metadata_is_published(tmp_path: Path) -> None:
    """The PRM document is served at the origin root and names the IdP."""
    with _app(tmp_path) as client:
        response = client.get(_WELL_KNOWN)
        assert response.status_code == HTTPStatus.OK
        doc = response.json()
        assert doc["resource"].rstrip("/") == _RESOURCE
        servers = [server.rstrip("/") for server in doc["authorization_servers"]]
        assert _ISSUER in servers


def test_valid_token_reaches_the_mcp_transport(tmp_path: Path) -> None:
    """A valid token passes the auth gate and the MCP server handles the request."""
    with _app(tmp_path) as client:
        response = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer good-token",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
        )
        assert response.status_code == HTTPStatus.OK


def test_api_surface_needs_no_bearer(tmp_path: Path) -> None:
    """The API/SPA surface stays reachable without an MCP bearer token."""
    with _app(tmp_path) as client:
        assert client.get("/").status_code == HTTPStatus.OK
