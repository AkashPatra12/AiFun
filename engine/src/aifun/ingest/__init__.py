import uuid

from aifun.utils.media import probe_metadata, save_upload


def ingest_upload(media_id: uuid.UUID, ext: str, data: bytes) -> dict:
    path = save_upload(media_id, ext, data)
    metadata = probe_metadata(path)
    return {"storage_key": str(path), **metadata}
