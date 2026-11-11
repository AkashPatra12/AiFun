from aifun.utils.ffmpeg import run_ffmpeg

# Keeps the fixed background track underneath the clip's own audio rather
# than drowning it out.
BACKGROUND_VOLUME = 0.2


def mix_background(
    input_path: str, background_path: str, output_path: str, *, has_audio: bool
) -> str:
    """Lay `background_path` underneath input_path's own audio track, or —
    for a clip with no audio stream of its own (e.g. a silent source video)
    — use it as the sole audio.

    The background is looped to cover clips longer than the track itself;
    `-shortest` then trims the mix back down to the (shorter) video length.
    """
    if has_audio:
        filter_complex = (
            f"[1:a]volume={BACKGROUND_VOLUME}[bg];"
            "[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        args = [
            "-i", input_path,
            "-stream_loop", "-1",
            "-i", background_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_path,
        ]
    else:
        args = [
            "-i", input_path,
            "-stream_loop", "-1",
            "-i", background_path,
            "-map", "0:v",
            "-map", "1:a",
            "-af", f"volume={BACKGROUND_VOLUME}",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_path,
        ]
    run_ffmpeg(args)
    return output_path


def normalize(segment):
    # Deferred to Phase 4 (docs/README.md) — audio normalize alongside
    # caption burn-in, once real (non-fixture) clips exist to normalize.
    raise NotImplementedError
