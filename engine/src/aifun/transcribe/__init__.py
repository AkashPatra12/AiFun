import os

# Some local Python installs (notably python.org's macOS builds) ship
# without the OS trust store wired into the default SSL context, so
# whisper's model-weight download (plain urllib, no certifi of its own)
# fails with CERTIFICATE_VERIFY_FAILED even though the network is fine.
# Point the default context at certifi's bundle before whisper ever needs
# it — this is what `pip`/`requests` already do internally, whisper just
# doesn't. `setdefault` so an operator-provided SSL_CERT_FILE always wins.
import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from dataclasses import asdict, dataclass

import whisper

from aifun.utils.media import ENGINE_ROOT, has_audio_stream

# Tech-stack choice per docs/README.md: "openai-whisper (local, tiny/base
# model, CPU-friendly)" — NOT engine/config/settings.yaml's
# `transcribe.model: whisper-large-v3`, which is a multi-GB model that
# contradicts the doc's own "$0/CPU-friendly" framing. See
# docs/phase1-data-ingestion.md's Phase 3 notes.
DEFAULT_MODEL_SIZE = "tiny"
WHISPER_CACHE_DIR = ENGINE_ROOT / "data" / "cache" / "whisper"

_model_cache: dict[str, "whisper.Whisper"] = {}


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


def _load_model(model_size: str):
    if model_size not in _model_cache:
        WHISPER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _model_cache[model_size] = whisper.load_model(
            model_size, download_root=str(WHISPER_CACHE_DIR)
        )
    return _model_cache[model_size]


def transcribe_video(
    video_path: str, model_size: str = DEFAULT_MODEL_SIZE
) -> list[TranscriptSegment]:
    """Local Whisper transcription. Returns segment-level timestamps + text;
    a video with no audio stream at all (e.g. a screen recording, or one of
    our own silent synthetic test clips) returns [] rather than raising —
    whisper's own ffmpeg-based audio extraction errors on that input.
    """
    if not has_audio_stream(video_path):
        return []

    model = _load_model(model_size)
    result = model.transcribe(str(video_path), fp16=False)
    return [
        TranscriptSegment(
            start=segment["start"], end=segment["end"], text=segment["text"].strip()
        )
        for segment in result["segments"]
    ]


def transcript_to_json(transcript: list[TranscriptSegment]) -> list[dict]:
    return [asdict(segment) for segment in transcript]
