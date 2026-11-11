import subprocess

import pytest

from aifun.analysis.photo_score import score_photo


def _make_image(tmp_path, name, ffmpeg_source):
    path = tmp_path / name
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", ffmpeg_source,
         "-frames:v", "1", str(path)],
        check=True,
    )
    return path


def test_score_photo_returns_expected_shape(tmp_path):
    image = _make_image(tmp_path, "flat.jpg", "color=c=gray:s=320x240")

    result = score_photo(str(image))

    assert set(result) == {"sharpness", "exposure", "hasFace", "score"}
    assert 0.0 <= result["score"] <= 1.0
    assert result["hasFace"] is False


def test_score_photo_mid_gray_scores_well_exposed(tmp_path):
    image = _make_image(tmp_path, "mid_gray.jpg", "color=c=gray:s=320x240")
    result = score_photo(str(image))
    assert result["exposure"] == pytest.approx(128, abs=2)


def test_score_photo_black_image_scores_poorly_exposed(tmp_path):
    black = _make_image(tmp_path, "black.jpg", "color=c=black:s=320x240")
    gray = _make_image(tmp_path, "gray.jpg", "color=c=gray:s=320x240")

    assert score_photo(str(black))["score"] < score_photo(str(gray))["score"]


def test_score_photo_missing_file_raises():
    with pytest.raises(ValueError):
        score_photo("/nonexistent/path.jpg")
