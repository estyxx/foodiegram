import pytest

from dispensa.instagram import CaptionOutcome, classify_refusal

# Real messages, copied from yt-dlp's Instagram extractor and instaloader.
_CASES = [
    (
        "ERROR: [Instagram] DJq4i8ysCL8: The webpage request was redirected to the "
        "login page. You have exceeded the rate-limit for accessing posts anonymously",
        CaptionOutcome.RATE_LIMITED,
    ),
    (
        "ERROR: [Instagram] DJq4i8ysCL8: Instagram sent an empty media response. "
        "Check if this post is accessible in your browser without being logged-in.",
        CaptionOutcome.LOGIN_WALL,
    ),
    (
        "This content is only available for registered users who follow this account",
        CaptionOutcome.LOGIN_WALL,
    ),
    (
        "429 Too Many Requests when accessing https://www.instagram.com/graphql/query",
        CaptionOutcome.RATE_LIMITED,
    ),
    ("Instagram asked to wait 600s", CaptionOutcome.FAILED),
    ("HTTP Error 404: Not Found", CaptionOutcome.NOT_FOUND),
    ("Fetching Post metadata failed.", CaptionOutcome.FAILED),
    (
        "Unable to download webpage: <urlopen error [Errno 110] timed out>",
        CaptionOutcome.FAILED,
    ),
]


@pytest.mark.parametrize(("message", "expected"), _CASES)
def test_classify_refusal(message: str, expected: CaptionOutcome) -> None:
    """Each library refusal maps to the outcome the queue logs and shows."""
    assert classify_refusal(message) is expected
