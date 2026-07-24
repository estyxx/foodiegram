import json
from collections.abc import Callable
from datetime import UTC, datetime

from foodiegram.ai.batch import PROMPT_VERSION, result_to_extraction
from foodiegram.domain.models import ExtractedRecipe

_EXTRACTED_AT = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
# A snapshot distinct from the module constant, proving the stamp comes from the
# response's `model` field rather than the MODEL constant.
_MODEL_SNAPSHOT = "gpt-5.4-mini-2026-03-17"


def _batch_line(code: str, extracted: ExtractedRecipe) -> str:
    """Build one OpenAI Batch output JSONL line for a Responses API result."""
    return json.dumps(
        {
            "custom_id": code,
            "response": {
                "body": {
                    "model": _MODEL_SNAPSHOT,
                    "output": [
                        {"type": "reasoning"},
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": extracted.model_dump_json(),
                                },
                            ],
                        },
                    ],
                },
            },
        },
    )


def test_result_to_extraction_parses_batch_line(
    make_extracted: Callable[..., ExtractedRecipe],
) -> None:
    """A batch output line becomes an append-only Extraction, provenance stamped."""
    extracted = make_extracted(title="New Title", dish_type="pasta")
    line = _batch_line("ABC", extracted)

    extraction = result_to_extraction(
        line=line,
        batch_id="batch_123",
        extracted_at=_EXTRACTED_AT,
    )

    assert extraction.recipe_code == "ABC"
    assert extraction.kind == "batch"
    assert extraction.prompt_version == PROMPT_VERSION
    assert extraction.model == _MODEL_SNAPSHOT
    assert extraction.batch_id == "batch_123"
    assert extraction.extracted_at == _EXTRACTED_AT
    assert extraction.payload == extracted
