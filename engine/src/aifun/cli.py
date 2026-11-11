import json
from dataclasses import asdict
from pathlib import Path

import typer

app = typer.Typer(help="AiFun - Auto Reel/Shorts Generator")


@app.command()
def process(input_path: str, output_dir: str = "data/output"):
    """Turn a long-form video into one or more short-form clips."""
    from aifun.pipeline import run_pipeline

    run_pipeline(input_path, output_dir)


@app.command()
def transcribe(input_path: str, model_size: str = "tiny"):
    """Transcribe a video locally with Whisper and print the segments."""
    from aifun.transcribe import transcribe_video

    segments = transcribe_video(input_path, model_size=model_size)
    typer.echo(json.dumps([asdict(s) for s in segments], indent=2))


@app.command()
def analyze(
    input_path: str,
    output_path: str = "highlights.json",
    media_id: str = "cli-media",
    model_size: str = "tiny",
):
    """Transcribe + score highlights for a video, writing a
    contracts/highlight.schema.json-shaped file — the Engine: Understand
    track's standalone entry point (docs/README.md Phase 3), independent
    of the API/DB/queue.
    """
    from aifun.analysis import find_highlights
    from aifun.transcribe import transcribe_video
    from aifun.utils.media import probe_metadata

    duration = probe_metadata(Path(input_path))["duration_seconds"]
    transcript = transcribe_video(input_path, model_size=model_size)
    highlights = find_highlights(media_id, input_path, transcript, duration)

    Path(output_path).write_text(json.dumps(highlights, indent=2))
    typer.echo(f"Wrote {len(highlights)} highlight(s) to {output_path}")


@app.command("score-photo")
def score_photo_cmd(input_path: str):
    """Score a photo (sharpness/exposure/face presence) for photo-mode reels."""
    from aifun.analysis.photo_score import score_photo

    typer.echo(json.dumps(score_photo(input_path), indent=2))


if __name__ == "__main__":
    app()
