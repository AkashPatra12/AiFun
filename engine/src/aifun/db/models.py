import uuid

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Media(Base):
    __tablename__ = "media"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    output_key: Mapped[str | None] = mapped_column(String, nullable=True)

    kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="uploaded")

    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    thumbnail_key: Mapped[str | None] = mapped_column(String, nullable=True)

    # Sub-status within status="processing" — transcribing / detecting_highlights
    # / rendering_previews / exporting — so the UI can show more than a bare
    # spinner. Null outside of an active processing run.
    stage: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Highlight(Base):
    """A candidate smart-clip segment for a video Media row — persisted so
    detection (the expensive Whisper/scene-detection work) survives a crash
    mid-job, and so candidates can be reviewed/edited later rather than only
    the one auto-picked for the main output. See aifun.analysis.find_highlights
    and docs/phase4-smart-editing.md.
    """

    __tablename__ = "highlights"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)

    # pending (row exists, preview not rendered yet) -> rendered / failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    clip_key: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
