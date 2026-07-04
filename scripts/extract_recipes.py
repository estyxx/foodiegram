"""Thin CLI wrapper around foodiegram.ai.batch.

Commands:
  submit [--force]   Build and submit an OpenAI batch job.
  status [BATCH_ID]  Check batch progress.
  apply  [BATCH_ID]  Download and apply completed batch results.
  smoke  [--limit N] Synchronously validate a few extractions (default 5).
"""

import argparse
import logging

from foodiegram.ai.batch import cmd_apply, cmd_smoke, cmd_status, cmd_submit
from foodiegram.settings import Settings


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
        "--force",
        action="store_true",
        help="Re-submit all eligible recipes, including those already extracted",
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

    if args.command == "submit":
        cmd_submit(settings, force=args.force, limit=args.limit)
    elif args.command == "status":
        cmd_status(settings, args.batch_id)
    elif args.command == "apply":
        cmd_apply(settings, args.batch_id)
    elif args.command == "smoke":
        cmd_smoke(settings, limit=args.limit)


if __name__ == "__main__":
    main()
