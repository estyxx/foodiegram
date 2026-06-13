from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SECRET_KEYWORDS = ("key", "password", "secret", "token")


class Settings(BaseSettings):
    """Application configuration, loaded and validated from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    instagram_username: str
    instagram_password: str
    instagram_collection_id: str
    instagram_session_file: Path
    openai_api_key: str
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str

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
