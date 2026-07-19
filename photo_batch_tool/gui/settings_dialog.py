from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable

from ..config import Config


class SettingsDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, config: Config, on_save: Callable[[Config], None]):
        super().__init__(master)
        self.title("Einstellungen")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self._config = config
        self._on_save = on_save

        self._watch_var = tk.StringVar(value=config.watch_folder)
        self._output_var = tk.StringVar(value=config.output_folder)
        self._done_var = tk.StringVar(value=config.done_folder)
        self._window_var = tk.StringVar(value=str(config.time_window_seconds))
        self._dpi_var = tk.StringVar(value=str(config.target_dpi))
        self._size_var = tk.StringVar(value=str(config.target_size_mm))
        self._auto_var = tk.BooleanVar(value=config.auto_accept_single)
        self._similarity_enabled_var = tk.BooleanVar(value=config.enable_similarity_grouping)
        self._similarity_threshold_var = tk.StringVar(value=str(config.similarity_hamming_threshold))
        self._similarity_extra_var = tk.StringVar(value=str(config.similarity_max_extra_seconds))

        self._add_folder_row("Überwachungsordner", self._watch_var, 0)
        self._add_folder_row("Ausgabeordner", self._output_var, 1)
        self._add_folder_row("Erledigt-Ordner", self._done_var, 2)

        tk.Label(self, text="Zeitfenster Serienerkennung (Sekunden)").grid(
            row=3, column=0, sticky="w", padx=10, pady=(10, 0)
        )
        tk.Entry(self, textvariable=self._window_var, width=10).grid(row=3, column=1, sticky="w", pady=(10, 0))

        tk.Label(self, text="Ziel-DPI (z.B. 300 für Lasergravur)").grid(row=4, column=0, sticky="w", padx=10)
        tk.Entry(self, textvariable=self._dpi_var, width=10).grid(row=4, column=1, sticky="w")

        tk.Label(self, text="Zielgröße (mm)").grid(row=5, column=0, sticky="w", padx=10)
        tk.Entry(self, textvariable=self._size_var, width=10).grid(row=5, column=1, sticky="w")

        tk.Checkbutton(
            self, text="Einzelfoto-Serien automatisch übernehmen (keine Rückfrage)", variable=self._auto_var
        ).grid(row=6, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 0))

        tk.Checkbutton(
            self,
            text="Ähnliche Fotos trotz größerem Zeitabstand zur selben Serie zählen (Bildvergleich)",
            variable=self._similarity_enabled_var,
        ).grid(row=7, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 0))

        tk.Label(self, text="Ähnlichkeits-Schwellenwert (0 = identisch, höher = toleranter)").grid(
            row=8, column=0, sticky="w", padx=10
        )
        tk.Entry(self, textvariable=self._similarity_threshold_var, width=10).grid(row=8, column=1, sticky="w")

        tk.Label(self, text="Zusätzliche Zeit für Ähnlichkeitserkennung (Sekunden)").grid(
            row=9, column=0, sticky="w", padx=10
        )
        tk.Entry(self, textvariable=self._similarity_extra_var, width=10).grid(row=9, column=1, sticky="w")

        button_row = tk.Frame(self)
        button_row.grid(row=10, column=0, columnspan=3, pady=15)
        tk.Button(button_row, text="Speichern", command=self._save).pack(side="left", padx=5)
        tk.Button(button_row, text="Abbrechen", command=self.destroy).pack(side="left", padx=5)

    def _add_folder_row(self, label: str, var: tk.StringVar, row: int) -> None:
        tk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=4)
        tk.Entry(self, textvariable=var, width=40).grid(row=row, column=1, padx=4)
        tk.Button(self, text="...", command=lambda: self._browse(var)).grid(row=row, column=2, padx=(0, 10))

    def _browse(self, var: tk.StringVar) -> None:
        chosen = filedialog.askdirectory(initialdir=var.get() or ".")
        if chosen:
            var.set(chosen)

    def _save(self) -> None:
        try:
            window = int(self._window_var.get())
            dpi = int(self._dpi_var.get())
            size_mm = float(self._size_var.get())
            similarity_threshold = int(self._similarity_threshold_var.get())
            similarity_extra = int(self._similarity_extra_var.get())
            if window <= 0 or dpi <= 0 or size_mm <= 0 or similarity_threshold < 0 or similarity_extra < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Ungültige Eingabe",
                "Bitte gültige Zahlenwerte eingeben (Zeitfenster, DPI und Zielgröße positiv; "
                "Ähnlichkeits-Schwellenwert und Zusatzzeit nicht negativ).",
                parent=self,
            )
            return

        if not self._watch_var.get().strip() or not self._output_var.get().strip() or not self._done_var.get().strip():
            messagebox.showerror("Ungültige Eingabe", "Bitte alle drei Ordner angeben.", parent=self)
            return

        self._config.watch_folder = self._watch_var.get().strip()
        self._config.output_folder = self._output_var.get().strip()
        self._config.done_folder = self._done_var.get().strip()
        self._config.time_window_seconds = window
        self._config.target_dpi = dpi
        self._config.target_size_mm = size_mm
        self._config.auto_accept_single = self._auto_var.get()
        self._config.enable_similarity_grouping = self._similarity_enabled_var.get()
        self._config.similarity_hamming_threshold = similarity_threshold
        self._config.similarity_max_extra_seconds = similarity_extra

        self._on_save(self._config)
        self.destroy()
