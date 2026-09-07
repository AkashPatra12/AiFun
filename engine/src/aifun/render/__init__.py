from pathlib import Path

from aifun.editing import clip, reframe
from aifun.editing.audio import mix_background
from aifun.utils.media import ENGINE_ROOT, has_audio_stream

FIXED_BACKGROUND_TRACK = ENGINE_ROOT / "assets" / "music" / "fixture_track.mp3"


def render_clip(
    input_path: str,
    start: float,
    end: float,
    *,
    is_photo: bool,
    work_dir: Path,
) -> str:
    """Cut -> reframe to 9:16 -> (video only) mix in the fixed background
    track. Returns the path to the fully rendered clip inside work_dir.
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    if is_photo:
        reframed_path = str(work_dir / "reframed.jpg")
        reframe.to_vertical(input_path, reframed_path, is_photo=True)
        return reframed_path

    cut_path = str(work_dir / "cut.mp4")
    clip.cut(input_path, start, end, cut_path)

    reframed_path = str(work_dir / "reframed.mp4")
    reframe.to_vertical(cut_path, reframed_path, is_photo=False)

    if not FIXED_BACKGROUND_TRACK.exists():
        return reframed_path

    final_path = str(work_dir / "final.mp4")
    mix_background(
        reframed_path,
        str(FIXED_BACKGROUND_TRACK),
        final_path,
        has_audio=has_audio_stream(reframed_path),
    )
    return final_path
