from typing import Self

from dotenv import dotenv_values
from pydantic import BaseModel


class Env(BaseModel):
    """Environment variables for the application."""

    INSTAGRAM_USERNAME: str
    INSTAGRAM_PASSWORD: str
    INSTAGRAM_COLLECTION_ID: int
    OPENAI_API_KEY: str

    def __repr__(self) -> str:
        """Return a custom representation to avoid printing sensitive information.

        Sensitive fields are replaced with '****'.
        """
        sensitive_keywords = ["KEY", "PASSWORD", "SECRET", "TOKEN"]
        return (
            type(self).__name__
            + "("
            + ", ".join(
                (
                    f"{name}='****'"
                    if any(kw in name for kw in sensitive_keywords)
                    else f"{name}='{value}'"
                )
                for name, value in self.model_dump().items()
            )
            + ")"
        )

    @classmethod
    def get_env(cls) -> Self:
        """Load environment variables from a .env file and return an instance of Env."""
        return cls(**dotenv_values(".env"))
