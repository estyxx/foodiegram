import pytest

from foodiegram.ai.batch import CAPTION_MARKER, PROMPT_PATH, render_prompt
from foodiegram.domain.errors import PromptTemplateError

_LITERAL_BRACES = "objects of {category, servings, is_oily_fish}"


def test_literal_braces_survive_and_caption_inserted() -> None:
    """Literal braces stay untouched while the marker is replaced verbatim."""
    template = f'Rules: {_LITERAL_BRACES}\nCaption: "{CAPTION_MARKER}"\nEnd.'

    rendered = render_prompt(template=template, caption="pasta al forno")

    assert _LITERAL_BRACES in rendered
    assert 'Caption: "pasta al forno"' in rendered
    assert CAPTION_MARKER not in rendered


def test_caption_with_braces_and_quotes_round_trips() -> None:
    """A caption containing braces, dollars, and quotes is inserted verbatim."""
    caption = 'Try {this} for $5 — "the best" recipe: {a: 1, b: 2}'
    template = f"Caption: {CAPTION_MARKER}"

    rendered = render_prompt(template=template, caption=caption)

    assert rendered == f"Caption: {caption}"


def test_missing_marker_raises() -> None:
    """A template without the caption marker raises the typed error."""
    with pytest.raises(PromptTemplateError):
        render_prompt(template="No marker here.", caption="x")


def test_duplicated_marker_raises() -> None:
    """A template with two caption markers raises the typed error."""
    template = f"{CAPTION_MARKER} and again {CAPTION_MARKER}"

    with pytest.raises(PromptTemplateError):
        render_prompt(template=template, caption="x")


def test_real_prompt_file_renders() -> None:
    """The shipped prompt file renders — pins file and code against the bug."""
    template = PROMPT_PATH.read_text(encoding="utf-8")

    rendered = render_prompt(template=template, caption="dummy caption")

    assert "<caption>\ndummy caption\n</caption>" in rendered
    assert CAPTION_MARKER not in rendered
