from aifun.utils.ffmpeg import run_ffmpeg

# Matches pipeline.target_aspect_ratio (9:16) in engine/config/settings.yaml.
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920


def to_vertical(input_path: str, output_path: str, *, is_photo: bool = False) -> str:
    """Scale-to-cover + center-crop to a 9:16 vertical frame."""
    vf = (
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}"
    )
    args = ["-i", input_path, "-vf", vf]
    if is_photo:
        args += ["-frames:v", "1"]
    else:
        args += ["-c:v", "libx264", "-c:a", "copy"]
    args.append(output_path)
    run_ffmpeg(args)
    return output_path
