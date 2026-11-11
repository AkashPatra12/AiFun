"""Phase 4 (docs/README.md step 12): the real, non-fixture Assemble
pipeline — detect highlights for real (aifun.transcribe + aifun.analysis)
instead of Phase 2's hand-authored fixture, and render a 9:16 preview clip
per candidate rather than just the one auto-picked for the main output.

Kept DB-free/pure, like Phase 2's version was — aifun.processing owns
persisting Highlight rows and Media.stage transitions around these calls,
which is also what makes a crashed/retried job resumable (see
aifun.processing._process_video).
"""

import tempfile
from pathlib import Path

from aifun.analysis import find_highlights
from aifun.export import export_clip
from aifun.render import render_clip
from aifun.transcribe import transcribe_video


def detect_highlights(
    media_id: str, input_path: str, duration_seconds: float | None
) -> list[dict]:
    """Transcribe + score highlights — the expensive step. Returns a list
    matching contracts/highlight.schema.json, already sorted best-first and
    capped at config/settings.yaml's max_clips_per_video.
    """
    transcript = transcribe_video(input_path)
    return find_highlights(media_id, input_path, transcript, duration_seconds)


def render_and_export(
    input_path: str,
    start: float,
    end: float,
    is_photo: bool,
    output_dir: str,
    output_filename: str,
) -> str:
    """Cut/reframe/mix-audio one window (a highlight, or — for a photo,
    where start/end are unused — the whole image) and export it. The same
    building blocks Phase 2 used for its single fixture-driven output, now
    also called once per highlight candidate.
    """
    with tempfile.TemporaryDirectory(prefix="aifun-render-") as tmp:
        rendered_path = render_clip(
            input_path, start, end, is_photo=is_photo, work_dir=Path(tmp)
        )
        return export_clip(rendered_path, output_dir, output_filename)
