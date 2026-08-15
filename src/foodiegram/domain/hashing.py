import hashlib
import unicodedata


def normalize_caption(caption: str) -> str:
    """Return caption with surrounding whitespace stripped and NFC-normalized.

    Minimal on purpose: the same visible text must always normalize to the same
    string so its hash is stable across re-ingests that differ only in trailing
    whitespace or Unicode composition form.
    """
    return unicodedata.normalize("NFC", caption.strip())


def caption_hash(caption: str | None) -> str | None:
    """Return the sha256 hex of the normalized caption, or None when empty."""
    if caption is None:
        return None
    normalized = normalize_caption(caption)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def document_hash(document: str) -> str:
    """Return the sha256 hex of the exact embedded-document string.

    Applied to recipe_document() output, so a re-extraction that changes the
    summary or tags (even with an unchanged caption) changes this hash.
    """
    return hashlib.sha256(document.encode("utf-8")).hexdigest()
