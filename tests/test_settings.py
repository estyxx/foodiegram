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
