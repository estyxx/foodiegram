"""Backfill the extractions table from kept batch_output.jsonl files.

One-shot: reconstructs append-only extraction history for recipes extracted
before the extractions table existed. Idempotent per (version, batch): codes
already present at the current PROMPT_VERSION are skipped. Honours DATABASE_URL
(default sqlite:///data/dispensa.db). Run via:
uv run scripts/backfill_extractions.py [data/batch_output.jsonl ...]
"""

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from foodiegram.ai.batch import PROMPT_VERSION, result_to_extraction
from foodiegram.domain.errors import ExtractionError
from foodiegram.settings import Settings
from foodiegram.storage.db import create_db_engine, init_db
from foodiegram.storage.extractions_db import ExtractionRepository

DEFAULT_FILE = Path("data/batch_output.jsonl")
LAST_BATCH_ID_PATH = Path("data/last_batch_id.txt")

logger = logging.getLogger(__name__)


def main() -> None:
    """Load extraction rows from batch output files, skipping duplicates."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Backfill the extractions table from batch output files.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        default=[DEFAULT_FILE],
        metavar="FILE",
        help=f"Batch output JSONL files (default: {DEFAULT_FILE})",
    )
    parser.add_argument(
        "--batch-id",
        default=None,
        help="Batch id to stamp (default: data/last_batch_id.txt if present)",
    )
    args = parser.parse_args()

    batch_id: str | None = args.batch_id
    if batch_id is None and LAST_BATCH_ID_PATH.exists():
        batch_id = LAST_BATCH_ID_PATH.read_text(encoding="utf-8").strip() or None

    settings = Settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    extractions = ExtractionRepository(engine)

    already = set(extractions.latest_by_code(PROMPT_VERSION))
    fallback = datetime.now(tz=UTC)
    added = skipped = errors = 0

    for path in args.files:
        if not path.exists():
            logger.error("File not found: %s", path)
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                extraction = result_to_extraction(
                    line=line,
                    batch_id=batch_id,
                    extracted_at=fallback,
                )
            except (
                KeyError,
                IndexError,
                TypeError,
                json.JSONDecodeError,
                ValidationError,
                ExtractionError,
            ):
                logger.exception("Failed to parse a line in %s", path)
                errors += 1
                continue

            if extraction.recipe_code in already:
                skipped += 1
                continue
            extractions.add(extraction)
            already.add(extraction.recipe_code)
            added += 1

    print(
        f"Backfilled {added} extractions at v{PROMPT_VERSION} "
        f"({skipped} already present, {errors} errors)",
    )


if __name__ == "__main__":
    main()
