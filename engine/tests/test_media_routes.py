import uuid
from pathlib import Path

import pytest

from aifun.db.models import Media


def test_create_media_video(client, tiny_video_bytes):
    res = client.post(
        "/media",
        files={"file": ("clip.mp4", tiny_video_bytes, "video/mp4")},
        data={"kind": "video", "autoProcess": "false"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["kind"] == "video"
    assert body["status"] == "uploaded"
    assert body["originalFilename"] == "clip.mp4"
    assert body["durationSeconds"] == pytest.approx(2.0, abs=0.1)
    assert body["width"] == 320
    assert body["height"] == 240


def test_create_media_photo_has_null_duration(client, tiny_photo_bytes):
    """Regression test: a photo's durationSeconds must be null, not the tiny
    non-zero value ffprobe reports for a single-frame JPEG (see
    docs/progress.md §5 and aifun.ingest.ingest_upload).
    """
    res = client.post(
        "/media",
        files={"file": ("photo.jpg", tiny_photo_bytes, "image/jpeg")},
        data={"kind": "photo", "autoProcess": "false"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["durationSeconds"] is None
    assert body["width"] == 640
    assert body["height"] == 480


def test_create_media_rejects_mismatched_extension(client, tiny_video_bytes):
    res = client.post(
        "/media",
        files={"file": ("clip.mp4", tiny_video_bytes, "video/mp4")},
        data={"kind": "photo", "autoProcess": "false"},
    )
    assert res.status_code == 400


def test_create_media_auto_process_schedules_processing(client, tiny_video_bytes):
    """schedule_processing is monkeypatched to a no-op in the `client`
    fixture, so this only asserts the status transition, not a real render.
    """
    res = client.post(
        "/media",
        files={"file": ("clip.mp4", tiny_video_bytes, "video/mp4")},
        data={"kind": "video", "autoProcess": "true"},
    )
    assert res.status_code == 201
    assert res.json()["status"] == "processing"


def test_list_media_includes_created_row(client, tiny_video_bytes):
    created = client.post(
        "/media",
        files={"file": ("clip.mp4", tiny_video_bytes, "video/mp4")},
        data={"kind": "video", "autoProcess": "false"},
    ).json()

    res = client.get("/media")
    assert res.status_code == 200
    assert any(item["id"] == created["id"] for item in res.json())


def test_process_media_not_found(client):
    res = client.post(f"/media/{uuid.uuid4()}/process")
    assert res.status_code == 404


def test_process_media_wrong_status_conflicts(client, tiny_video_bytes):
    created = client.post(
        "/media",
        files={"file": ("clip.mp4", tiny_video_bytes, "video/mp4")},
        data={"kind": "video", "autoProcess": "true"},  # already "processing"
    ).json()

    res = client.post(f"/media/{created['id']}/process")
    assert res.status_code == 409


def test_process_media_retries_from_uploaded(client, tiny_video_bytes):
    created = client.post(
        "/media",
        files={"file": ("clip.mp4", tiny_video_bytes, "video/mp4")},
        data={"kind": "video", "autoProcess": "false"},
    ).json()

    res = client.post(f"/media/{created['id']}/process")
    assert res.status_code == 200
    assert res.json()["status"] == "processing"


def test_get_output_not_found(client):
    res = client.get(f"/media/{uuid.uuid4()}/output")
    assert res.status_code == 404


def test_get_output_before_processed_conflicts(client, tiny_video_bytes):
    created = client.post(
        "/media",
        files={"file": ("clip.mp4", tiny_video_bytes, "video/mp4")},
        data={"kind": "video", "autoProcess": "false"},
    ).json()

    res = client.get(f"/media/{created['id']}/output")
    assert res.status_code == 409


def test_delete_media_not_found(client):
    res = client.delete(f"/media/{uuid.uuid4()}")
    assert res.status_code == 404


def test_delete_media_removes_row_and_input_file(client, db_session, tiny_video_bytes):
    created = client.post(
        "/media",
        files={"file": ("clip.mp4", tiny_video_bytes, "video/mp4")},
        data={"kind": "video", "autoProcess": "false"},
    ).json()
    media = db_session.get(Media, uuid.UUID(created["id"]))
    storage_path = Path(media.storage_key)
    assert storage_path.exists()

    res = client.delete(f"/media/{created['id']}")
    assert res.status_code == 204

    remaining_ids = [item["id"] for item in client.get("/media").json()]
    assert created["id"] not in remaining_ids
    assert not storage_path.exists()


def test_delete_media_while_processing_conflicts(client, tiny_video_bytes):
    created = client.post(
        "/media",
        files={"file": ("clip.mp4", tiny_video_bytes, "video/mp4")},
        data={"kind": "video", "autoProcess": "true"},  # -> "processing"
    ).json()

    res = client.delete(f"/media/{created['id']}")
    assert res.status_code == 409
