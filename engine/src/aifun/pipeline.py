from aifun.analysis import find_highlights
from aifun.editing import audio, captions, clip, reframe
from aifun.export import export_clip
from aifun.ingest import load_video
from aifun.render import render_clip
from aifun.transcribe import transcribe_video


def run_pipeline(input_path: str, output_dir: str) -> list[str]:
    video = load_video(input_path)
    transcript = transcribe_video(video)
    highlights = find_highlights(transcript)

    output_paths = []
    for highlight in highlights:
        segment = clip.cut(video, highlight)
        segment = reframe.to_vertical(segment)
        segment = captions.burn_in(segment, transcript, highlight)
        segment = audio.normalize(segment)
        rendered = render_clip(segment)
        output_paths.append(export_clip(rendered, output_dir))

    return output_paths
