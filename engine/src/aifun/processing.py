import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aifun.db.models import Media
from aifun.db.session import SessionLocal
from aifun.utils.media import DATA_OUTPUT_DIR

_executor = ThreadPoolExecutor(max_workers=4)


def schedule_processing(media_id: uuid.UUID) -> None:
    _executor.submit(_run_processing, media_id)


def _run_processing(media_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        media = db.get(Media, media_id)
        if media is None:
            return

        try:
            time.sleep(2)
            DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            input_path = Path(media.storage_key)
            output_path = DATA_OUTPUT_DIR / input_path.name
            shutil.copyfile(input_path, output_path)
            media.output_key = str(output_path)
            media.status = "processed"
        except Exception:
            media.status = "failed"

        db.commit()
    finally:
        db.close()
