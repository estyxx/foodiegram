import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from openai import OpenAI
from pydantic import ValidationError

from foodiegram.domain.models import ExtractedRecipe, Recipe
from foodiegram.repository import RecipeRepository
from foodiegram.settings import Settings

# --- Inputs / constants ---
MODEL = "gpt-4.1-mini"
PROMPT_PATH = Path("src/foodiegram/prompts/extract_recipe_details.txt")
BATCH_INPUT_PATH = Path("data/batch_input.jsonl")
BATCH_OUTPUT_PATH = Path("data/batch_output.jsonl")
LAST_BATCH_ID_PATH = Path("data/last_batch_id.txt")
MIN_CAPTION_LENGTH = 80

logger = logging.getLogger(__name__)


def _load_batch_id(batch_id: str | None) -> str:
    """Return batch_id, falling back to data/last_batch_id.txt."""
    if batch_id:
        return batch_id
    if not LAST_BATCH_ID_PATH.exists():
        logger.error("No batch_id given and %s not found", LAST_BATCH_ID_PATH)
        sys.exit(1)
    return LAST_BATCH_ID_PATH.read_text(encoding="utf-8").strip()


def _needs_extraction(recipe: Recipe, *, force: bool = False) -> bool:
    """Return True if recipe is eligible for batch extraction.

    With force=True, re-submit all non-edited recipes with a long enough
    caption, including those already extracted — use after a prompt change.
    """
    if recipe.edited_by_user:
        return False
    if recipe.caption is None or len(recipe.caption.strip()) < MIN_CAPTION_LENGTH:
        return False
    if force:
        return True
    return not recipe.instructions


def cmd_submit(settings: Settings, *, force: bool = False) -> None:
    """Load recipes, build batch_input.jsonl, upload to OpenAI, and create a batch."""
    repo = RecipeRepository(settings.data_dir)
    all_recipes = repo.list_all()

    to_submit = [r for r in all_recipes if _needs_extraction(r, force=force)]
    already_extracted = [r for r in all_recipes if r.instructions]
    no_caption = [
        r
        for r in all_recipes
        if r.caption is None or len(r.caption.strip()) < MIN_CAPTION_LENGTH
    ]

    logger.info("Total recipes: %d", len(all_recipes))
    logger.info("Already extracted: %d (have instructions)", len(already_extracted))
    logger.info("No caption: %d", len(no_caption))
    logger.info("Will submit: %d%s", len(to_submit), " (force=True)" if force else "")

    if not to_submit:
        logger.info("Nothing to submit.")
        return

    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    schema = ExtractedRecipe.model_json_schema()

    BATCH_INPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BATCH_INPUT_PATH.open("w", encoding="utf-8") as fh:
        for recipe in to_submit:
            caption = recipe.caption or ""
            line: dict[str, object] = {
                "custom_id": recipe.code,
                "method": "POST",
                "url": "/v1/responses",
                "body": {
                    "model": MODEL,
                    "input": prompt_template.format(caption=caption),
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "ExtractedRecipe",
                            "schema": schema,
                            "strict": True,
                        },
                    },
                },
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


def cmd_apply(settings: Settings, batch_id: str | None) -> None:
    """Download a completed batch output and update recipes in the repository."""
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

    repo = RecipeRepository(settings.data_dir)
    applied = 0
    skipped = 0
    errors = 0
    now = datetime.now(tz=UTC)

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        code = "<unknown>"
        try:
            result: dict[str, object] = json.loads(line)
            code = str(result["custom_id"])

            existing = repo.get(code)
            if existing is None:
                logger.warning("Recipe not found for code %s — skipping", code)
                skipped += 1
                continue

            response_body: dict[str, object] = result["response"]["body"]  # type: ignore[index]
            output_text: str = response_body["output"][0]["content"][0]["text"]  # type: ignore[index]
            extracted = ExtractedRecipe.model_validate(json.loads(output_text))

            updated = Recipe.from_extracted(
                code=existing.code,
                pk=existing.pk,
                caption=existing.caption,
                extracted=extracted,
                model_used=MODEL,
            ).model_copy(
                update={
                    "thumbnail_url": existing.thumbnail_url,
                    "cloudinary_url": existing.cloudinary_url,
                    "user_notes": existing.user_notes,
                    "is_favorite": existing.is_favorite,
                    "edited_by_user": existing.edited_by_user,
                    "extracted_at": now,
                },
            )

            repo.save(updated)
            applied += 1

        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError):
            logger.exception("Failed to parse result for code %s", code)
            errors += 1

    logger.info("Applied: %d  Skipped: %d  Errors: %d", applied, skipped, errors)


def main() -> None:
    """Entry point for the batch recipe extraction CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Batch recipe extraction via OpenAI Batch API",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    submit_parser = subparsers.add_parser("submit", help="Build and submit a batch job")
    submit_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-submit all eligible recipes, including those already extracted",
    )

    status_parser = subparsers.add_parser("status", help="Check batch status")
    status_parser.add_argument("batch_id", nargs="?", default=None)

    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply completed batch results to the recipe repository",
    )
    apply_parser.add_argument("batch_id", nargs="?", default=None)

    args = parser.parse_args()
    settings = Settings()

    if args.command == "submit":
        cmd_submit(settings, force=args.force)
    elif args.command == "status":
        cmd_status(settings, args.batch_id)
    elif args.command == "apply":
        cmd_apply(settings, args.batch_id)


if __name__ == "__main__":
    main()
