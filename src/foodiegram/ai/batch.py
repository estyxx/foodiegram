import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict, ValidationError

from foodiegram.domain.enums import Course, MedCategory
from foodiegram.domain.errors import ExtractionError, PromptTemplateError
from foodiegram.domain.models import ExtractedRecipe, Extraction

if TYPE_CHECKING:
    from collections.abc import Sequence

    from foodiegram.domain.models import Recipe
    from foodiegram.settings import Settings

# --- Inputs / constants ---
# Pin the exact snapshot, never the alias: extraction provenance depends on the
# model string being stable across runs.
MODEL = "gpt-5.4-mini-2026-03-17"
# gpt-5.4-mini is a reasoning model; its default effort "none" disables reasoning,
# so request "low" for the category-judgment calls.
REASONING_EFFORT = "low"
PROMPT_VERSION = "3"
CAPTION_MARKER = "{caption}"
PROMPT_PATH = Path(__file__).parent / "prompts" / "extract_recipe_details.txt"
BATCH_INPUT_PATH = Path("data/batch_input.jsonl")
BATCH_OUTPUT_PATH = Path("data/batch_output.jsonl")
LAST_BATCH_ID_PATH = Path("data/last_batch_id.txt")
BATCH_INPUT_ARCHIVE_DIR = Path("data/batch_inputs")

logger = logging.getLogger(__name__)


class BatchOutput(BaseModel):
    """The downloaded results of one completed OpenAI batch."""

    model_config = ConfigDict(frozen=True)

    batch_id: str
    content: str


def _make_strict(node: dict[str, Any]) -> None:
    """Force every object node into OpenAI strict structured-output shape.

    Strict mode requires additionalProperties=false and every property listed in
    `required`; it also rejects `default`, which Pydantic emits for fields that
    have one. Recurse through properties, array items, and $defs.
    """
    node.pop("default", None)
    properties = node.get("properties")
    if isinstance(properties, dict):
        node["required"] = list(properties)
        node["additionalProperties"] = False
        for child in properties.values():
            if isinstance(child, dict):
                _make_strict(child)
    items = node.get("items")
    if isinstance(items, dict):
        _make_strict(items)


def _extraction_schema() -> dict[str, Any]:
    """Build the strict ExtractedRecipe JSON schema with enum-constrained fields."""
    schema: dict[str, Any] = ExtractedRecipe.model_json_schema()
    schema["properties"]["course"]["enum"] = [c.value for c in Course]

    defs: dict[str, Any] = schema.get("$defs", {})
    category_serving = defs.get("ExtractedCategoryServing")
    if category_serving is not None:
        category_serving["properties"]["category"]["enum"] = [
            c.value for c in MedCategory
        ]

    _make_strict(schema)
    for definition in defs.values():
        _make_strict(definition)
    return schema


def render_prompt(*, template: str, caption: str) -> str:
    """Insert caption into template at its single caption marker, verbatim.

    Uses str.replace, never str.format/f-strings/string.Template: prompt v2 and
    captions both contain literal braces and dollars that those would choke on.
    Raise PromptTemplateError unless the marker appears exactly once.
    """
    marker_count = template.count(CAPTION_MARKER)
    if marker_count != 1:
        msg = (
            f"Prompt template must contain {CAPTION_MARKER!r} exactly once, "
            f"found {marker_count}"
        )
        raise PromptTemplateError(msg)
    return template.replace(CAPTION_MARKER, caption)


