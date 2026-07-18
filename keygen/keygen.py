"""Developer-only tool for issuing license keys for the Photo Batch Tool.

Not shipped to customers: this script and its keys/ directory (containing
the private signing key) must stay on the developer's/seller's machine and
must never be committed to version control or bundled into the customer
EXE. Only the PUBLIC key (printed/copied here) belongs in
photo_batch_tool/licensing.py, which is safe to ship since it can only
verify signatures, not create them.
"""
from __future__ import annotations

import base64
import csv
import datetime as dt
import secrets
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from photo_batch_tool.license_format import add_months, format_key_string, pack_payload  # noqa: E402

KEYS_DIR = Path(__file__).resolve().parent / "keys"
PRIVATE_KEY_PATH = KEYS_DIR / "private_key.pem"
ISSUED_LOG_PATH = Path(__file__).resolve().parent / "issued_keys.csv"


def load_or_create_private_key() -> Ed25519PrivateKey:
    if PRIVATE_KEY_PATH.exists():
        return serialization.load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    PRIVATE_KEY_PATH.write_bytes(pem)
    return private_key


def public_key_base64(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def create_license_key(private_key: Ed25519PrivateKey, expires_at: dt.datetime) -> tuple[str, int]:
    key_id = secrets.randbits(32)
    expires_unix = int(expires_at.replace(tzinfo=dt.timezone.utc).timestamp())
    payload = pack_payload(expires_unix, key_id)
    signature = private_key.sign(payload)
    return format_key_string(payload + signature), key_id


def log_issued_key(key_id: int, expires_at: dt.datetime, licensee: str, duration_label: str) -> None:
    is_new = not ISSUED_LOG_PATH.exists()
    with ISSUED_LOG_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["generated_at", "key_id", "expires_at", "licensee", "duration"])
        writer.writerow(
            [dt.datetime.now().isoformat(timespec="seconds"), key_id, expires_at.date().isoformat(), licensee, duration_label]
        )


class KeygenWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Photo Batch Tool – Keygen (nur für Entwickler/Verkäufer)")
        self.resizable(False, False)

        self._private_key = load_or_create_private_key()
        self._build_ui()

    def _build_ui(self) -> None:
        pub_frame = tk.LabelFrame(self, text="Öffentlicher Schlüssel — einmalig in photo_batch_tool/licensing.py eintragen")
        pub_frame.pack(fill="x", padx=10, pady=(10, 5))
        self._public_key_var = tk.StringVar(value=public_key_base64(self._private_key))
        tk.Entry(pub_frame, textvariable=self._public_key_var, width=60, state="readonly").pack(
            side="left", padx=5, pady=5, fill="x", expand=True
        )
        tk.Button(pub_frame, text="Kopieren", command=lambda: self._copy(self._public_key_var.get())).pack(
            side="left", padx=5
        )

        form = tk.LabelFrame(self, text="Neuen Lizenzschlüssel erzeugen")
        form.pack(fill="x", padx=10, pady=5)

        tk.Label(form, text="Gültigkeitsdauer:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self._amount_var = tk.StringVar(value="6")
        tk.Entry(form, textvariable=self._amount_var, width=6).grid(row=0, column=1, sticky="w")
        self._unit_var = tk.StringVar(value="Monate")
        ttk.Combobox(
            form, textvariable=self._unit_var, values=["Tage", "Monate", "Jahre"], width=8, state="readonly"
        ).grid(row=0, column=2, sticky="w", padx=5)

        tk.Label(form, text="Kunde/Referenz (optional, nur lokal protokolliert):").grid(
            row=1, column=0, columnspan=3, sticky="w", padx=5, pady=(8, 0)
        )
        self._licensee_var = tk.StringVar()
        tk.Entry(form, textvariable=self._licensee_var, width=42).grid(
            row=2, column=0, columnspan=3, sticky="we", padx=5, pady=(0, 5)
        )

        tk.Button(form, text="Schlüssel generieren", command=self._generate).grid(
            row=3, column=0, columnspan=3, pady=(0, 5)
        )

        result = tk.LabelFrame(self, text="Erzeugter Lizenzschlüssel")
        result.pack(fill="x", padx=10, pady=5)
        self._result_var = tk.StringVar()
        tk.Entry(result, textvariable=self._result_var, width=52, state="readonly").pack(
            side="left", padx=5, pady=5, fill="x", expand=True
        )
        button_col = tk.Frame(result)
        button_col.pack(side="left", padx=5)
        tk.Button(button_col, text="Kopieren", command=lambda: self._copy(self._result_var.get())).pack(
            pady=2, fill="x"
        )
        tk.Button(button_col, text="Als .lic speichern", command=self._save_to_file).pack(pady=2, fill="x")

        self._expiry_var = tk.StringVar()
        tk.Label(self, textvariable=self._expiry_var, fg="#333333").pack(padx=10, pady=(0, 10))

    def _copy(self, value: str) -> None:
        if not value:
            return
        self.clipboard_clear()
        self.clipboard_append(value)

    def _generate(self) -> None:
        try:
            amount = int(self._amount_var.get())
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ungültige Eingabe", "Bitte eine positive ganze Zahl eingeben.", parent=self)
            return

        now = dt.datetime.now(dt.timezone.utc)
        unit = self._unit_var.get()
        if unit == "Tage":
            expires_at = now + dt.timedelta(days=amount)
        elif unit == "Monate":
            expires_at = add_months(now, amount)
        else:
            expires_at = add_months(now, amount * 12)

        key_str, key_id = create_license_key(self._private_key, expires_at)
        self._result_var.set(key_str)
        self._expiry_var.set(f"Gültig bis {expires_at:%d.%m.%Y} (Key-ID {key_id})")
        log_issued_key(key_id, expires_at, self._licensee_var.get().strip(), f"{amount} {unit}")

    def _save_to_file(self) -> None:
        key_str = self._result_var.get()
        if not key_str:
            messagebox.showinfo("Kein Schlüssel", "Bitte zuerst einen Schlüssel generieren.", parent=self)
            return
        path = filedialog.asksaveasfilename(defaultextension=".lic", filetypes=[("Lizenzdatei", "*.lic")])
        if path:
            Path(path).write_text(key_str, encoding="utf-8")


def main() -> None:
    KeygenWindow().mainloop()


if __name__ == "__main__":
    main()
