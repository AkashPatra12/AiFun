from scenedetect import ContentDetector, detect


def detect_scenes(video_path: str) -> list[tuple[float, float]]:
    """Shot-boundary detection via PySceneDetect's ContentDetector.

    `start_in_scene=True` means a video with no detected cuts (a single
    static shot, or one of our short synthetic test clips) still comes back
    as one scene spanning the whole video, rather than an empty list.
    """
    scenes = detect(str(video_path), ContentDetector(), start_in_scene=True)
    return [(start.seconds, end.seconds) for start, end in scenes]