def build_extraction_body(
    *,
    caption: str,
    prompt_template: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Build the /v1/responses request body shared by the batch and smoke paths.

    Reasoning models reject `temperature`; effort is set via `reasoning` instead.
    No token cap is set — reasoning tokens count against the output budget, so we
    leave `max_output_tokens` unset to give the model full headroom.
    """
    return {
        "model": MODEL,
        "input": render_prompt(template=prompt_template, caption=caption),
        "reasoning": {"effort": REASONING_EFFORT},
        "text": {
            "format": {
                "type": "json_schema",
                "name": "ExtractedRecipe",
                "schema": schema,
                "strict": True,
            },
        },
    }


def _output_text(output: list[dict[str, Any]]) -> str:
    """Return the assistant message text from a Responses API `output` list.

    Reasoning models prepend a `type="reasoning"` item, so the message is not at
    a fixed index: scan for the message item and its first output_text content.
    """
    for item in output:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                return text
    msg = "No output_text found in Responses API output"
    raise ExtractionError(msg)


def result_to_extraction(
    *,
    line: str,
    batch_id: str | None,
    extracted_at: datetime,
) -> Extraction:
    """Parse one batch-output JSONL line into an append-only Extraction.

    Pure: no I/O, no recipe access. Uses the response's own created_at when
    present (accurate for backfilling old batches), falling back to extracted_at.
    The caller persists the row; later `promote()` merges it into the recipe.
    """
    result: dict[str, Any] = json.loads(line)
    code = str(result["custom_id"])
    response_body: dict[str, Any] = result["response"]["body"]
    model_used = str(response_body["model"])
    output_text = _output_text(response_body["output"])
    extracted = ExtractedRecipe.model_validate(json.loads(output_text))
    created_at = response_body.get("created_at")
    when = (
        datetime.fromtimestamp(created_at, tz=UTC)
        if isinstance(created_at, int | float)
        else extracted_at
    )
    return Extraction(
        id=None,
        recipe_code=code,
        prompt_version=PROMPT_VERSION,
        model=model_used,
        batch_id=batch_id,
        kind="batch",
        extracted_at=when,
        payload=extracted,
    )


def _load_batch_id(batch_id: str | None) -> str:
    """Return batch_id, falling back to data/last_batch_id.txt."""
    if batch_id:
        return batch_id
    if not LAST_BATCH_ID_PATH.exists():
        logger.error("No batch_id given and %s not found", LAST_BATCH_ID_PATH)
        sys.exit(1)
    return LAST_BATCH_ID_PATH.read_text(encoding="utf-8").strip()


def write_batch_input(recipes: Sequence[Recipe]) -> Path:
    """Write one batch request line per recipe and return the input file path."""
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    schema = _extraction_schema()

    BATCH_INPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BATCH_INPUT_PATH.open("w", encoding="utf-8") as fh:
        for recipe in recipes:
            line: dict[str, object] = {
                "custom_id": recipe.code,
                "method": "POST",
                "url": "/v1/responses",
                "body": build_extraction_body(
                    caption=recipe.caption or "",
                    prompt_template=prompt_template,
                    schema=schema,
                ),
            }
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    logger.info("Wrote %d tasks to %s", len(recipes), BATCH_INPUT_PATH)
    return BATCH_INPUT_PATH


def _archive_batch_input(input_path: Path, *, batch_id: str) -> Path:
    """Copy the submitted input file to a batch_id-keyed archive path.

    write_batch_input overwrites the same fixed path on every submission, so
    without this the input for a given batch_id is unrecoverable as soon as the
    next batch is written.
    """
    BATCH_INPUT_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archived_path = BATCH_INPUT_ARCHIVE_DIR / f"{batch_id}.jsonl"
    archived_path.write_bytes(input_path.read_bytes())
    return archived_path


def create_batch(settings: Settings, *, input_path: Path) -> str:
    """Upload the batch input file, create the batch, and return its id."""
    client = OpenAI(api_key=settings.require_openai_api_key())

    with input_path.open("rb") as fh:
        upload = client.files.create(file=fh, purpose="batch")

    logger.info("Uploaded input file: %s", upload.id)

    batch = client.batches.create(
        input_file_id=upload.id,
        endpoint="/v1/responses",
        completion_window="24h",
    )

    LAST_BATCH_ID_PATH.write_text(batch.id, encoding="utf-8")
    archived_path = _archive_batch_input(input_path, batch_id=batch.id)
    logger.info("Archived batch input to %s", archived_path)
    logger.info("Batch created: %s", batch.id)
    return batch.id


def submitted_codes() -> set[str]:
    """Return recipe codes present in any archived batch input file.

    Reads every data/batch_inputs/*.jsonl written by create_batch, regardless of
    whether that batch has completed. Lets submit_batch skip recipes already sent
    in a prior batch — applied or still in flight — so repeated `sync extract`
    calls advance through the backlog instead of resubmitting the same recipes.

    Splits on a literal newline rather than str.splitlines(): a caption can
    contain a Unicode line-separator character (e.g. U+2028) that splitlines()
    also treats as a break, which would slice a JSON line in two and corrupt it.
    """
    codes: set[str] = set()
    if not BATCH_INPUT_ARCHIVE_DIR.exists():
        return codes
    for path in BATCH_INPUT_ARCHIVE_DIR.glob("*.jsonl"):
        content = path.read_text(encoding="utf-8")
        for line_no, raw_line in enumerate(content.split("\n"), start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                msg = (
                    f"Malformed JSONL in {path} at line {line_no}: {exc}. "
                    f"Line starts with: {line[:120]!r}"
                )
                raise ExtractionError(msg) from exc
            codes.add(str(record["custom_id"]))
    return codes


def recover_batch_input(settings: Settings, batch_id: str) -> Path:
    """Download and archive a submitted batch's input file from OpenAI.

    Recovers the batch_id-keyed archive for a batch that was submitted before
    create_batch started archiving locally, or whose local archive was lost —
    OpenAI retains the uploaded input file for the life of the batch.
    """
    client = OpenAI(api_key=settings.require_openai_api_key())
    batch = client.batches.retrieve(batch_id)

    if not batch.input_file_id:
        msg = f"Batch {batch_id} has no input_file_id"
        raise ExtractionError(msg)

    content = client.files.content(batch.input_file_id).text
    BATCH_INPUT_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archived_path = BATCH_INPUT_ARCHIVE_DIR / f"{batch_id}.jsonl"
    archived_path.write_text(content, encoding="utf-8")
    logger.info("Recovered batch input to %s", archived_path)
    return archived_path


def log_batch_status(settings: Settings, batch_id: str | None) -> None:
    """Print the status and request counts of an OpenAI batch job."""
    bid = _load_batch_id(batch_id)
    client = OpenAI(api_key=settings.require_openai_api_key())
    batch = client.batches.retrieve(bid)

    counts = batch.request_counts
    if counts:
        logger.info(
            "Batch %s: status=%s  completed=%d  total=%d  failed=%d",
            bid,
            batch.status,
            counts.completed,
            counts.total,
            counts.failed,
        )
    else:
        logger.info("Batch %s: status=%s", bid, batch.status)


def fetch_batch_output(settings: Settings, batch_id: str | None) -> BatchOutput | None:
    """Download a completed batch's results, or None if it is not finished yet.

    The downloaded batch_output.jsonl is kept on disk so extraction history can
    be backfilled later.
    """
    bid = _load_batch_id(batch_id)
    client = OpenAI(api_key=settings.require_openai_api_key())
    batch = client.batches.retrieve(bid)

    if batch.status != "completed":
        logger.info("Batch %s is not completed (status=%s)", bid, batch.status)
        return None

    if not batch.output_file_id:
        logger.error("Batch %s completed but has no output_file_id", bid)
        sys.exit(1)

    content = client.files.content(batch.output_file_id).text
    BATCH_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BATCH_OUTPUT_PATH.write_text(content, encoding="utf-8")
    logger.info("Downloaded output to %s", BATCH_OUTPUT_PATH)
    return BatchOutput(batch_id=bid, content=content)


def smoke_extract(settings: Settings, *, recipes: Sequence[Recipe]) -> int:
    """Extract captions synchronously to validate model + schema wiring.

    Uses the same request-body builder as the batch path, calls the Responses API
    directly, validates each result into ExtractedRecipe, and logs a one-line
    pass/fail plus token usage per caption. Returns how many validated. Writes
    nothing.
    """
    if not recipes:
        logger.info("No eligible captions to smoke-test.")
        return 0

    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    schema = _extraction_schema()
    client = OpenAI(api_key=settings.require_openai_api_key())

    passed = 0
    for recipe in recipes:
        body = build_extraction_body(
            caption=recipe.caption or "",
            prompt_template=prompt_template,
            schema=schema,
        )
        try:
            response = client.responses.create(**body)
            ExtractedRecipe.model_validate_json(response.output_text)
        except (OpenAIError, ValidationError, ValueError):
            logger.exception("FAIL %s", recipe.code)
            continue

        passed += 1
        usage = response.usage
        if usage is None:
            logger.info(
                "PASS %s — model=%s (no usage reported)",
                recipe.code,
                response.model,
            )
        else:
            logger.info(
                "PASS %s — model=%s in=%d out=%d (reasoning=%d) total=%d",
                recipe.code,
                response.model,
                usage.input_tokens,
                usage.output_tokens,
                usage.output_tokens_details.reasoning_tokens,
                usage.total_tokens,
            )

    logger.info("Smoke: %d/%d validated", passed, len(recipes))
    return passed
