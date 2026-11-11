"""aifun.processing's DB-coupled orchestration around the pure
aifun.assemble functions: Highlight persistence, Media.stage transitions,
and resumability after a simulated crash. Runs `_run_processing` directly
and synchronously (bypassing the thread pool) against real ffmpeg/Whisper —
uses `make_real_media` (see conftest.py) since aifun.processing opens its
own DB session, which the transaction-rollback `db_session` fixture can't
intercept.
"""

import subprocess
from pathlib import Path

from aifun.db.models import Highlight, Media
from aifun.db.session import SessionLocal
from aifun.processing import _run_processing, reconcile_orphaned_jobs


def _make_clip_with_scenes_and_audio(tmp_path):
    path = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=red:s=320x240:d=2:r=10",
            "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=2:r=10",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map", "[v]", "-map", "2:a", "-shortest",
            str(path),
        ],
        check=True,
    )
    return path


def test_process_video_persists_highlights_and_top_output(tmp_path, make_real_media):
    clip = _make_clip_with_scenes_and_audio(tmp_path)
    media_id = make_real_media(
        storage_key=str(clip),
        output_key=None,
        kind="video",
        status="processing",
        original_filename="clip.mp4",
        mime_type="video/mp4",
        size_bytes=clip.stat().st_size,
        duration_seconds=4.0,
    )

    _run_processing(media_id)

    db = SessionLocal()
    try:
        media = db.get(Media, media_id)
        assert media.status == "processed"
        assert media.stage is None
        assert media.output_key and Path(media.output_key).exists()

        highlights = db.query(Highlight).filter(Highlight.media_id == media_id).all()
        assert len(highlights) >= 1
        assert all(h.status == "rendered" for h in highlights)
        assert all(h.clip_key and Path(h.clip_key).exists() for h in highlights)
    finally:
        db.close()


def test_process_video_skips_already_rendered_highlights_on_retry(tmp_path, make_real_media):
    """Simulates a crash-and-retry: run once, note the highlight ids and
    their preview file mtimes, run again, and confirm no new highlights
    were detected and none were re-rendered (resumability — see
    aifun.processing._process_video).
    """
    clip = _make_clip_with_scenes_and_audio(tmp_path)
    media_id = make_real_media(
        storage_key=str(clip),
        output_key=None,
        kind="video",
        status="processing",
        original_filename="clip.mp4",
        mime_type="video/mp4",
        size_bytes=clip.stat().st_size,
        duration_seconds=4.0,
    )

    _run_processing(media_id)

    db = SessionLocal()
    try:
        first_run = db.query(Highlight).filter(Highlight.media_id == media_id).all()
        first_ids = {h.id for h in first_run}
        first_mtimes = {h.id: Path(h.clip_key).stat().st_mtime for h in first_run}
        media = db.get(Media, media_id)
        media.status = "processing"  # simulate a manual retry trigger
        db.commit()
    finally:
        db.close()

    _run_processing(media_id)

    db = SessionLocal()
    try:
        second_run = db.query(Highlight).filter(Highlight.media_id == media_id).all()
        assert {h.id for h in second_run} == first_ids  # no re-detection
        for h in second_run:
            assert Path(h.clip_key).stat().st_mtime == first_mtimes[h.id]  # no re-render
    finally:
        db.close()


def test_reconcile_orphaned_jobs_flips_stuck_processing_to_failed(make_real_media):
    media_id = make_real_media(
        storage_key="/tmp/does-not-matter.mp4",
        output_key=None,
        kind="video",
        status="processing",
        stage="transcribing",
        original_filename="clip.mp4",
        mime_type="video/mp4",
        size_bytes=1,
        duration_seconds=1.0,
    )

    reconcile_orphaned_jobs()

    db = SessionLocal()
    try:
        media = db.get(Media, media_id)
        assert media.status == "failed"
        assert media.stage is None
    finally:
        db.close()
