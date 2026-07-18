from __future__ import annotations

import datetime as dt
from pathlib import Path

from PIL import ExifTags, Image

_EXIF_FORMAT = "%Y:%m:%d %H:%M:%S"

_TAG_DATETIME = 306  # DateTime (IFD0)
_TAG_DATETIME_ORIGINAL = 36867  # DateTimeOriginal (Exif IFD)
_TAG_DATETIME_DIGITIZED = 36868  # DateTimeDigitized (Exif IFD)


def get_photo_timestamp(path: Path) -> dt.datetime:
    """Best-effort EXIF capture timestamp, falling back to the file's mtime."""
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            candidates = []

            try:
                exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            except Exception:
                exif_ifd = {}

            for tag_id in (_TAG_DATETIME_ORIGINAL, _TAG_DATETIME_DIGITIZED):
                value = exif_ifd.get(tag_id)
                if value:
                    candidates.append(value)

            value = exif.get(_TAG_DATETIME)
            if value:
                candidates.append(value)

            for value in candidates:
                try:
                    return dt.datetime.strptime(value, _EXIF_FORMAT)
                except ValueError:
                    continue
    except Exception:
        pass

    return dt.datetime.fromtimestamp(path.stat().st_mtime)
