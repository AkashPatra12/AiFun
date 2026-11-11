import uuid

from aifun.utils.media import probe_metadata, save_upload


def ingest_upload(media_id: uuid.UUID, ext: str, data: bytes, kind: str) -> dict:
    path = save_upload(media_id, ext, data)
    metadata = probe_metadata(path)
    if kind == "photo":
        # A static image has no meaningful duration — ffprobe still reports
        # a tiny format.duration for a single-frame JPEG (e.g. 0.04s from
        # its default frame-rate metadata), which isn't a real duration.
        metadata["duration_seconds"] = None
    return {"storage_key": str(path), **metadata}
