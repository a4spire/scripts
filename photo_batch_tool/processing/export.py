from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

MM_PER_INCH = 25.4


def compute_pixel_size(target_mm: float, dpi: int) -> int:
    return max(1, round(target_mm / MM_PER_INCH * dpi))


def _sanitize(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_\-]+", "_", name.strip())
    return name.strip("_")


def build_filename(series_id: str, customer_name: str = "") -> str:
    parts = [series_id]
    customer = _sanitize(customer_name)
    if customer:
        parts.append(customer)
    return "_".join(parts) + ".png"


def scale_and_export(
    image: Image.Image,
    dpi: int,
    target_mm: float,
    output_folder: Path,
    series_id: str,
    customer_name: str = "",
) -> Path:
    """Resizes the circular cutout to exactly `target_mm` x `target_mm` at
    `dpi` and saves it as PNG with physical-size (DPI) metadata."""
    size_px = compute_pixel_size(target_mm, dpi)
    resized = image.resize((size_px, size_px), Image.LANCZOS)

    output_folder.mkdir(parents=True, exist_ok=True)
    out_path = output_folder / build_filename(series_id, customer_name)
    resized.save(out_path, format="PNG", dpi=(dpi, dpi))
    return out_path
