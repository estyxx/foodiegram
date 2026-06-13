"""Instagram authentication helper following instagrapi best practices."""

import logging
import os

from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, LoginRequired

from foodiegram.settings import Settings

logger = logging.getLogger(__name__)


def _resolve_challenge(client: Client) -> None:
    """Attempt automatic challenge resolution, then log instructions if it fails."""
    try:
        client.challenge_resolve(client.last_json)
        logger.info("Challenge resolved automatically.")
    except Exception as exc:
        logger.warning(
            "Auto-resolve failed (%s). "
            "Open Instagram on your phone, accept any pending prompt "
            "(Terms of Service, age verification, security check), "
            "then re-run this script.",
            exc,
        )
        raise


def login_client(settings: Settings) -> Client:
    """Return an authenticated instagrapi Client, reusing saved session if possible.

    Follows the instagrapi best-practices pattern: always load + login together
    so device UUIDs stay consistent across runs.
    """
    session_file = settings.instagram_session_file
    username = settings.instagram_username
    password = settings.instagram_password
    verification_code = os.getenv("INSTAGRAM_2FA_CODE", "")

    client = Client()
    login_via_session = False

    if session_file.exists():
        try:
            saved = client.load_settings(session_file)
            client.set_settings(saved)
            client.login(username, password, verification_code=verification_code)
            try:
                client.get_timeline_feed()
                login_via_session = True
            except ChallengeRequired:
                _resolve_challenge(client)
                login_via_session = True
            except LoginRequired:
                logger.info(
                    "Saved session expired; re-logging with preserved device UUIDs.",
                )
                old_settings = client.get_settings()
                client.set_settings({})
                client.set_uuids(old_settings["uuids"])
                client.login(username, password, verification_code=verification_code)
                login_via_session = True
        except Exception as exc:  # noqa: BLE001 — instagrapi raises many undocumented types
            logger.info("Could not log in via saved session: %s", exc)

    if not login_via_session:
        logger.info("Logging in fresh with username and password.")
        client = Client()
        try:
            client.login(username, password)
        except ChallengeRequired:
            _resolve_challenge(client)

    client.dump_settings(session_file)
    return client
