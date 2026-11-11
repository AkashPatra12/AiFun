import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class MediaOut(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )

    id: uuid.UUID
    kind: str
    status: str
    stage: str | None
    original_filename: str
    mime_type: str
    size_bytes: int
    duration_seconds: float | None
    width: int | None
    height: int | None
    thumbnail_key: str | None
    created_at: datetime


class HighlightOut(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )

    id: uuid.UUID
    media_id: uuid.UUID
    start_seconds: float
    end_seconds: float
    score: float
    reason: str
    status: str
    clip_key: str | None
    created_at: datetime
