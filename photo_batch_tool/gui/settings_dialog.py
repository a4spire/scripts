from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk
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
        self._ask_customer_name_var = tk.BooleanVar(value=config.ask_customer_name)
        self._similarity_enabled_var = tk.BooleanVar(value=config.enable_similarity_grouping)
        self._similarity_threshold_var = tk.StringVar(value=str(config.similarity_hamming_threshold))
        self._similarity_extra_var = tk.StringVar(value=str(config.similarity_max_extra_seconds))
        self._quality_enabled_var = tk.BooleanVar(value=config.enable_quality_filter)
        self._quality_action_var = tk.StringVar(
            value="Nur markieren" if config.quality_action == "warn" else "Automatisch aussortieren"
        )
        self._quality_blur_var = tk.StringVar(value=str(config.quality_blur_threshold))
        self._quality_min_bright_var = tk.StringVar(value=str(config.quality_min_brightness))
        self._quality_max_bright_var = tk.StringVar(value=str(config.quality_max_brightness))
        self._auto_confirm_var = tk.BooleanVar(value=config.auto_confirm_unambiguous_selection)
        self._selection_timeout_enabled_var = tk.BooleanVar(value=config.enable_selection_timeout)
        self._selection_timeout_var = tk.StringVar(value=str(config.selection_timeout_seconds))
        self._circle_timeout_enabled_var = tk.BooleanVar(value=config.enable_circle_crop_timeout)
        self._circle_timeout_var = tk.StringVar(value=str(config.circle_crop_timeout_seconds))

        folders = tk.LabelFrame(self, text="Ordner")
        folders.pack(fill="x", padx=10, pady=(10, 5))
        self._add_folder_row(folders, "Überwachungsordner", self._watch_var, 0)
        self._add_folder_row(folders, "Ausgabeordner", self._output_var, 1)
        self._add_folder_row(folders, "Erledigt-Ordner", self._done_var, 2)

        processing = tk.LabelFrame(self, text="Verarbeitung")
        processing.pack(fill="x", padx=10, pady=5)
        tk.Label(processing, text="Zeitfenster Serienerkennung (Sekunden)").grid(
            row=0, column=0, sticky="w", padx=10, pady=(6, 0)
        )
        tk.Entry(processing, textvariable=self._window_var, width=10).grid(
            row=0, column=1, sticky="w", pady=(6, 0)
        )
        tk.Label(processing, text="Ziel-DPI (z.B. 300 für Lasergravur)").grid(
            row=1, column=0, sticky="w", padx=10
        )
        tk.Entry(processing, textvariable=self._dpi_var, width=10).grid(row=1, column=1, sticky="w")
        tk.Label(processing, text="Zielgröße (mm)").grid(row=2, column=0, sticky="w", padx=10)
        tk.Entry(processing, textvariable=self._size_var, width=10).grid(row=2, column=1, sticky="w")
        tk.Checkbutton(
            processing, text="Einzelfoto-Serien automatisch übernehmen (keine Rückfrage)", variable=self._auto_var
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=10, pady=(6, 2))
        tk.Checkbutton(
            processing, text="Kundennamen beim Export abfragen", variable=self._ask_customer_name_var
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 6))

        similarity = tk.LabelFrame(self, text="Serienerkennung per Bildähnlichkeit")
        similarity.pack(fill="x", padx=10, pady=5)
        tk.Checkbutton(
            similarity,
            text="Ähnliche Fotos trotz größerem Zeitabstand zur selben Serie zählen",
            variable=self._similarity_enabled_var,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(6, 2))
        tk.Label(similarity, text="Ähnlichkeits-Schwellenwert (0 = identisch, höher = toleranter)").grid(
            row=1, column=0, sticky="w", padx=10
        )
        tk.Entry(similarity, textvariable=self._similarity_threshold_var, width=10).grid(
            row=1, column=1, sticky="w"
        )
        tk.Label(similarity, text="Zusätzliche Zeit für Ähnlichkeitserkennung (Sekunden)").grid(
            row=2, column=0, sticky="w", padx=10, pady=(0, 6)
        )
        tk.Entry(similarity, textvariable=self._similarity_extra_var, width=10).grid(
            row=2, column=1, sticky="w", pady=(0, 6)
        )

        quality = tk.LabelFrame(self, text="Automatische Qualitätsprüfung (Unschärfe, Belichtung, Augen/Gesicht)")
        quality.pack(fill="x", padx=10, pady=5)
        tk.Checkbutton(
            quality, text="Fotos automatisch auf Qualitätsprobleme prüfen", variable=self._quality_enabled_var
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(6, 2))
        tk.Label(quality, text="Bei Problemen:").grid(row=1, column=0, sticky="w", padx=10)
        ttk.Combobox(
            quality,
            textvariable=self._quality_action_var,
            values=["Nur markieren", "Automatisch aussortieren"],
            state="readonly",
            width=22,
        ).grid(row=1, column=1, columnspan=2, sticky="w")
        tk.Label(quality, text="Unschärfe-Schwellenwert (niedriger = strenger)").grid(
            row=2, column=0, sticky="w", padx=10, pady=(4, 0)
        )
        tk.Entry(quality, textvariable=self._quality_blur_var, width=10).grid(
            row=2, column=1, sticky="w", pady=(4, 0)
        )
        tk.Label(quality, text="Mindesthelligkeit (0-255, darunter = zu dunkel)").grid(
            row=3, column=0, sticky="w", padx=10
        )
        tk.Entry(quality, textvariable=self._quality_min_bright_var, width=10).grid(row=3, column=1, sticky="w")
        tk.Label(quality, text="Maximalhelligkeit (0-255, darüber = zu hell)").grid(
            row=4, column=0, sticky="w", padx=10, pady=(0, 6)
        )
        tk.Entry(quality, textvariable=self._quality_max_bright_var, width=10).grid(
            row=4, column=1, sticky="w", pady=(0, 6)
        )
        tk.Checkbutton(
            quality,
            text='Bei eindeutiger Auswahl automatisch bestätigen (nur wirksam bei "Automatisch aussortieren": '
            "bleibt nach dem Aussortieren genau ein Foto übrig, wird es ohne Rückfrage verwendet)",
            variable=self._auto_confirm_var,
            wraplength=420,
            justify="left",
        ).grid(row=5, column=0, columnspan=3, sticky="w", padx=10, pady=(2, 6))

        timeout = tk.LabelFrame(self, text="Auswahl-Zeitlimit (Fotoauswahl)")
        timeout.pack(fill="x", padx=10, pady=5)
        tk.Checkbutton(
            timeout,
            text="Auswahl nach Zeitlimit automatisch bestätigen (best bewertetes Foto ist vorausgewählt)",
            variable=self._selection_timeout_enabled_var,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(6, 2))
        tk.Label(timeout, text="Zeitlimit in Sekunden (0 = sofort anwenden, kein Dialog)").grid(
            row=1, column=0, sticky="w", padx=10, pady=(0, 6)
        )
        tk.Entry(timeout, textvariable=self._selection_timeout_var, width=10).grid(
            row=1, column=1, sticky="w", pady=(0, 6)
        )

        circle_timeout = tk.LabelFrame(self, text="Auswahl-Zeitlimit (Kreisausschnitt)")
        circle_timeout.pack(fill="x", padx=10, pady=5)
        tk.Checkbutton(
            circle_timeout,
            text="Kreisausschnitt nach Zeitlimit automatisch bestätigen (Gesichtserkennung/Bildmitte als Vorschlag)",
            variable=self._circle_timeout_enabled_var,
            wraplength=420,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(6, 2))
        tk.Label(circle_timeout, text="Zeitlimit in Sekunden (0 = sofort anwenden, kein Dialog)").grid(
            row=1, column=0, sticky="w", padx=10, pady=(0, 6)
        )
        tk.Entry(circle_timeout, textvariable=self._circle_timeout_var, width=10).grid(
            row=1, column=1, sticky="w", pady=(0, 6)
        )

        self._error_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._error_var, fg="#b00020", wraplength=420, justify="left").pack(
            padx=10, pady=(4, 0)
        )

        button_row = tk.Frame(self)
        button_row.pack(pady=15)
        tk.Button(button_row, text="Speichern", command=self._save).pack(side="left", padx=5)
        tk.Button(button_row, text="Abbrechen", command=self.destroy).pack(side="left", padx=5)

    def _add_folder_row(self, parent: tk.Misc, label: str, var: tk.StringVar, row: int) -> None:
        pady = (6, 4) if row == 0 else 4
        tk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=pady)
        tk.Entry(parent, textvariable=var, width=40).grid(row=row, column=1, padx=4, pady=pady)
        tk.Button(parent, text="...", command=lambda: self._browse(var)).grid(
            row=row, column=2, padx=(0, 10), pady=pady
        )

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
            quality_blur = float(self._quality_blur_var.get())
            quality_min_bright = float(self._quality_min_bright_var.get())
            quality_max_bright = float(self._quality_max_bright_var.get())
            selection_timeout = int(self._selection_timeout_var.get())
            circle_timeout = int(self._circle_timeout_var.get())
            if (
                window <= 0
                or dpi <= 0
                or size_mm <= 0
                or similarity_threshold < 0
                or similarity_extra < 0
                or quality_blur < 0
                or not (0 <= quality_min_bright <= 255)
                or not (0 <= quality_max_bright <= 255)
                or quality_min_bright >= quality_max_bright
                or selection_timeout < 0
                or circle_timeout < 0
            ):
                raise ValueError
        except ValueError:
            self._error_var.set(
                "Bitte gültige Zahlenwerte eingeben (Zeitfenster, DPI und Zielgröße positiv; "
                "Ähnlichkeits-Schwellenwert, Zusatzzeit und Zeitlimits nicht negativ; Helligkeitswerte "
                "0-255 mit Minimum < Maximum)."
            )
            return

        if not self._watch_var.get().strip() or not self._output_var.get().strip() or not self._done_var.get().strip():
            self._error_var.set("Bitte alle drei Ordner angeben.")
            return

        self._error_var.set("")
        self._config.watch_folder = self._watch_var.get().strip()
        self._config.output_folder = self._output_var.get().strip()
        self._config.done_folder = self._done_var.get().strip()
        self._config.time_window_seconds = window
        self._config.target_dpi = dpi
        self._config.target_size_mm = size_mm
        self._config.auto_accept_single = self._auto_var.get()
        self._config.ask_customer_name = self._ask_customer_name_var.get()
        self._config.enable_similarity_grouping = self._similarity_enabled_var.get()
        self._config.similarity_hamming_threshold = similarity_threshold
        self._config.similarity_max_extra_seconds = similarity_extra
        self._config.enable_quality_filter = self._quality_enabled_var.get()
        self._config.quality_action = "warn" if self._quality_action_var.get() == "Nur markieren" else "auto_move"
        self._config.quality_blur_threshold = quality_blur
        self._config.quality_min_brightness = quality_min_bright
        self._config.quality_max_brightness = quality_max_bright
        self._config.auto_confirm_unambiguous_selection = self._auto_confirm_var.get()
        self._config.enable_selection_timeout = self._selection_timeout_enabled_var.get()
        self._config.selection_timeout_seconds = selection_timeout
        self._config.enable_circle_crop_timeout = self._circle_timeout_enabled_var.get()
        self._config.circle_crop_timeout_seconds = circle_timeout

        self._on_save(self._config)
        self.destroy()
