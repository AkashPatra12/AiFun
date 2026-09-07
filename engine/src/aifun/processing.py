import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aifun.assemble import detect_highlights, render_and_export
from aifun.db.models import Highlight, Media
from aifun.db.session import SessionLocal
from aifun.export import export_clip
from aifun.utils.media import DATA_OUTPUT_DIR

_executor = ThreadPoolExecutor(max_workers=4)

HIGHLIGHTS_OUTPUT_DIR = DATA_OUTPUT_DIR / "highlights"


def schedule_processing(media_id: uuid.UUID) -> None:
    _executor.submit(_run_processing, media_id)


def reconcile_orphaned_jobs() -> int:
    """Call once on API startup. Phase 1's in-process thread pool
    (docs/phase1-data-ingestion.md §1) has no durable queue to resume
    from, so a Media row still at status="processing" means the previous
    process died mid-job — flip it to "failed" so the existing
    Process/Retry button can pick it back up, rather than leaving it stuck
    forever (POST /media/{id}/process only accepts uploaded/failed).
    Already-persisted Highlight rows for that media are left as-is, so a
    retry resumes rather than re-detecting from scratch — see
    _process_video below.
    """
    db = SessionLocal()
    try:
        orphaned = db.query(Media).filter(Media.status == "processing").all()
        for media in orphaned:
            media.status = "failed"
            media.stage = None
        db.commit()
        return len(orphaned)
    finally:
        db.close()


def _run_processing(media_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        media = db.get(Media, media_id)
        if media is None:
            return

        try:
            if media.kind == "photo":
                _process_photo(db, media)
            else:
                _process_video(db, media)
            media.status = "processed"
            media.stage = None
        except Exception:
            media.status = "failed"

        db.commit()
    finally:
        db.close()


def _process_photo(db, media: Media) -> None:
    media.stage = "exporting"
    db.commit()

    media.output_key = render_and_export(
        input_path=media.storage_key,
        start=0.0,
        end=0.0,
        is_photo=True,
        output_dir=str(DATA_OUTPUT_DIR),
        output_filename=Path(media.storage_key).name,
    )


def _process_video(db, media: Media) -> None:
    media_id = media.id
    highlights = (
        db.query(Highlight)
        .filter(Highlight.media_id == media_id)
        .order_by(Highlight.score.desc())
        .all()
    )

    if not highlights:
        # First run for this media (or a retry from before any highlight
        # was even detected): do the expensive transcribe + scene/highlight
        # scoring once, then persist every candidate immediately, before
        # rendering a single preview — if the process dies partway through
        # rendering below, this detection work is not repeated on retry.
        media.stage = "transcribing"
        db.commit()

        media.stage = "detecting_highlights"
        db.commit()
        detected = detect_highlights(
            str(media_id), media.storage_key, media.duration_seconds
        )

        highlights = [
            Highlight(
                media_id=media_id,
                start_seconds=h["start"],
                end_seconds=h["end"],
                score=h["score"],
                reason=h["reason"],
            )
            for h in detected
        ]
        db.add_all(highlights)
        db.commit()
        highlights.sort(key=lambda h: h.score, reverse=True)

    media.stage = "rendering_previews"
    db.commit()

    HIGHLIGHTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for highlight in highlights:
        if highlight.status == "rendered":
            continue  # already done in a prior (crashed) run — resumability
        try:
            highlight.clip_key = render_and_export(
                input_path=media.storage_key,
                start=highlight.start_seconds,
                end=highlight.end_seconds,
                is_photo=False,
                output_dir=str(HIGHLIGHTS_OUTPUT_DIR),
                output_filename=f"{highlight.id}.mp4",
            )
            highlight.status = "rendered"
        except Exception:
            highlight.status = "failed"
        db.commit()  # per-highlight commit — one failure doesn't lose the rest

    media.stage = "exporting"
    db.commit()

    top_rendered = next((h for h in highlights if h.status == "rendered"), None)
    if top_rendered is None:
        raise RuntimeError("No highlight preview rendered successfully")

    # The top-ranked rendered highlight's preview clip IS the main output —
    # copy it under the media's own output filename rather than re-running
    # the same cut/reframe/audio-mix work a second time.
    media.output_key = export_clip(
        top_rendered.clip_key, str(DATA_OUTPUT_DIR), f"{media_id}.mp4"
    )
