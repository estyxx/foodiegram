from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

from foodiegram.domain.errors import ConfigurationError

# Substrings that mark a settings field as secret; matched fields are masked in
# repr and cover credential-bearing URLs (database_url, cloudinary_url) too.
_SECRET_KEYWORDS = ("key", "password", "secret", "sessionid", "token", "url")


class CloudinaryConfig(BaseModel):
    """Cloudinary credentials required by the image-upload scripts."""

    model_config = ConfigDict(frozen=True)

    cloud_name: str
    api_key: str
    api_secret: str


class InstagramConfig(BaseModel):
    """Instagram login credentials required by the local auth flow."""

    model_config = ConfigDict(frozen=True)

    username: str
    password: str


class Settings(BaseSettings):
    """Application configuration, loaded and validated from the environment.

    Ingestion-only secrets (OpenAI, Cloudinary, Instagram) default to empty so a
    read-only web server boots with just DATABASE_URL and BASIC_AUTH_*. The local
    pipeline reads them through the require_* accessors, which fail loudly.
    """

    # env_prefix is intentionally absent: the existing .env uses unprefixed names
    # (INSTAGRAM_USERNAME, OPENAI_API_KEY, …).  To adopt FOODIEGRAM_ prefix, rename
    # every key in .env first, then add env_prefix="FOODIEGRAM_" here.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    # --- Runtime (needed to serve the app) ---
    data_dir: Path = Path("data/recipes")
    database_url: str = "sqlite:///data/dispensa.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # SPA directory to serve, resolved against the process CWD (the repo root under
    # `fastapi run`). CWD-relative so it survives a non-editable install where the
    # package lives in site-packages; override with FRONTEND_DIR if needed.
    frontend_dir: Path = Path("frontend")

    # Commit SHA shown in the footer so the deployed build is identifiable. Falls
    # back to reading .git at runtime, then to "unknown"; set GIT_SHA in deploys
    # where .git is not shipped.
    git_sha: str = ""

    # HTTP Basic auth over the whole app (D13). Empty username disables auth (dev).
    basic_auth_username: str = ""
    basic_auth_password: str = ""

    # OAuth 2.1 for the HTTP MCP endpoint (/mcp). The composed ASGI app refuses to
    # build unless issuer, JWKS URI, and resource URL are all set, so an
    # unauthenticated MCP write surface can never ship. The local stdio server
    # reads none of these. resource_url is the endpoint's PUBLIC /mcp URL and is
    # also the token audience (RFC 8707); scopes are optional and space-separated.
    mcp_oauth_issuer: str = ""
    mcp_oauth_jwks_uri: str = ""
    mcp_oauth_resource_url: str = ""
    mcp_oauth_required_scopes: str = ""

    # Comma-separated cross-origin allowlist. Empty (default) = no CORS: the SPA is
    # served same-origin, so cross-origin access is off unless explicitly enabled.
    cors_allow_origins: str = ""

    # --- Ingestion-only secrets (local pipeline; optional so the server boots) ---
    openai_api_key: str = ""
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_url: str = ""
    instagram_username: str = ""
    instagram_password: str = ""
    instagram_collection_id: str = ""
    instagram_session_file: Path = Path("session.json")
    instagram_sessionid: str = ""

    def __repr__(self) -> str:
        """Return a repr with secret-bearing fields masked."""
        parts: list[str] = []
        for name, value in self:
            secret = any(keyword in name for keyword in _SECRET_KEYWORDS)
            parts.append(f"{name}={'****' if secret else repr(value)}")
        return f"{type(self).__name__}({', '.join(parts)})"

    def __str__(self) -> str:
        """Return the masked repr so logging never leaks secrets."""
        return repr(self)

    @staticmethod
    def _require(value: str, env_name: str) -> str:
        """Return value, raising ConfigurationError when it is empty."""
        if not value:
            msg = f"{env_name} is required for this operation but is not set"
            raise ConfigurationError(msg)
        return value

    def require_openai_api_key(self) -> str:
        """Return the OpenAI API key, raising if it is unset."""
        return self._require(self.openai_api_key, "OPENAI_API_KEY")

    def require_cloudinary(self) -> CloudinaryConfig:
        """Return Cloudinary credentials, raising if any are unset."""
        return CloudinaryConfig(
            cloud_name=self._require(
                self.cloudinary_cloud_name,
                "CLOUDINARY_CLOUD_NAME",
            ),
            api_key=self._require(self.cloudinary_api_key, "CLOUDINARY_API_KEY"),
            api_secret=self._require(
                self.cloudinary_api_secret,
                "CLOUDINARY_API_SECRET",
            ),
        )

    def require_instagram(self) -> InstagramConfig:
        """Return Instagram login credentials, raising if any are unset."""
        return InstagramConfig(
            username=self._require(self.instagram_username, "INSTAGRAM_USERNAME"),
            password=self._require(self.instagram_password, "INSTAGRAM_PASSWORD"),
        )

    def cors_origins(self) -> list[str]:
        """Return the configured cross-origin allowlist (empty when unset)."""
        return [
            origin.strip()
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]
