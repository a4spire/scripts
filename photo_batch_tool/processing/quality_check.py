from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageStat

from .face_detection import FaceBox, detect_faces

_EYE_CASCADE_FILE = "haarcascade_eye.xml"


@dataclass
class QualityAssessment:
    is_blurry: bool
    blur_score: float
    is_too_dark: bool
    is_too_bright: bool
    brightness: float
    no_face_detected: bool
    eyes_closed_suspected: bool

    @property
    def is_low_quality(self) -> bool:
        return (
            self.is_blurry
            or self.is_too_dark
            or self.is_too_bright
            or self.no_face_detected
            or self.eyes_closed_suspected
        )

    @property
    def reasons(self) -> List[str]:
        reasons = []
        if self.is_blurry:
            reasons.append("Verschwommen")
        if self.is_too_dark:
            reasons.append("Unterbelichtet")
        if self.is_too_bright:
            reasons.append("Überbelichtet")
        if self.no_face_detected:
            reasons.append("Kein Gesicht erkannt")
        elif self.eyes_closed_suspected:
            reasons.append("Augen evtl. geschlossen")
        return reasons


def _blur_score(gray_image: Image.Image) -> float:
    """Variance of the Laplacian: a low-cost, well-established blur metric
    (sharp edges produce a high-variance Laplacian; blurry images don't).
    Returns +inf (never flagged as blurry) if OpenCV is unavailable or the
    computation fails -- this is a soft hint, not a hard requirement."""
    try:
        import cv2
        import numpy as np

        return float(cv2.Laplacian(np.array(gray_image), cv2.CV_64F).var())
    except Exception:
        return float("inf")


def _mean_brightness(gray_image: Image.Image) -> float:
    return ImageStat.Stat(gray_image).mean[0]


def _any_face_has_open_eyes(gray_image: Image.Image, faces: List[FaceBox]) -> bool:
    """Heuristic: runs OpenCV's eye cascade over the upper ~60% of each
    detected face (where eyes normally sit). If at least one face shows
    detected eyes, we assume eyes are open somewhere in the photo. This can
    miss open eyes too (side angles, glasses, poor lighting), so it is only
    ever used as a soft warning, never to silently discard a photo outright."""
    try:
        import cv2
        import numpy as np

        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + _EYE_CASCADE_FILE)
        if cascade.empty():
            return True

        gray = np.array(gray_image)
        for x, y, w, h in faces:
            roi_bottom = y + int(h * 0.6)
            roi = gray[max(y, 0):max(roi_bottom, 0), max(x, 0):max(x + w, 0)]
            if roi.size == 0:
                continue
            eyes = cascade.detectMultiScale(roi, scaleFactor=1.1, minNeighbors=5, minSize=(15, 15))
            if len(eyes) > 0:
                return True
        return False
    except Exception:
        return True


def assess_quality(
    image: Image.Image,
    faces: Optional[List[FaceBox]] = None,
    blur_threshold: float = 100.0,
    min_brightness: float = 40.0,
    max_brightness: float = 220.0,
) -> QualityAssessment:
    """Best-effort photo quality check: blur, exposure, and (if a face is
    visible) a heuristic guess at closed eyes. Every sub-check fails open
    (assumes "fine") on any error, so a detection hiccup never blocks the
    workflow -- this only ever informs a warning or an optional auto-sort,
    the user can always override it."""
    if faces is None:
        faces = detect_faces(image)

    gray_image = image.convert("L")

    blur_score = _blur_score(gray_image)
    brightness = _mean_brightness(gray_image)
    no_face_detected = not faces
    eyes_closed_suspected = bool(faces) and not _any_face_has_open_eyes(gray_image, faces)

    return QualityAssessment(
        is_blurry=blur_score < blur_threshold,
        blur_score=blur_score,
        is_too_dark=brightness < min_brightness,
        is_too_bright=brightness > max_brightness,
        brightness=brightness,
        no_face_detected=no_face_detected,
        eyes_closed_suspected=eyes_closed_suspected,
    )


def _safe_open_image(path: Path) -> Optional[Image.Image]:
    try:
        with Image.open(path) as image:
            return image.convert("RGB")
    except Exception:
        return None


def split_by_quality(
    photos: List[Path],
    enable_quality_filter: bool,
    quality_action: str,
    blur_threshold: float = 100.0,
    min_brightness: float = 40.0,
    max_brightness: float = 220.0,
) -> Tuple[List[Path], List[Path], Dict[Path, QualityAssessment]]:
    """Assesses every photo and, in "auto_move" mode, splits them into
    (selectable, excluded). Excluded stays empty unless quality filtering is
    enabled, the action is "auto_move", at least one photo is flagged, and
    not every photo is flagged -- a series that is entirely flagged always
    stays fully selectable, so the user is never left with zero candidates.
    This is the single source of truth for the split, shared by the series
    selector dialog and by the auto-confirm check in the main window."""
    assessments: Dict[Path, QualityAssessment] = {}
    if enable_quality_filter:
        for photo in photos:
            image = _safe_open_image(photo)
            if image is not None:
                assessments[photo] = assess_quality(
                    image,
                    blur_threshold=blur_threshold,
                    min_brightness=min_brightness,
                    max_brightness=max_brightness,
                )

    low_quality = {p for p, a in assessments.items() if a.is_low_quality}

    if (
        enable_quality_filter
        and quality_action == "auto_move"
        and low_quality
        and low_quality != set(photos)
    ):
        selectable = [p for p in photos if p not in low_quality]
        excluded = [p for p in photos if p in low_quality]
    else:
        selectable = list(photos)
        excluded = []

    return selectable, excluded, assessments
