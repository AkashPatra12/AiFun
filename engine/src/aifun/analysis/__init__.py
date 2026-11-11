from aifun.analysis.motion import detect_face_presence, score_motion
from aifun.analysis.scenes import detect_scenes
from aifun.transcribe import TranscriptSegment
from aifun.utils.settings import load_settings


def _transcript_density(
    transcript: list[TranscriptSegment], start: float, end: float
) -> float:
    """Words spoken per second within [start, end], normalized to ~0-1
    (2.5 words/sec, fast confident speech, is treated as the ceiling).
    """
    words = 0.0
    for segment in transcript:
        overlap = min(segment.end, end) - max(segment.start, start)
        if overlap > 0:
            segment_duration = max(segment.end - segment.start, 0.01)
            words += len(segment.text.split()) * overlap / segment_duration

    duration = max(end - start, 0.01)
    return min((words / duration) / 2.5, 1.0)


def _candidate_windows(
    scene_start: float, scene_end: float, window_length: float
) -> list[tuple[float, float]]:
    """Sub-windows of `window_length` sliding through [scene_start,
    scene_end], 50%-overlapping. A scene no longer than one window just
    comes back as itself.

    Without this, PySceneDetect's ContentDetector — which only fires on
    hard cuts — hands back exactly one "scene" spanning the *entire* video
    for any continuous single-shot recording (no internal cuts to find),
    and the old code took that whole scene as the one candidate verbatim.
    For a 30s continuous phone clip, that's "highlight selection" that
    just returns the whole video, reframed — not a real sub-clip pick. See
    docs/progress.md and the bug report that prompted this.
    """
    if scene_end - scene_start <= window_length:
        return [(scene_start, scene_end)]

    stride = window_length / 2
    windows = []
    window_start = scene_start
    while window_start < scene_end:
        window_end = min(window_start + window_length, scene_end)
        windows.append((window_start, window_end))
        if window_end >= scene_end:
            break
        window_start += stride
    return windows


def find_highlights(
    media_id: str,
    video_path: str,
    transcript: list[TranscriptSegment],
    duration_seconds: float | None,
) -> list[dict]:
    """Scene + transcript highlight scoring (docs/README.md feature #3):
    detect shot boundaries, slide candidate windows through each one, score
    every window for motion/faces/speech density, and return the
    top-scoring ones matching contracts/highlight.schema.json.

    This is an MVP heuristic, not a trained/LLM model — see
    docs/progress.md for what real scoring would need.
    """
    settings = load_settings()["pipeline"]
    min_duration, max_duration = settings["target_duration_seconds"]
    max_clips = settings["max_clips_per_video"]
    # The shortest allowed clip length doubles as the sliding-window size —
    # picking a tight, focused sub-clip fits "highlight" better than
    # defaulting to the longest allowed one.
    window_length = min_duration

    candidates = []
    for scene_start, scene_end in detect_scenes(video_path):
        for start, end in _candidate_windows(scene_start, scene_end, window_length):
            if end - start < min(min_duration, 3.0):
                continue  # a trailing sliver at the end of a scene

            motion = score_motion(video_path, start, end)
            has_face = detect_face_presence(video_path, start, end)
            speech = _transcript_density(transcript, start, end)
            score = 0.4 * motion + 0.3 * (1.0 if has_face else 0.0) + 0.3 * speech

            reason = [f"motion={motion:.2f}"]
            if has_face:
                reason.append("face detected")
            if speech > 0:
                reason.append(f"speech_density={speech:.2f}")

            candidates.append(
                {
                    "sourceMediaId": media_id,
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "score": round(min(score, 1.0), 4),
                    "reason": ", ".join(reason),
                }
            )

    if not candidates and duration_seconds:
        # Every scene was shorter than the minimum (e.g. a very short or
        # single-frame-ish source) — fall back to one highlight covering
        # what there is, rather than returning nothing.
        candidates.append(
            {
                "sourceMediaId": media_id,
                "start": 0.0,
                "end": min(duration_seconds, max_duration),
                "score": 0.0,
                "reason": "fallback: no scene met the minimum clip duration",
            }
        )

    candidates.sort(key=lambda h: h["score"], reverse=True)
    return candidates[:max_clips]
