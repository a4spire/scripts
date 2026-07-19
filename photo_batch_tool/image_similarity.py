from __future__ import annotations

from pathlib import Path

from PIL import Image

_HASH_SIZE = 8  # -> 64-bit hash


def compute_hash(path: Path) -> int:
    """Difference hash (dHash): a perceptual fingerprint for 'is this
    visually the same shot' comparisons. Minor JPEG compression, exposure
    or framing differences barely move the hash; a genuinely different
    photo differs in many bits."""
    with Image.open(path) as image:
        resized = image.convert("L").resize((_HASH_SIZE + 1, _HASH_SIZE), Image.LANCZOS)
        pixels = list(resized.getdata())

    bits = 0
    for row in range(_HASH_SIZE):
        offset = row * (_HASH_SIZE + 1)
        for col in range(_HASH_SIZE):
            bits <<= 1
            if pixels[offset + col] > pixels[offset + col + 1]:
                bits |= 1
    return bits


def hamming_distance(hash_a: int, hash_b: int) -> int:
    return bin(hash_a ^ hash_b).count("1")
