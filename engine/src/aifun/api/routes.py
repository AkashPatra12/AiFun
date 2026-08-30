import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from aifun.api.schemas import MediaOut
from aifun.db.models import Media
from aifun.db.session import get_db
from aifun.ingest import ingest_upload
from aifun.processing import schedule_processing
from aifun.utils.media import DATA_INPUT_DIR

router = APIRouter()

ALLOWED_EXTENSIONS = {
    "video": {"mp4", "mov"},
    "photo": {"jpg", "png"},
}


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
        ingested = ingest_upload(media_id, ext, data)
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

    return FileResponse(
        media.output_key,
        media_type=media.mime_type,
        filename=media.original_filename,
    )
