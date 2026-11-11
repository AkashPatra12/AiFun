import asyncio
import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from aifun.api.schemas import HighlightOut, MediaOut
from aifun.db.models import Highlight, Media
from aifun.db.session import SessionLocal, get_db
from aifun.ingest import ingest_upload
from aifun.processing import schedule_processing
from aifun.utils.media import DATA_INPUT_DIR

router = APIRouter()

ALLOWED_EXTENSIONS = {
    "video": {"mp4", "mov"},
    "photo": {"jpg", "png"},
}

# How often the SSE stream below re-checks Postgres for a change. Real-time
# in the sense that matters here — a push to the browser as soon as this
# process notices a change — not a DB trigger/notify (see GET .../events).
SSE_POLL_INTERVAL_SECONDS = 0.5


@router.post("/media", response_model=MediaOut, status_code=201)
async def create_media(
    file: UploadFile,
    kind: str = Form(...),
    autoProcess: bool = Form(True),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename).suffix.lstrip(".").lower()
    if kind not in ALLOWED_EXTENSIONS or ext not in ALLOWED_EXTENSIONS[kind]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}' for kind '{kind}'",
        )

    media_id = uuid.uuid4()
    data = await file.read()

    try:
        ingested = ingest_upload(media_id, ext, data, kind)
    except RuntimeError as exc:
        (DATA_INPUT_DIR / f"{media_id}.{ext}").unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    media = Media(
        id=media_id,
        storage_key=ingested["storage_key"],
        kind=kind,
        status="uploaded",
        original_filename=file.filename,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        duration_seconds=ingested["duration_seconds"],
        width=ingested["width"],
        height=ingested["height"],
    )
    db.add(media)
    db.commit()
    db.refresh(media)

    if autoProcess:
        media.status = "processing"
        db.commit()
        db.refresh(media)
        schedule_processing(media_id)

    return media


@router.get("/media", response_model=list[MediaOut])
def list_media(db: Session = Depends(get_db)):
    return db.query(Media).order_by(Media.created_at.desc()).all()


@router.post("/media/{media_id}/process", response_model=MediaOut)
def process_media(media_id: uuid.UUID, db: Session = Depends(get_db)):
    media = db.get(Media, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    if media.status not in ("uploaded", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot process media in status '{media.status}'",
        )

    media.status = "processing"
    db.commit()
    db.refresh(media)
    schedule_processing(media_id)
    return media


@router.get("/media/{media_id}/output")
def get_media_output(media_id: uuid.UUID, db: Session = Depends(get_db)):
    media = db.get(Media, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    if media.status != "processed" or not media.output_key:
        raise HTTPException(
            status_code=409,
            detail=f"Media is not processed yet (status '{media.status}')",
        )

    # media.mime_type/original_filename describe the *upload*; the output
    # can be a different container (e.g. a .mov upload is always re-muxed to
    # .mp4 — see aifun.processing), so derive these from the output file
    # itself rather than the stale upload metadata.
    output_path = Path(media.output_key)
    media_type, _ = mimetypes.guess_type(output_path.name)
    download_filename = Path(media.original_filename).stem + output_path.suffix

    return FileResponse(
        output_path,
        media_type=media_type or "application/octet-stream",
        filename=download_filename,
    )


@router.delete("/media/{media_id}", status_code=204)
def delete_media(media_id: uuid.UUID, db: Session = Depends(get_db)):
    media = db.get(Media, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    if media.status == "processing":
        raise HTTPException(
            status_code=409, detail="Cannot delete media while it is processing"
        )

    highlights = db.query(Highlight).filter(Highlight.media_id == media_id).all()
    for highlight in highlights:
        if highlight.clip_key:
            Path(highlight.clip_key).unlink(missing_ok=True)
        db.delete(highlight)

    for path in (media.storage_key, media.output_key):
        if path:
            Path(path).unlink(missing_ok=True)

    db.delete(media)
    db.commit()


@router.get("/media/{media_id}/highlights", response_model=list[HighlightOut])
def list_highlights(media_id: uuid.UUID, db: Session = Depends(get_db)):
    if db.get(Media, media_id) is None:
        raise HTTPException(status_code=404, detail="Media not found")

    return (
        db.query(Highlight)
        .filter(Highlight.media_id == media_id)
        .order_by(Highlight.score.desc())
        .all()
    )


@router.get("/highlights/{highlight_id}/preview")
def get_highlight_preview(highlight_id: uuid.UUID, db: Session = Depends(get_db)):
    highlight = db.get(Highlight, highlight_id)
    if highlight is None:
        raise HTTPException(status_code=404, detail="Highlight not found")
    if highlight.status != "rendered" or not highlight.clip_key:
        raise HTTPException(
            status_code=409,
            detail=f"Highlight preview is not ready yet (status '{highlight.status}')",
        )

    return FileResponse(highlight.clip_key, media_type="video/mp4")


@router.get("/media/{media_id}/events")
async def media_events(media_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    """Server-Sent Events stream of this media's status/stage, so the UI
    gets pushed updates instead of waiting out its own ~2s poll interval.
    Internally this is still a poll — of Postgres, from this process, every
    SSE_POLL_INTERVAL_SECONDS — rather than a DB trigger/LISTEN-NOTIFY setup;
    simple, and Postgres is already the single source of truth the
    background job (aifun.processing) writes to, so no separate in-memory
    event bus is needed to bridge the two. Closes itself once the media
    reaches a terminal status, or the client disconnects.
    """
    if db.get(Media, media_id) is None:
        raise HTTPException(status_code=404, detail="Media not found")

    async def event_stream():
        last_payload = None
        stream_db = SessionLocal()
        try:
            while True:
                if await request.is_disconnected():
                    break

                # Without this, .get() on a long-lived session just returns
                # its own cached copy of the row forever — the background
                # job (aifun.processing) writes through a different session
                # entirely, so this one never sees those commits otherwise.
                stream_db.expire_all()
                media = stream_db.get(Media, media_id)
                if media is None:
                    yield "event: error\ndata: media not found\n\n"
                    return

                payload = MediaOut.model_validate(media).model_dump_json(by_alias=True)
                if payload != last_payload:
                    yield f"data: {payload}\n\n"
                    last_payload = payload

                if media.status in ("processed", "failed"):
                    return

                await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)
        finally:
            stream_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
