import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from foodiegram.domain.enums import Course, MedCategory
from foodiegram.domain.errors import ExtractionError, PromptTemplateError
from foodiegram.domain.models import ExtractedRecipe, Extraction

if TYPE_CHECKING:
    from foodiegram.domain.models import Recipe
    from foodiegram.settings import Settings
    from foodiegram.storage.extractions_db import ExtractionRepository
    from foodiegram.storage.recipes_db import RecipeRepository

# --- Inputs / constants ---
# Pin the exact snapshot, never the alias: extraction provenance depends on the
# model string being stable across runs.
MODEL = "gpt-5.4-mini-2026-03-17"
# gpt-5.4-mini is a reasoning model; its default effort "none" disables reasoning,
# so request "low" for the category-judgment calls.
REASONING_EFFORT = "low"
PROMPT_VERSION = "2"
CAPTION_MARKER = "{caption}"
PROMPT_PATH = Path(__file__).parent / "prompts" / "extract_recipe_details.txt"
BATCH_INPUT_PATH = Path("data/batch_input.jsonl")
BATCH_OUTPUT_PATH = Path("data/batch_output.jsonl")
LAST_BATCH_ID_PATH = Path("data/last_batch_id.txt")
MIN_CAPTION_LENGTH = 80

logger = logging.getLogger(__name__)


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


def _has_usable_caption(recipe: Recipe) -> bool:
    """Return True if the caption is long enough to be worth extracting."""
    return (
        recipe.caption is not None and len(recipe.caption.strip()) >= MIN_CAPTION_LENGTH
    )


def _eligible_for_submit(
    recipe: Recipe,
    *,
    extracted_codes: set[str],
    only_missing: bool,
) -> bool:
    """Return True if recipe should be submitted for extraction.

    only_missing skips recipes that already have an extraction at the current
    PROMPT_VERSION; only_missing=False (--all) re-submits every captioned,
    non-edited recipe — use after a prompt or model change.
    """
    if recipe.edited_by_user:
        return False
    if not _has_usable_caption(recipe):
        return False
    return not (only_missing and recipe.code in extracted_codes)


def cmd_submit(
    settings: Settings,
    *,
    recipes: RecipeRepository,
    extractions: ExtractionRepository,
    only_missing: bool = True,
    limit: int | None = None,
) -> None:
    """Load recipes, build batch_input.jsonl, upload to OpenAI, and create a batch.

    With limit set, submit only the first `limit` eligible recipes — useful for a
    small, cheap test run before submitting the whole backlog.
    """
    all_recipes = recipes.list_all()
    extracted_codes = {e.recipe_code for e in extractions.for_version(PROMPT_VERSION)}

    to_submit = [
        r
        for r in all_recipes
        if _eligible_for_submit(
            r,
            extracted_codes=extracted_codes,
            only_missing=only_missing,
        )
    ]
    no_caption = [r for r in all_recipes if not _has_usable_caption(r)]

    eligible = len(to_submit)
    if limit is not None:
        to_submit = to_submit[:limit]

    mode = "only-missing" if only_missing else "all"
    logger.info("Total recipes: %d", len(all_recipes))
    logger.info("Already extracted at v%s: %d", PROMPT_VERSION, len(extracted_codes))
    logger.info("No caption: %d", len(no_caption))
    if limit is not None:
        logger.info(
            "Will submit: %d of %d eligible (limit=%d, mode=%s)",
            len(to_submit),
            eligible,
            limit,
            mode,
        )
    else:
        logger.info("Will submit: %d (mode=%s)", len(to_submit), mode)

    if not to_submit:
        logger.info("Nothing to submit.")
        return

    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    schema = _extraction_schema()

    BATCH_INPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BATCH_INPUT_PATH.open("w", encoding="utf-8") as fh:
        for recipe in to_submit:
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

    logger.info("Wrote %d tasks to %s", len(to_submit), BATCH_INPUT_PATH)

    client = OpenAI(api_key=settings.openai_api_key)

    with BATCH_INPUT_PATH.open("rb") as fh:
        upload = client.files.create(file=fh, purpose="batch")

    logger.info("Uploaded input file: %s", upload.id)

    batch = client.batches.create(
        input_file_id=upload.id,
        endpoint="/v1/responses",
        completion_window="24h",
    )

    LAST_BATCH_ID_PATH.write_text(batch.id, encoding="utf-8")
    logger.info("Batch created: %s", batch.id)


def cmd_status(settings: Settings, batch_id: str | None) -> None:
    """Print the status and request counts of an OpenAI batch job."""
    bid = _load_batch_id(batch_id)
    client = OpenAI(api_key=settings.openai_api_key)
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


def cmd_apply(
    settings: Settings,
    batch_id: str | None,
    *,
    extractions: ExtractionRepository,
) -> None:
    """Download a completed batch and append its results as extraction rows.

    Writes extraction history only — never touches recipes. Run promote.py to
    merge these extractions into recipes (honouring user edits). The downloaded
    batch_output.jsonl is kept so history can be backfilled later.
    """
    bid = _load_batch_id(batch_id)
    client = OpenAI(api_key=settings.openai_api_key)
    batch = client.batches.retrieve(bid)

    if batch.status != "completed":
        logger.info("Batch %s is not completed (status=%s)", bid, batch.status)
        return

    if not batch.output_file_id:
        logger.error("Batch %s completed but has no output_file_id", bid)
        sys.exit(1)

    content = client.files.content(batch.output_file_id).text
    BATCH_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BATCH_OUTPUT_PATH.write_text(content, encoding="utf-8")
    logger.info("Downloaded output to %s", BATCH_OUTPUT_PATH)

    added = 0
    errors = 0
    now = datetime.now(tz=UTC)

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            extraction = result_to_extraction(line=line, batch_id=bid, extracted_at=now)
            extractions.add(extraction)
            added += 1
        except (
            KeyError,
            IndexError,
            TypeError,
            json.JSONDecodeError,
            ValidationError,
            ExtractionError,
        ):
            logger.exception("Failed to parse batch result line")
            errors += 1

    logger.info("Extractions added: %d  Errors: %d", added, errors)


def cmd_smoke(
    settings: Settings,
    *,
    recipes: RecipeRepository,
    extractions: ExtractionRepository,
    limit: int,
) -> None:
    """Extract a few captions synchronously to validate model + schema wiring.

    Uses the same request-body builder as the batch path, calls the Responses API
    directly, validates each result into ExtractedRecipe, and logs a one-line
    pass/fail plus token usage per caption. Does not write anything to the repo.
    """
    all_recipes = recipes.list_all()
    extracted_codes = {e.recipe_code for e in extractions.for_version(PROMPT_VERSION)}
    eligible = [
        r
        for r in all_recipes
        if _eligible_for_submit(r, extracted_codes=extracted_codes, only_missing=True)
    ][:limit]
    if not eligible:
        logger.info("No eligible captions to smoke-test.")
        return

    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    schema = _extraction_schema()
    client = OpenAI(api_key=settings.openai_api_key)

    passed = 0
    for recipe in eligible:
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

    logger.info("Smoke: %d/%d validated", passed, len(eligible))
