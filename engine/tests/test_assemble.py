"""Exercises the real FFmpeg + Whisper + analysis pipeline
(docs/phase4-smart-editing.md) — no DB, no API, just files. Requires the
`ffmpeg`/`ffprobe` binaries, same as production. The DB-coupled
orchestration around these (Highlight persistence, Media.stage, retry
resumability) lives in aifun.processing and is exercised via the API
routes tests instead (test_media_routes.py), since it needs a Media row.
"""

import json
import subprocess

import pytest

from aifun.assemble import detect_highlights, render_and_export
from aifun.utils.media import has_audio_stream


def _ffprobe(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def _video_stream(probe):
    return next(s for s in probe["streams"] if s["codec_type"] == "video")


def test_detect_highlights_matches_contract_shape(tmp_path):
    clip = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
            str(clip),
        ],
        check=True,
    )

    highlights = detect_highlights("media-1", str(clip), duration_seconds=2.0)

    assert len(highlights) >= 1
    assert highlights[0]["sourceMediaId"] == "media-1"


def test_render_and_export_video_is_vertical_with_audio(tmp_path):
    src = tmp_path / "src.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10",
            str(src),
        ],
        check=True,
    )
    assert not has_audio_stream(src)  # source has no audio of its own

    output_dir = tmp_path / "output"
    output_path = render_and_export(
        input_path=str(src),
        start=0.0,
        end=3.0,
        is_photo=False,
        output_dir=str(output_dir),
        output_filename="test-video.mp4",
    )

    probe = _ffprobe(output_path)
    video = _video_stream(probe)
    assert video["width"] == 1080
    assert video["height"] == 1920
    assert float(probe["format"]["duration"]) == pytest.approx(3.0, abs=0.15)
    assert has_audio_stream(output_path)  # fixed background track was mixed in


def test_render_and_export_photo_is_cropped(tmp_path):
    src = tmp_path / "src.jpg"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=blue:s=800x600", "-frames:v", "1",
            str(src),
        ],
        check=True,
    )

    output_dir = tmp_path / "output"
    output_path = render_and_export(
        input_path=str(src),
        start=0.0,
        end=0.0,
        is_photo=True,
        output_dir=str(output_dir),
        output_filename="test-photo.jpg",
    )

    assert output_path.endswith(".jpg")
    probe = _ffprobe(output_path)
    video = _video_stream(probe)
    assert video["width"] == 1080
    assert video["height"] == 1920
