from aifun.utils.ffmpeg import run_ffmpeg


def cut(input_path: str, start: float, end: float, output_path: str) -> str:
    """Trim [start, end) seconds of input_path into output_path."""
    run_ffmpeg(
        [
            "-ss", str(start),
            "-i", input_path,
            "-t", str(end - start),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-avoid_negative_ts", "make_zero",
            output_path,
        ]
    )
    return output_path
