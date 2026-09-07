import json
import subprocess

from typer.testing import CliRunner

from aifun.cli import app

runner = CliRunner()


def test_analyze_command_writes_highlights_file(tmp_path):
    clip = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=5",
            str(clip),
        ],
        check=True,
    )
    output_path = tmp_path / "highlights.json"

    result = runner.invoke(
        app,
        [
            "analyze", str(clip),
            "--output-path", str(output_path),
            "--media-id", "cli-test-media",
        ],
    )

    assert result.exit_code == 0, result.output
    highlights = json.loads(output_path.read_text())
    assert len(highlights) >= 1
    assert highlights[0]["sourceMediaId"] == "cli-test-media"


def test_score_photo_command_prints_json(tmp_path):
    image = tmp_path / "photo.jpg"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=gray:s=160x120",
            "-frames:v", "1", str(image),
        ],
        check=True,
    )

    result = runner.invoke(app, ["score-photo", str(image)])

    assert result.exit_code == 0, result.output
    body = json.loads(result.output)
    assert "score" in body
