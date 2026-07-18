from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from .errors import BackgroundRemovalError, NoObjectDetectedError


def default_model_path() -> Path:
    """Where rembg caches its downloaded U2Net model (~170 MB, fetched on first use)."""
    return Path.home() / ".u2net" / "u2net.onnx"


def is_model_cached() -> bool:
    return default_model_path().exists()


def remove_background(path: Path) -> Image.Image:
    """Runs rembg on the given photo and returns an RGBA image with a
    transparent background. Raises BackgroundRemovalError if rembg is
    unavailable or fails, and NoObjectDetectedError if the result is
    fully transparent (no foreground found)."""
    try:
        from rembg import remove
    except ImportError as exc:
        raise BackgroundRemovalError(
            "Die Bibliothek 'rembg' ist nicht installiert. Bitte 'pip install rembg' ausführen."
        ) from exc

    try:
        input_bytes = path.read_bytes()
    except OSError as exc:
        raise BackgroundRemovalError(f"Foto konnte nicht gelesen werden: {exc}") from exc

    try:
        output_bytes = remove(input_bytes)
    except Exception as exc:
        raise BackgroundRemovalError(f"Hintergrundentfernung fehlgeschlagen: {exc}") from exc

    try:
        image = Image.open(io.BytesIO(output_bytes)).convert("RGBA")
    except Exception as exc:
        raise BackgroundRemovalError(f"Ergebnis der Hintergrundentfernung ist ungültig: {exc}") from exc

    alpha = image.getchannel("A")
    if alpha.getextrema()[1] == 0:
        raise NoObjectDetectedError(
            "Es wurde kein Objekt im Bild erkannt (Ergebnis ist vollständig transparent)."
        )

    return image
