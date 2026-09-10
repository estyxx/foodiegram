import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Stage:
    """One named step in the Stage B pipeline, wrapping a use-case call."""

    name: str
    run: Callable[[], str]


def run_stages(stages: Sequence[Stage]) -> list[str]:
    """Run stages in order, returning each stage's summary line.

    Stops at the first stage that raises: the exception propagates unchanged so
    a broken state is never pushed downstream, and later stages do not run. The
    caller (CLI edge) decides how to report the failure.
    """
    summaries: list[str] = []
    for stage in stages:
        logger.info("sync all: %s", stage.name)
        summary = stage.run()
        summaries.append(f"{stage.name}: {summary}")
    return summaries
