"""Thin CLI wrapper around foodiegram.app.extraction.

Commands:
  submit [--all]     Build and submit an OpenAI batch job (default: only-missing).
  status [BATCH_ID]  Check batch progress.
  apply  [BATCH_ID]  Download completed results into the extractions table.
  smoke  [--limit N] Synchronously validate a few extractions (default 5).
"""

import argparse
import logging
from datetime import UTC, datetime

from foodiegram.ai.batch import log_batch_status
from foodiegram.app.extraction import apply_batch, smoke_test, submit_batch
from foodiegram.settings import Settings
from foodiegram.storage.db import create_db_engine, init_db
from foodiegram.storage.extractions_db import ExtractionRepository
from foodiegram.storage.recipes_db import RecipeRepository


def _positive_int(raw: str) -> int:
    """Parse a strictly positive integer for the --limit argument."""
    value = int(raw)
    if value < 1:
        msg = f"must be a positive integer, got {value}"
        raise argparse.ArgumentTypeError(msg)
    return value


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
        "--all",
        action="store_true",
        help="Re-submit every captioned recipe, including those already extracted "
        "at the current prompt version (default: only-missing)",
    )
    submit_parser.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help="Submit only the first N eligible recipes (for a small test run)",
    )

    status_parser = subparsers.add_parser("status", help="Check batch status")
    status_parser.add_argument("batch_id", nargs="?", default=None)

    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply completed batch results to the recipe repository",
    )
    apply_parser.add_argument("batch_id", nargs="?", default=None)

    smoke_parser = subparsers.add_parser(
        "smoke",
        help="Synchronously extract a few captions and validate the responses",
    )
    smoke_parser.add_argument(
        "--limit",
        type=_positive_int,
        default=5,
        help="Number of eligible captions to test (default 5)",
    )

    args = parser.parse_args()
    settings = Settings()

    if args.command == "status":
        log_batch_status(settings, args.batch_id)
        return

    engine = create_db_engine(settings.database_url)
    init_db(engine)
    recipes = RecipeRepository(engine)
    extractions = ExtractionRepository(engine)

    if args.command == "submit":
        submit_batch(
            settings,
            recipes=recipes,
            extractions=extractions,
            only_missing=not args.all,
            limit=args.limit,
        )
    elif args.command == "apply":
        apply_batch(
            settings,
            args.batch_id,
            extractions=extractions,
            applied_at=datetime.now(tz=UTC),
        )
    elif args.command == "smoke":
        smoke_test(settings, recipes=recipes, extractions=extractions, limit=args.limit)


if __name__ == "__main__":
    main()
