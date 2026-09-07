import subprocess

from aifun.analysis import _candidate_windows, find_highlights
from aifun.analysis.motion import detect_face_presence, score_motion
from aifun.analysis.scenes import detect_scenes


def _make_two_scene_clip(tmp_path):
    """Two solid-color halves concatenated — a scene cut PySceneDetect's
    ContentDetector is guaranteed to catch, at a known timestamp.
    """
    path = tmp_path / "two_scenes.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=red:s=320x240:d=3:r=10",
            "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=3:r=10",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map", "[v]",
            str(path),
        ],
        check=True,
    )
    return path


def test_detect_scenes_finds_the_cut(tmp_path):
    scenes = detect_scenes(str(_make_two_scene_clip(tmp_path)))

    assert len(scenes) == 2
    (first_start, first_end), (second_start, second_end) = scenes
    assert first_start == 0.0
    assert first_end == second_start
    assert abs(first_end - 3.0) < 0.2
    assert abs(second_end - 6.0) < 0.2


def test_score_motion_is_higher_for_moving_content(tmp_path):
    still = tmp_path / "still.mp4"
    moving = tmp_path / "moving.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=gray:s=320x240:d=2:r=10",
            str(still),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
            str(moving),
        ],
        check=True,
    )

    assert score_motion(str(still), 0, 2) == 0.0
    assert score_motion(str(moving), 0, 2) > 0.0


def test_detect_face_presence_false_on_a_plain_pattern(tmp_path):
    # Negative case only — asserting a true positive needs a real face
    # image, which isn't available as a synthetic ffmpeg fixture.
    clip = _make_two_scene_clip(tmp_path)
    assert detect_face_presence(str(clip), 0, 3) is False


def test_find_highlights_matches_contract_shape(tmp_path):
    clip = _make_two_scene_clip(tmp_path)

    highlights = find_highlights("media-123", str(clip), transcript=[], duration_seconds=6.0)

    assert len(highlights) >= 1
    for highlight in highlights:
        assert highlight["sourceMediaId"] == "media-123"
        assert 0 <= highlight["start"] < highlight["end"]
        assert 0.0 <= highlight["score"] <= 1.0
        assert isinstance(highlight["reason"], str)
    # sorted by score, descending
    scores = [h["score"] for h in highlights]
    assert scores == sorted(scores, reverse=True)


def test_find_highlights_falls_back_when_no_scene_is_long_enough(tmp_path):
    tiny = tmp_path / "tiny.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=green:s=160x120:d=1:r=5",
            str(tiny),
        ],
        check=True,
    )

    highlights = find_highlights("media-1", str(tiny), transcript=[], duration_seconds=1.0)

    assert len(highlights) == 1
    assert highlights[0]["reason"].startswith("fallback")


def test_candidate_windows_returns_scene_unchanged_when_short_enough():
    assert _candidate_windows(0.0, 10.0, window_length=15.0) == [(0.0, 10.0)]


def test_candidate_windows_slides_through_a_long_scene():
    windows = _candidate_windows(0.0, 30.72, window_length=15.0)

    assert len(windows) > 1
    for start, end in windows:
        assert end - start <= 15.0
    assert windows[0][0] == 0.0
    assert windows[-1][1] == 30.72


def test_find_highlights_on_one_long_continuous_scene_yields_sub_clips_not_the_whole_thing(tmp_path):
    """Regression test: a single continuous shot with no internal cuts (the
    common case for real phone footage) used to come back as one highlight
    spanning the entire video — see docs/progress.md's bug report. It
    should now be split into several candidate sub-clips instead.
    """
    clip = tmp_path / "continuous.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=20:size=320x240:rate=10",
            str(clip),
        ],
        check=True,
    )
    assert detect_scenes(str(clip)) == [(0.0, 20.0)]  # confirms no cut was found

    highlights = find_highlights("media-1", str(clip), transcript=[], duration_seconds=20.0)

    assert len(highlights) > 1
    for highlight in highlights:
        assert highlight["end"] - highlight["start"] < 20.0
