import cv2

_face_cascade: cv2.CascadeClassifier | None = None


def _get_face_cascade() -> cv2.CascadeClassifier:
    global _face_cascade
    if _face_cascade is None:
        _face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    return _face_cascade


def _evenly_spaced_frame_indices(start_frame: int, end_frame: int, count: int) -> list[int]:
    span = max(end_frame - start_frame, 1)
    step = max(span // count, 1)
    return list(range(start_frame, end_frame, step))[:count]


def _sample_frames(video_path: str, start: float, end: float, max_samples: int):
    cap = cv2.VideoCapture(str(video_path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        start_frame = int(start * fps)
        end_frame = max(int(end * fps), start_frame + 1)

        frames = []
        for idx in _evenly_spaced_frame_indices(start_frame, end_frame, max_samples):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if ok:
                frames.append(frame)
        return frames
    finally:
        cap.release()


def score_motion(video_path: str, start: float, end: float) -> float:
    """Mean frame-to-frame pixel difference across sampled frames in
    [start, end], normalized to ~0-1. A crude motion proxy (no optical
    flow) — enough to rank scenes by "how much is changing" for the Phase 3
    MVP; see docs/README.md feature #3.
    """
    frames = _sample_frames(video_path, start, end, max_samples=6)
    if len(frames) < 2:
        return 0.0

    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    diffs = [cv2.absdiff(a, b).mean() for a, b in zip(grays, grays[1:])]
    mean_diff = sum(diffs) / len(diffs)
    return min(mean_diff / 40.0, 1.0)  # 40 picked empirically as "a lot of motion"


def detect_face_presence(video_path: str, start: float, end: float) -> bool:
    """True if a face is detected in any sampled frame in [start, end]."""
    cascade = _get_face_cascade()
    for frame in _sample_frames(video_path, start, end, max_samples=3):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        if len(faces) > 0:
            return True
    return False
