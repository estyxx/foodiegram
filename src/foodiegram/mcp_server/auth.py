import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import anyio.to_thread
import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier

from foodiegram.domain.errors import ConfigurationError

if TYPE_CHECKING:
    from foodiegram.settings import Settings

logger = logging.getLogger(__name__)

# Only asymmetric signatures are accepted: the IdP signs, we verify with its public
# JWKS. Symmetric HS* would require sharing a secret with the IdP and is refused.
_ALGORITHMS = ["RS256"]


@dataclass(frozen=True)
class OAuthConfig:
    """Resolved, validated OAuth inputs for the HTTP MCP endpoint."""

    issuer: str
    jwks_uri: str
    resource_url: str
    required_scopes: list[str]


def oauth_config(settings: Settings) -> OAuthConfig:
    """Read the OAuth env; raise ConfigurationError if a required field is unset.

    resource_url doubles as the token audience (RFC 8707), so a token minted for
    another resource cannot be replayed here.
    """
    missing = [
        name
        for name, value in (
            ("MCP_OAUTH_ISSUER", settings.mcp_oauth_issuer),
            ("MCP_OAUTH_JWKS_URI", settings.mcp_oauth_jwks_uri),
            ("MCP_OAUTH_RESOURCE_URL", settings.mcp_oauth_resource_url),
        )
        if not value
    ]
    if missing:
        joined = ", ".join(missing)
        msg = f"{joined} required to serve the MCP endpoint over HTTP"
        raise ConfigurationError(msg)
    return OAuthConfig(
        issuer=settings.mcp_oauth_issuer,
        jwks_uri=settings.mcp_oauth_jwks_uri,
        resource_url=settings.mcp_oauth_resource_url,
        required_scopes=settings.mcp_oauth_required_scopes.split(),
    )


def _claim_scopes(claims: dict[str, Any]) -> list[str]:
    """Extract granted scopes across the common IdP claim spellings."""
    scope = claims.get("scope")
    if isinstance(scope, str):
        return scope.split()
    for key in ("scp", "permissions"):
        value = claims.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
    return []


class JwtTokenVerifier(TokenVerifier):
    """Verify a JWT bearer token against an IdP's JWKS, issuer, and audience.

    Header-only: it inspects the token the transport already parsed and never
    touches the request body. JWKS fetches run off the event loop; keys are
    cached by PyJWKClient after the first lookup.
    """

    def __init__(self, *, jwks_uri: str, issuer: str, audience: str) -> None:
        """Build a verifier bound to one issuer and one audience (the /mcp URL)."""
        self._issuer = issuer
        self._audience = audience
        self._jwks_client = PyJWKClient(jwks_uri)

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return the decoded token if the signature, issuer, and audience hold."""
        try:
            signing_key = await anyio.to_thread.run_sync(
                self._jwks_client.get_signing_key_from_jwt, token
            )
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.PyJWTError as exc:
            logger.info("Rejected MCP token: %s", exc)
            return None
        subject = claims.get("sub")
        return AccessToken(
            token=token,
            client_id=str(claims.get("client_id") or claims.get("azp") or subject or ""),
            scopes=_claim_scopes(claims),
            expires_at=claims.get("exp"),
            resource=self._audience,
            subject=subject,
            claims=claims,
        )
