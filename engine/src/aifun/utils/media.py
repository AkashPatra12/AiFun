import json
import subprocess
import uuid
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[3]
DATA_INPUT_DIR = ENGINE_ROOT / "data" / "input"


def save_upload(media_id: uuid.UUID, ext: str, data: bytes) -> Path:
    DATA_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_INPUT_DIR / f"{media_id}.{ext}"
    path.write_bytes(data)
    return path


def probe_metadata(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr.strip()}")

    info = json.loads(result.stdout)

    duration = info.get("format", {}).get("duration")
    duration_seconds = float(duration) if duration is not None else None

    width = height = None
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            width = stream.get("width")
            height = stream.get("height")
            break

    return {
        "duration_seconds": duration_seconds,
        "width": width,
        "height": height,
    }
