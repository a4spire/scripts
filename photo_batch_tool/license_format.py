from __future__ import annotations

import base64
import calendar
import datetime as dt
import struct

VERSION = 1

# version(1 byte) + expires_unix(4 bytes, uint32) + key_id(4 bytes, uint32)
STRUCT_FORMAT = ">BII"
PAYLOAD_SIZE = struct.calcsize(STRUCT_FORMAT)
SIGNATURE_SIZE = 64  # Ed25519 signature length
TOTAL_SIZE = PAYLOAD_SIZE + SIGNATURE_SIZE

GROUP_SIZE = 5


def pack_payload(expires_unix: int, key_id: int) -> bytes:
    return struct.pack(STRUCT_FORMAT, VERSION, expires_unix, key_id)


def unpack_payload(data: bytes) -> tuple[int, int, int]:
    return struct.unpack(STRUCT_FORMAT, data)


def format_key_string(raw: bytes) -> str:
    """Base32-encodes raw key bytes and groups them as XXXXX-XXXXX-... for readability."""
    b32 = base64.b32encode(raw).decode("ascii").rstrip("=")
    return "-".join(b32[i:i + GROUP_SIZE] for i in range(0, len(b32), GROUP_SIZE))


def parse_key_string(key_str: str) -> bytes:
    cleaned = key_str.strip().replace("-", "").replace(" ", "").upper()
    padding = "=" * ((8 - len(cleaned) % 8) % 8)
    return base64.b32decode(cleaned + padding)


def add_months(value: dt.datetime, months: int) -> dt.datetime:
    """Calendar-correct month addition (e.g. 31 Jan + 1 month -> 28/29 Feb)."""
    total = value.month - 1 + months
    year = value.year + total // 12
    month = total % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)
