"""Create or refresh the saved Instagram session used by the extractor.

Run once before using instagram.py or extract.py.
Set INSTAGRAM_2FA_CODE in the environment if the account uses 2FA.
"""

import logging

from foodiegram._auth import login_client
from foodiegram.settings import Settings


def main() -> None:
    """Validate or create the Instagram session file."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings()
    login_client(settings)
    logging.getLogger(__name__).info(
        "Session saved to %s",
        settings.instagram_session_file,
    )


if __name__ == "__main__":
    main()
