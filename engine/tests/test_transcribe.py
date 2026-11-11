"""Real Whisper calls (tiny model, downloaded/cached under
engine/data/cache/whisper on first run) — no mocking, per the project's
"verify it actually works" approach elsewhere in the test suite.
"""

import subprocess

from aifun.transcribe import transcribe_video


def test_transcribe_video_silent_clip_returns_empty_list(tmp_path):
    """A clip with no audio stream at all must return [] rather than crash
    whisper's ffmpeg-based audio extraction (see docstring in
    aifun.transcribe.transcribe_video).
    """
    silent = tmp_path / "silent.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=160x120:rate=5",
            str(silent),
        ],
        check=True,
    )

    assert transcribe_video(str(silent)) == []


def test_transcribe_video_with_audio_returns_segment_list(tmp_path):
    """A tone isn't speech, so we don't assert on the transcribed text —
    just that a real audio track round-trips through whisper without error
    and comes back as a list of segments with the right shape.
    """
    clip = tmp_path / "tone.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=160x120:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-shortest",
            str(clip),
        ],
        check=True,
    )

    segments = transcribe_video(str(clip))

    assert isinstance(segments, list)
    for segment in segments:
        assert segment.start < segment.end
        assert isinstance(segment.text, str)
