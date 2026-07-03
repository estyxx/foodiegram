"""Thin CLI wrapper around foodiegram.ai.batch.

Commands:
  submit [--force]   Build and submit an OpenAI batch job.
  status [BATCH_ID]  Check batch progress.
  apply  [BATCH_ID]  Download and apply completed batch results.
"""

import argparse
import logging

from foodiegram.ai.batch import cmd_apply, cmd_status, cmd_submit
from foodiegram.settings import Settings


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
