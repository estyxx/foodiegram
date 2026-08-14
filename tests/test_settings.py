import pytest

from foodiegram.domain.errors import ConfigurationError
from foodiegram.settings import Settings

_PAYLOAD = {
    "instagram_username": "alice_distinct",
    "instagram_password": "hunter2secret_pw",
    "instagram_collection_id": "17854976980356429",
    "instagram_session_file": "session.json",
    "openai_api_key": "sk-distinctkey",
    "cloudinary_cloud_name": "mycloud",
    "cloudinary_api_key": "ck-distinct",
    "cloudinary_api_secret": "cs-distinct",
}


def _build() -> Settings:
    """Build a Settings instance from a dict, bypassing the real .env."""
    return Settings.model_validate(_PAYLOAD)


def test_repr_masks_secret_fields() -> None:
    """Secret-bearing fields are masked in repr; plain fields are shown."""
    rendered = repr(_build())
    assert "hunter2secret_pw" not in rendered
    assert "sk-distinctkey" not in rendered
    assert "ck-distinct" not in rendered
    assert "cs-distinct" not in rendered
    assert "****" in rendered
    assert "alice_distinct" in rendered


def test_str_also_masks_secrets() -> None:
    """str() must not leak secrets, since logging relies on it."""
    assert "hunter2secret_pw" not in str(_build())


def test_values_remain_accessible() -> None:
    """Masking is display-only; the real values stay usable."""
    settings = _build()
    assert settings.instagram_password == "hunter2secret_pw"
    assert settings.openai_api_key == "sk-distinctkey"
    assert settings.instagram_collection_id == "17854976980356429"


def test_repr_masks_credential_bearing_urls() -> None:
    """database_url and cloudinary_url carry credentials, so they are masked."""
    settings = Settings.model_construct(database_url="postgres://user:pw@host/db")
    rendered = repr(settings)
    assert "pw@host" not in rendered
    assert "database_url=****" in rendered


def test_boots_with_no_pipeline_secrets() -> None:
    """A read-only server boots with defaults; ingestion secrets are empty."""
    settings = Settings.model_construct()
    assert settings.openai_api_key == ""
    assert settings.cloudinary_cloud_name == ""
    assert settings.instagram_username == ""
    assert settings.database_url == (
        "postgresql+psycopg2://dispensa:dispensa@localhost:5432/dispensa"
    )


def test_require_openai_api_key_raises_when_unset() -> None:
    """require_openai_api_key fails loudly when the key is empty."""
    with pytest.raises(ConfigurationError):
        Settings.model_construct().require_openai_api_key()


def test_require_openai_api_key_returns_value() -> None:
    """require_openai_api_key returns the key when set."""
    settings = Settings.model_construct(openai_api_key="sk-live")
    assert settings.require_openai_api_key() == "sk-live"


def test_require_cloudinary_raises_when_partial() -> None:
    """require_cloudinary fails when any Cloudinary field is missing."""
    settings = Settings.model_construct(cloudinary_cloud_name="only-name")
    with pytest.raises(ConfigurationError):
        settings.require_cloudinary()


def test_require_cloudinary_returns_config() -> None:
    """require_cloudinary returns all three credentials when present."""
    settings = Settings.model_construct(
        cloudinary_cloud_name="cn",
        cloudinary_api_key="ak",
        cloudinary_api_secret="as",
    )
    config = settings.require_cloudinary()
    assert config.cloud_name == "cn"
    assert config.api_key == "ak"
    assert config.api_secret == "as"


def test_require_instagram_raises_when_unset() -> None:
    """require_instagram fails loudly when credentials are missing."""
    with pytest.raises(ConfigurationError):
        Settings.model_construct().require_instagram()


def test_cors_origins_parses_comma_list() -> None:
    """cors_origins splits, trims, and drops empties; default is no origins."""
    settings = Settings.model_construct(
        cors_allow_origins=" https://a.com , https://b.com ,",
    )
    assert settings.cors_origins() == ["https://a.com", "https://b.com"]
    assert Settings.model_construct().cors_origins() == []
