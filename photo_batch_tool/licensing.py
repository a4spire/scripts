from __future__ import annotations

import base64
import datetime as dt
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .license_format import PAYLOAD_SIZE, TOTAL_SIZE, add_months, parse_key_string, unpack_payload

# Public half of the license signing keypair. Safe to ship/commit: it can only
# VERIFY signatures produced by the matching private key, never create new
# ones. The private key lives only on the developer's machine (see keygen/).
PUBLIC_KEY_B64 = "9xd4Zss99tuObv89VlyUA5AUzfBiV80cM6VmpBK2qQ0="

TRIAL_MONTHS = 6
_STATE_FILENAME = "license.json"
_REGISTRY_KEY_PATH = r"Software\PhotoBatchTool"
_REGISTRY_VALUE_NAME = "InstallDate"


class LicenseError(Exception):
    pass


class LicenseFormatError(LicenseError):
    pass


class LicenseSignatureError(LicenseError):
    pass


class LicenseExpiredError(LicenseError):
    pass


@dataclass
class LicenseInfo:
    expires_at: dt.datetime
    key_id: int


@dataclass
class LicenseStatus:
    licensed: bool
    trial: bool
    expires_at: dt.datetime
    days_remaining: int


def _public_key() -> Ed25519PublicKey:
    raw = base64.b64decode(PUBLIC_KEY_B64)
    return Ed25519PublicKey.from_public_bytes(raw)


def verify_license_key(key_str: str) -> LicenseInfo:
    """Parses and cryptographically verifies a license key string.
    Raises LicenseFormatError / LicenseSignatureError on invalid input."""
    try:
        raw = parse_key_string(key_str)
    except Exception as exc:
        raise LicenseFormatError("Der Lizenzschlüssel hat ein ungültiges Format.") from exc

    if len(raw) != TOTAL_SIZE:
        raise LicenseFormatError("Der Lizenzschlüssel hat eine ungültige Länge.")

    payload, signature = raw[:PAYLOAD_SIZE], raw[PAYLOAD_SIZE:]

    try:
        _public_key().verify(signature, payload)
    except InvalidSignature as exc:
        raise LicenseSignatureError("Der Lizenzschlüssel ist ungültig (Signatur stimmt nicht überein).") from exc

    _version, expires_unix, key_id = unpack_payload(payload)
    expires_at = dt.datetime.fromtimestamp(expires_unix, tz=dt.timezone.utc)
    return LicenseInfo(expires_at=expires_at, key_id=key_id)


def _read_state(config_dir: Path) -> dict:
    path = config_dir / _STATE_FILENAME
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _write_state(config_dir: Path, state: dict) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / _STATE_FILENAME).write_text(json.dumps(state, indent=2), encoding="utf-8")


def _registry_install_date() -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REGISTRY_KEY_PATH) as key:
            value, _ = winreg.QueryValueEx(key, _REGISTRY_VALUE_NAME)
            return value
    except OSError:
        return None


def _write_registry_install_date(value: str) -> None:
    if os.name != "nt":
        return
    try:
        import winreg
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REGISTRY_KEY_PATH)
        winreg.SetValueEx(key, _REGISTRY_VALUE_NAME, 0, winreg.REG_SZ, value)
        winreg.CloseKey(key)
    except OSError:
        pass


def _resolve_install_date(state: dict) -> dt.datetime:
    """Determines the true first-run date. Checks both the config-file state
    and (on Windows) the registry, and keeps the EARLIEST of whatever is
    found, so deleting just one of the two stores cannot restart the trial.
    This is a reasonable deterrent for a small desktop tool, not a hard
    tamper-proofing guarantee."""
    candidates = []
    file_value = state.get("install_date")
    if file_value:
        candidates.append(file_value)
    reg_value = _registry_install_date()
    if reg_value:
        candidates.append(reg_value)

    if candidates:
        earliest = min(dt.datetime.fromisoformat(v) for v in candidates)
    else:
        earliest = dt.datetime.now(dt.timezone.utc)

    iso = earliest.isoformat()
    state["install_date"] = iso
    _write_registry_install_date(iso)
    return earliest


class LicenseManager:
    def __init__(self, config_dir: Path):
        self._config_dir = config_dir
        self._state = _read_state(config_dir)
        self._install_date = _resolve_install_date(self._state)
        _write_state(config_dir, self._state)

    def activate(self, key_str: str) -> LicenseInfo:
        info = verify_license_key(key_str)
        if info.expires_at < dt.datetime.now(dt.timezone.utc):
            raise LicenseExpiredError(
                f"Dieser Lizenzschlüssel ist bereits abgelaufen ({info.expires_at:%d.%m.%Y})."
            )
        self._state["license_key"] = key_str
        _write_state(self._config_dir, self._state)
        return info

    def status(self) -> LicenseStatus:
        now = dt.datetime.now(dt.timezone.utc)

        key_str = self._state.get("license_key")
        if key_str:
            try:
                info = verify_license_key(key_str)
            except LicenseError:
                info = None  # invalid/corrupted key: fall back to trial status
            if info is not None:
                days_remaining = max((info.expires_at - now).days, 0)
                return LicenseStatus(
                    licensed=info.expires_at >= now,
                    trial=False,
                    expires_at=info.expires_at,
                    days_remaining=days_remaining,
                )

        trial_expires = add_months(self._install_date, TRIAL_MONTHS)
        days_remaining = max((trial_expires - now).days, 0)
        return LicenseStatus(
            licensed=trial_expires >= now,
            trial=True,
            expires_at=trial_expires,
            days_remaining=days_remaining,
        )
