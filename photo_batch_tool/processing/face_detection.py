from __future__ import annotations

from typing import List, Optional, Tuple

from PIL import Image

from .circle_crop import max_radius_for_center

FaceBox = Tuple[int, int, int, int]  # x, y, width, height

_CASCADE_FILES = ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml")
_DEFAULT_MARGIN_RATIO = 0.15


def detect_faces(image: Image.Image) -> List[FaceBox]:
    """Best-effort face detection using OpenCV's Haar cascades, which ship
    inside the opencv-python(-headless) package itself -- no model download
    at runtime, unlike rembg's U2Net model.

    This is a soft hint for where to default the crop circle, not a hard
    requirement: on any failure (OpenCV missing, cascade files missing,
    detection error) this returns an empty list rather than raising, and
    callers fall back to centering the circle on the whole image."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []

    try:
        gray = np.array(image.convert("L"))
        boxes: List[FaceBox] = []
        for cascade_file in _CASCADE_FILES:
            cascade = cv2.CascadeClassifier(cv2.data.haarcascades + cascade_file)
            if cascade.empty():
                continue
            detections = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
            boxes.extend((int(x), int(y), int(w), int(h)) for x, y, w, h in detections)
        return boxes
    except Exception:
        return []


def compute_default_circle(
    image_size: Tuple[int, int],
    faces: List[FaceBox],
    margin_ratio: float = _DEFAULT_MARGIN_RATIO,
) -> Tuple[Tuple[float, float], float]:
    """Proposes a starting circle: centered on all detected faces with a
    radius that encloses them plus a small margin. Falls back to the
    previous default (image center, quarter of the shorter side) when no
    faces were found."""
    width, height = image_size

    if not faces:
        return (width / 2, height / 2), min(width, height) / 4

    left = min(x for x, y, w, h in faces)
    top = min(y for x, y, w, h in faces)
    right = max(x + w for x, y, w, h in faces)
    bottom = max(y + h for x, y, w, h in faces)

    center = ((left + right) / 2, (top + bottom) / 2)
    half_diagonal = ((right - left) ** 2 + (bottom - top) ** 2) ** 0.5 / 2
    radius = half_diagonal * (1 + margin_ratio)

    radius = min(radius, max_radius_for_center(image_size, center))
    return center, radius
