from datetime import datetime

from pydantic import BaseModel, ConfigDict

from dispensa.domain.enums import BatchStatus


class BatchRun(BaseModel):
    """One submitted OpenAI extraction batch and the recipes it covers.

    Replaces the local-only `data/last_batch_id.txt` hack: the batch id and the
    codes it carries live in the database, so a deployed, disk-less process can
    find a batch between submitting it and applying its results.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_id: str
    prompt_version: str
    codes: tuple[str, ...]
    status: BatchStatus = BatchStatus.SUBMITTED
    submitted_at: datetime
