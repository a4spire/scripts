from __future__ import annotations

import hashlib
import io
import os
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Optional

from PIL import Image

from .errors import BackgroundRemovalError, NoObjectDetectedError

# Verified directly from the installed rembg source (U2netSession.download_models(),
# BaseSession.u2net_home()) -- not guessed.
_MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx"
_MODEL_MD5 = "60024c5c889badc19c04ad937298a77b"
_DOWNLOAD_TIMEOUT_SECONDS = 20
_DOWNLOAD_MAX_ATTEMPTS = 3
_DOWNLOAD_RETRY_DELAY_SECONDS = 3


def default_model_path() -> Path:
    """Where rembg caches its downloaded U2Net model (~170 MB, fetched on first use).
    Matches rembg's own default: BaseSession.u2net_home() -> "~/.u2net"."""
    return Path.home() / ".u2net" / "u2net.onnx"


def is_model_cached() -> bool:
    return default_model_path().exists()


def _md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_model_once(target: Path) -> None:
    """Downloads to a temp file in the same directory first and only moves
    it to the real target path (an atomic rename on the same filesystem)
    once the checksum has been verified. A crash, timeout, or kill signal
    mid-download can therefore never leave a corrupted/partial file at the
    path rembg expects -- only the .part file is affected, and that is
    always cleaned up."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix="u2net_", suffix=".part")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            with urllib.request.urlopen(_MODEL_URL, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    tmp_file.write(chunk)

        if _md5sum(tmp_path) != _MODEL_MD5:
            raise BackgroundRemovalError("Heruntergeladenes Modell hat eine falsche Prüfsumme.")

        tmp_path.replace(target)
    finally:
        tmp_path.unlink(missing_ok=True)


def ensure_model_available() -> None:
    """Ensures rembg's U2Net model is present at its expected cache path.

    We download it ourselves instead of relying solely on rembg's internal
    downloader: that one has no timeout and can hang indefinitely if a
    firewall silently drops the connection instead of refusing it. Our own
    attempts are bounded (20s each, up to 3 tries), so a genuine network
    problem surfaces as a clear error within about a minute instead of
    looking like a frozen app."""
    if is_model_cached():
        return

    target = default_model_path()
    last_error: Optional[Exception] = None
    for attempt in range(1, _DOWNLOAD_MAX_ATTEMPTS + 1):
        try:
            _download_model_once(target)
            return
        except Exception as exc:
            last_error = exc
            if attempt < _DOWNLOAD_MAX_ATTEMPTS:
                time.sleep(_DOWNLOAD_RETRY_DELAY_SECONDS)

    raise BackgroundRemovalError(
        f"Das rembg-KI-Modell konnte nach {_DOWNLOAD_MAX_ATTEMPTS} Versuchen nicht "
        f"heruntergeladen werden ({last_error}). Bitte Internetverbindung/Firewall prüfen "
        f"oder die Datei manuell nach {target} kopieren (siehe README, Abschnitt "
        "'Fehlerbehebung: Hintergrundentfernung hängt / reagiert nicht')."
    )


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
