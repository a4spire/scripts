from __future__ import annotations

import io
import shutil
import sys
from pathlib import Path
from typing import Optional

from PIL import Image

from .errors import BackgroundRemovalError, NoObjectDetectedError


def default_model_path() -> Path:
    """Where rembg caches its downloaded U2Net model (~170 MB, fetched on first use).
    Matches rembg's own default: BaseSession.u2net_home() -> "~/.u2net"."""
    return Path.home() / ".u2net" / "u2net.onnx"


def is_model_cached() -> bool:
    return default_model_path().exists()


def _bundled_model_path() -> Optional[Path]:
    """The Windows build (see .github/workflows/build-windows-exe.yml) downloads
    u2net.onnx into models/ before packaging, so PyInstaller ships it inside the
    EXE. Running from source without that download step, there is no bundled
    copy -- rembg then falls back to its normal first-run network download."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent.parent
    candidate = base / "models" / "u2net.onnx"
    return candidate if candidate.is_file() else None


def ensure_model_available() -> None:
    """Copies the bundled model into rembg's expected cache location on first
    use, so end users never need their own internet access for it."""
    if is_model_cached():
        return
    bundled = _bundled_model_path()
    if bundled is None:
        return
    target = default_model_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bundled, target)


def remove_background(path: Path) -> Image.Image:
    """Runs rembg on the given photo and returns an RGBA image with a
    transparent background. Raises BackgroundRemovalError if rembg is
    unavailable or fails, and NoObjectDetectedError if the result is
    fully transparent (no foreground found)."""
    ensure_model_available()

    try:
        from rembg import remove
    except ImportError as exc:
        raise BackgroundRemovalError(
            "Die Bibliothek 'rembg' konnte nicht geladen werden "
            f"({exc}). Falls sie eigentlich installiert ist, könnte ein Teilmodul fehlen "
            "(z.B. beim Bau der EXE) statt rembg komplett zu fehlen. "
            "Bitte 'pip install rembg' ausführen bzw. beim Entwickler die genaue Meldung melden."
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
