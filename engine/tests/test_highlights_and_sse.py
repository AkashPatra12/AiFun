import json
import threading
import time
import uuid

from aifun.db.models import Highlight, Media
from aifun.db.session import SessionLocal


def _create_media_row(db_session, **overrides):
    media = Media(
        storage_key="/tmp/does-not-matter.mp4",
        kind="video",
        status="processed",
        original_filename="clip.mp4",
        mime_type="video/mp4",
        size_bytes=1,
        duration_seconds=4.0,
        **overrides,
    )
    db_session.add(media)
    db_session.commit()
    return media


def test_list_highlights_returns_rows_sorted_by_score(client, db_session):
    media = _create_media_row(db_session)
    low = Highlight(media_id=media.id, start_seconds=0, end_seconds=1, score=0.2, reason="low")
    high = Highlight(media_id=media.id, start_seconds=1, end_seconds=2, score=0.9, reason="high")
    db_session.add_all([low, high])
    db_session.commit()

    res = client.get(f"/media/{media.id}/highlights")

    assert res.status_code == 200
    body = res.json()
    assert [h["reason"] for h in body] == ["high", "low"]
    assert body[0]["mediaId"] == str(media.id)


def test_list_highlights_media_not_found(client):
    res = client.get(f"/media/{uuid.uuid4()}/highlights")
    assert res.status_code == 404


def test_get_highlight_preview_not_rendered_yet_conflicts(client, db_session):
    media = _create_media_row(db_session)
    highlight = Highlight(
        media_id=media.id, start_seconds=0, end_seconds=1, score=0.5,
        reason="pending", status="pending",
    )
    db_session.add(highlight)
    db_session.commit()

    res = client.get(f"/highlights/{highlight.id}/preview")
    assert res.status_code == 409


def test_get_highlight_preview_not_found(client):
    res = client.get(f"/highlights/{uuid.uuid4()}/preview")
    assert res.status_code == 404


def test_events_stream_closes_immediately_for_terminal_status(make_real_media):
    media_id = make_real_media(
        storage_key="/tmp/does-not-matter.mp4",
        output_key=None,
        kind="video",
        status="processed",
        original_filename="clip.mp4",
        mime_type="video/mp4",
        size_bytes=1,
        duration_seconds=4.0,
    )

    from aifun.api.app import app
    from fastapi.testclient import TestClient

    # Deliberately not `with TestClient(app) as ...` — that re-runs the
    # app's lifespan, including reconcile_orphaned_jobs(), which would
    # immediately flip the row this test just set to "processing" back to
    # "failed" before the stream even opens. Tables already exist (the
    # session-scoped _tables fixture), so skipping startup here is safe.
    test_client = TestClient(app)
    with test_client.stream("GET", f"/media/{media_id}/events") as response:
        assert response.status_code == 200
        lines = [line for line in response.iter_lines() if line]

    assert len(lines) == 1
    payload = json.loads(lines[0].removeprefix("data: "))
    assert payload["id"] == str(media_id)
    assert payload["status"] == "processed"


def test_events_stream_pushes_update_before_terminal(make_real_media):
    """The whole point of SSE over the UI's existing 2s poll: a change
    should reach the stream well inside that window. A background thread
    flips the row to "processed" shortly after the stream opens; the test
    asserts both the "processing" and "processed" states were pushed, and
    that it didn't take anywhere near 2s to see the second one.
    """
    media_id = make_real_media(
        storage_key="/tmp/does-not-matter.mp4",
        output_key=None,
        kind="video",
        status="processing",
        stage="transcribing",
        original_filename="clip.mp4",
        mime_type="video/mp4",
        size_bytes=1,
        duration_seconds=4.0,
    )

    def flip_to_processed_after_delay():
        time.sleep(0.3)
        db = SessionLocal()
        try:
            media = db.get(Media, media_id)
            media.status = "processed"
            media.stage = None
            db.commit()
        finally:
            db.close()

    thread = threading.Thread(target=flip_to_processed_after_delay)
    thread.start()

    from aifun.api.app import app
    from fastapi.testclient import TestClient

    # See the comment in test_events_stream_closes_immediately_for_terminal_status
    # for why this deliberately isn't `with TestClient(app) as ...`.
    test_client = TestClient(app)
    start = time.monotonic()
    with test_client.stream("GET", f"/media/{media_id}/events") as response:
        lines = [line for line in response.iter_lines() if line]
    elapsed = time.monotonic() - start
    thread.join()

    payloads = [json.loads(line.removeprefix("data: ")) for line in lines]
    assert [p["status"] for p in payloads] == ["processing", "processed"]
    assert elapsed < 2.0  # well inside the UI's own poll interval
