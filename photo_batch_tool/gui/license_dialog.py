from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable

from ..licensing import LicenseError, LicenseManager


class LicenseDialog(tk.Toplevel):
    """Shown when the trial/license has expired (blocking, no way to reach
    the main window without a valid key) or opened manually via "Lizenz
    verwalten" to check status or enter a new key at any time."""

    def __init__(self, master: tk.Misc, manager: LicenseManager, on_result: Callable[[bool], None]):
        super().__init__(master)
        self.title("Lizenz")
        self.resizable(False, False)

        self._manager = manager
        self._on_result = on_result
        status = manager.status()
        self._was_licensed = status.licensed

        if status.licensed and not status.trial:
            status_text = f"Lizenziert bis {status.expires_at:%d.%m.%Y}."
        elif status.licensed and status.trial:
            status_text = f"Testphase aktiv, noch {status.days_remaining} Tag(e) (bis {status.expires_at:%d.%m.%Y})."
        else:
            status_text = f"Die Testphase ist abgelaufen ({status.expires_at:%d.%m.%Y})."

        tk.Label(self, text=status_text, font=("Segoe UI", 10, "bold"), wraplength=360, justify="left").pack(
            padx=15, pady=(15, 10)
        )

        prompt = (
            "Bitte gib einen gültigen Lizenzschlüssel ein, um fortzufahren:"
            if not status.licensed
            else "Neuen Lizenzschlüssel eingeben (optional):"
        )
        tk.Label(self, text=prompt, wraplength=360, justify="left").pack(padx=15)

        self._key_var = tk.StringVar()
        tk.Entry(self, textvariable=self._key_var, width=50).pack(padx=15, pady=(5, 10))

        self._error_var = tk.StringVar()
        tk.Label(self, textvariable=self._error_var, fg="#b00020", wraplength=360, justify="left").pack(padx=15)

        button_row = tk.Frame(self)
        button_row.pack(pady=(5, 15))
        tk.Button(button_row, text="Aktivieren", command=self._activate).pack(side="left", padx=5)
        if status.licensed:
            tk.Button(button_row, text="Schließen", command=self._close).pack(side="left", padx=5)
        else:
            tk.Button(button_row, text="Beenden", command=self._quit).pack(side="left", padx=5)

        self.protocol("WM_DELETE_WINDOW", self._close if status.licensed else self._quit)
        self.transient(master)
        self.grab_set()
        self.focus_set()

    def _activate(self) -> None:
        key = self._key_var.get().strip()
        if not key:
            self._error_var.set("Bitte einen Lizenzschlüssel eingeben.")
            return
        try:
            info = self._manager.activate(key)
        except LicenseError as exc:
            self._error_var.set(str(exc))
            return
        messagebox.showinfo("Lizenz aktiviert", f"Lizenz gültig bis {info.expires_at:%d.%m.%Y}.", parent=self)
        self.grab_release()
        self.destroy()
        self._on_result(True)

    def _close(self) -> None:
        self.grab_release()
        self.destroy()
        self._on_result(self._was_licensed)

    def _quit(self) -> None:
        self.grab_release()
        self.destroy()
        self._on_result(False)
