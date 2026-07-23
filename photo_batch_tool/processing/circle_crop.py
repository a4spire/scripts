from __future__ import annotations

from typing import Tuple

from PIL import Image, ImageDraw

from .errors import InvalidRadiusError


def max_radius_for_center(image_size: Tuple[int, int], center: Tuple[float, float]) -> float:
    """Largest radius that keeps the circle fully inside the image for a given center."""
    width, height = image_size
    cx, cy = center
    return max(1.0, min(cx, cy, width - cx, height - cy))


def apply_circular_crop(image: Image.Image, center: Tuple[float, float], radius: float) -> Image.Image:
    """Crops `image` to a circle of `radius` around `center`. Everything outside
    the circle becomes transparent. Raises InvalidRadiusError if the circle
    would extend beyond the image bounds."""
    if radius <= 0:
        raise InvalidRadiusError("Der Radius muss größer als 0 sein.")

    cx, cy = center
    left, top = cx - radius, cy - radius
    right, bottom = cx + radius, cy + radius

    if left < -0.01 or top < -0.01 or right > image.width + 0.01 or bottom > image.height + 0.01:
        raise InvalidRadiusError(
            "Der gewählte Kreis liegt außerhalb des Bildes. Bitte Radius verkleinern oder Position anpassen."
        )

    left, top = max(left, 0), max(top, 0)
    right, bottom = min(right, image.width), min(bottom, image.height)

    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((left, top, right, bottom), fill=255)

    rgba = image.convert("RGBA")
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.paste(rgba, (0, 0), mask)

    return result.crop((int(left), int(top), int(right), int(bottom)))
