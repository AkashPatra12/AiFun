import cv2

# Aesthetic/quality scoring for photo-mode reels — docs/README.md feature #4.
# Heuristic MVP (sharpness/exposure/face-presence), not a trained model.

_face_cascade: cv2.CascadeClassifier | None = None


def _get_face_cascade() -> cv2.CascadeClassifier:
    global _face_cascade
    if _face_cascade is None:
        _face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    return _face_cascade


def score_photo(image_path: str) -> dict:
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Laplacian variance: a sharp, in-focus image has more high-frequency
    # edge content than a blurry one.
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    sharpness_score = min(sharpness / 500.0, 1.0)  # 500 picked empirically

    # Mean brightness: 127.5 (mid-gray) is "well exposed", falling off
    # toward either under- or over-exposed.
    exposure = float(gray.mean())
    exposure_score = 1.0 - abs(exposure - 127.5) / 127.5

    faces = _get_face_cascade().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
    has_face = len(faces) > 0

    overall = 0.4 * sharpness_score + 0.3 * exposure_score + 0.3 * (1.0 if has_face else 0.0)

    return {
        "sharpness": round(float(sharpness), 2),
        "exposure": round(exposure, 2),
        "hasFace": has_face,
        "score": round(overall, 4),
    }
