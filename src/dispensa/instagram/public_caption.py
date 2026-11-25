import logging
import re
from enum import StrEnum

import instaloader
import yt_dlp
from instaloader.exceptions import InstaloaderException, LoginRequiredException
from pydantic import BaseModel, ConfigDict
from yt_dlp.utils import YoutubeDLError

# Reads a public post's caption without logging in, the way IGbulkDL does
# (github.com/doncezart/IGbulkDL, MIT): ask yt-dlp for the post's metadata and
# take its description. yt-dlp refuses a photo-only post ("no video") after it
# has already read the caption, so ignore_no_formats_error lets every post type
# through; instaloader is the fallback when yt-dlp is turned away. No cookies,
# no account: a refusal can never flag anyone.
#
# Everything here is one quick, best-effort attempt. Nothing waits out a rate
# limit: a person is waiting on the other end, and the pasted caption is always
# the fallback.

logger = logging.getLogger(__name__)

POST_URL = "https://www.instagram.com/p/{code}/"
_TIMEOUT_SECONDS = 8
_DETAIL_CHARS = 200

_RATE_LIMITED = re.compile(r"rate[- ]limit|too many requests|\b429\b")
_LOGIN_WALL = re.compile(
    r"login|log in|registered users|empty media response|restricted|private",
)
_NOT_FOUND = re.compile(r"does not exist|not found|\b404\b|removed|deleted")


class CaptionOutcome(StrEnum):
    """How one attempt to read a public caption ended."""

    FOUND = "found"
    NO_CAPTION = "no_caption"
    LOGIN_WALL = "login_wall"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    FAILED = "failed"
    UNKNOWN = "unknown"


# A clear answer about the post: trying the other library would not change it.
_SETTLED = frozenset(
    {CaptionOutcome.FOUND, CaptionOutcome.NO_CAPTION, CaptionOutcome.NOT_FOUND},
)


class CaptionFetch(BaseModel):
    """The result of trying to read a post's caption from Instagram."""

    model_config = ConfigDict(frozen=True)

    outcome: CaptionOutcome
    caption: str | None = None
    # Which library answered: "yt-dlp", "instaloader", or "" when neither did.
    source: str = ""
    # A short reason for a failure, for the logs; never shown as data.
    detail: str = ""


class _ThrottledError(Exception):
    """Raised by the rate controller instead of sleeping."""


class _NoWaitRateController(instaloader.RateController):
    """Refuse to wait out a rate limit: give up at once instead."""

    def sleep(self, secs: float) -> None:
        """Raise instead of sleeping for secs."""
        msg = f"Instagram asked to wait {secs:.0f}s"
        raise _ThrottledError(msg)


class _QuietLogger:
    """Send yt-dlp's chatter to debug, so it never floods the server log."""

    def debug(self, msg: str) -> None:
        """Drop progress lines."""
        logger.debug("yt-dlp: %s", msg)

    def info(self, msg: str) -> None:
        """Drop informational lines."""
        logger.debug("yt-dlp: %s", msg)

    def warning(self, msg: str) -> None:
        """Keep warnings at debug: 'no video' is expected for photo posts."""
        logger.debug("yt-dlp warning: %s", msg)

    def error(self, msg: str) -> None:
        """Errors are reported by the caller through CaptionFetch."""
        logger.debug("yt-dlp error: %s", msg)


def classify_refusal(message: str) -> CaptionOutcome:
    """Map a yt-dlp or instaloader error message to an outcome."""
    text = message.lower()
    if _RATE_LIMITED.search(text):
        return CaptionOutcome.RATE_LIMITED
    if _NOT_FOUND.search(text):
        return CaptionOutcome.NOT_FOUND
    if _LOGIN_WALL.search(text):
        return CaptionOutcome.LOGIN_WALL
    return CaptionOutcome.FAILED


def _from_text(caption: object, *, source: str) -> CaptionFetch:
    """Turn whatever the library returned into FOUND or NO_CAPTION."""
    if isinstance(caption, str) and caption.strip():
        return CaptionFetch(
            outcome=CaptionOutcome.FOUND,
            caption=caption.strip(),
            source=source,
        )
    return CaptionFetch(outcome=CaptionOutcome.NO_CAPTION, source=source)


def _failure(outcome: CaptionOutcome, *, source: str, error: Exception) -> CaptionFetch:
    """Build a failed CaptionFetch with a short reason."""
    detail = " ".join(str(error).split())[:_DETAIL_CHARS]
    return CaptionFetch(outcome=outcome, source=source, detail=detail)


def _via_yt_dlp(code: str) -> CaptionFetch:
    """Read the caption through yt-dlp's logged-out Instagram extractor."""
    options = {
        "quiet": True,
        "no_warnings": True,
        "logger": _QuietLogger(),
        "skip_download": True,
        "noplaylist": False,
        # A photo post has no video; its caption is read before that refusal.
        "ignore_no_formats_error": True,
        "socket_timeout": _TIMEOUT_SECONDS,
        "extractor_retries": 0,
        "cookiefile": None,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            # process=False: metadata only, no format selection.
            info: object = ydl.extract_info(
                POST_URL.format(code=code),
                download=False,
                process=False,
            )
    except YoutubeDLError as exc:
        return _failure(classify_refusal(str(exc)), source="yt-dlp", error=exc)
    if not isinstance(info, dict):
        return CaptionFetch(
            outcome=CaptionOutcome.FAILED,
            source="yt-dlp",
            detail="no metadata",
        )
    return _from_text(info.get("description"), source="yt-dlp")


def _via_instaloader(code: str) -> CaptionFetch:
    """Read the caption through instaloader, anonymously."""
    loader = instaloader.Instaloader(
        quiet=True,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        max_connection_attempts=1,
        request_timeout=_TIMEOUT_SECONDS,
        rate_controller=_NoWaitRateController,
        iphone_support=False,
    )
    try:
        post = instaloader.Post.from_shortcode(loader.context, code)
        caption = post.caption
    except _ThrottledError as exc:
        return _failure(CaptionOutcome.RATE_LIMITED, source="instaloader", error=exc)
    except LoginRequiredException as exc:
        return _failure(CaptionOutcome.LOGIN_WALL, source="instaloader", error=exc)
    except InstaloaderException as exc:
        return _failure(classify_refusal(str(exc)), source="instaloader", error=exc)
    return _from_text(caption, source="instaloader")


def fetch_public_caption(code: str) -> CaptionFetch:
    """Read a public post's caption, without logging in.

    Tries yt-dlp, then instaloader when yt-dlp was turned away. Never raises for
    an Instagram refusal: the outcome says what happened.
    """
    first = _via_yt_dlp(code)
    if first.outcome in _SETTLED:
        return first
    second = _via_instaloader(code)
    if second.outcome in _SETTLED:
        return second
    # Both refused: report the first refusal, with both reasons for the log.
    return first.model_copy(
        update={"detail": f"{first.detail} | instaloader: {second.detail}"},
    )
