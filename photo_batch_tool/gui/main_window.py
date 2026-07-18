from __future__ import annotations

import queue
import shutil
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, simpledialog
from typing import List, Optional

from PIL import Image

from ..config import DEFAULT_CONFIG_PATH, Config
from ..exif_utils import get_photo_timestamp
from ..licensing import LicenseManager
from ..processing.background_removal import remove_background
from ..processing.errors import ProcessingError
from ..processing.export import scale_and_export
from ..series_builder import SeriesBuilder
from ..watcher import FolderWatcher
from .circle_crop_editor import CircleCropEditor
from .license_dialog import LicenseDialog
from .series_selector import SeriesSelectorDialog
from .settings_dialog import SettingsDialog

APP_TITLE = "Foto-Batch-Verarbeitung"


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title(APP_TITLE)

        self._license_manager = LicenseManager(DEFAULT_CONFIG_PATH.parent)
        if not self._check_license():
            self.after(0, self.destroy)
            return

        self.geometry("620x440")
        self.minsize(560, 360)

        self.config_obj = Config.load(DEFAULT_CONFIG_PATH)
        self._watcher: Optional[FolderWatcher] = None
        self._series_builder: Optional[SeriesBuilder] = None
        self._series_queue: "queue.Queue[List[Path]]" = queue.Queue()
        self._dialog_active = False
        self._watching = False

        self._build_ui()
        self._refresh_license_title()
        self.after(300, self._poll_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.deiconify()

    def _check_license(self) -> bool:
        status = self._license_manager.status()
        if status.licensed:
            return True
        result = {"ok": False}
        dialog = LicenseDialog(self, self._license_manager, on_result=lambda ok: result.update(ok=ok))
        self.wait_window(dialog)
        return result["ok"]

    def _refresh_license_title(self) -> None:
        status = self._license_manager.status()
        if status.trial:
            suffix = f"Testphase: noch {status.days_remaining} Tag(e)"
        else:
            suffix = f"Lizenziert bis {status.expires_at:%d.%m.%Y}"
        self.title(f"{APP_TITLE} — {suffix}")

    def _open_license_dialog(self) -> None:
        dialog = LicenseDialog(self, self._license_manager, on_result=lambda ok: None)
        self.wait_window(dialog)
        self._refresh_license_title()

    def _build_ui(self) -> None:
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        self._toggle_button = tk.Button(top, text="Überwachung starten", command=self._toggle_watch)
        self._toggle_button.pack(side="left")
        tk.Button(top, text="Einstellungen", command=self._open_settings).pack(side="left", padx=6)
        tk.Button(top, text="Lizenz verwalten", command=self._open_license_dialog).pack(side="left", padx=6)

        self._status_var = tk.StringVar(value="Gestoppt")
        tk.Label(self, textvariable=self._status_var, anchor="w").pack(fill="x", padx=10)

        tk.Label(self, text="Protokoll:").pack(anchor="w", padx=10, pady=(10, 0))
        log_frame = tk.Frame(self)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")
        self._log = tk.Listbox(log_frame, yscrollcommand=scrollbar.set)
        self._log.pack(fill="both", expand=True)
        scrollbar.config(command=self._log.yview)

    def _log_message(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log.insert("end", f"[{timestamp}] {message}")
        self._log.see("end")

    def _toggle_watch(self) -> None:
        if self._watching:
            self._stop_watch()
        else:
            self._start_watch()

    def _start_watch(self) -> None:
        watch_folder = Path(self.config_obj.watch_folder)
        self._series_builder = SeriesBuilder(
            window_seconds=self.config_obj.time_window_seconds,
            on_series_ready=self._on_series_ready,
        )
        self._watcher = FolderWatcher(watch_folder, self._series_builder.add_photo)
        self._watcher.start()
        for existing in self._watcher.scan_existing():
            self._series_builder.add_photo(existing)

        self._watching = True
        self._toggle_button.config(text="Überwachung stoppen")
        self._status_var.set(f"Überwache: {watch_folder}")
        self._log_message(f"Überwachung gestartet: {watch_folder}")

    def _stop_watch(self) -> None:
        if self._watcher:
            self._watcher.stop()
        self._watcher = None
        self._series_builder = None
        self._watching = False
        self._toggle_button.config(text="Überwachung starten")
        self._status_var.set("Gestoppt")
        self._log_message("Überwachung gestoppt")

    def _on_series_ready(self, photos: List[Path]) -> None:
        # Called from a watchdog/timer thread; hand off to the Tk main thread.
        self._series_queue.put(photos)

    def _poll_queue(self) -> None:
        if not self._dialog_active:
            try:
                photos = self._series_queue.get_nowait()
            except queue.Empty:
                photos = None
            if photos:
                self._dialog_active = True
                self._log_message(f"Neue Serie erkannt ({len(photos)} Foto(s))")
                self._present_series(photos)
        self.after(300, self._poll_queue)

    def _present_series(self, photos: List[Path]) -> None:
        if len(photos) == 1 and self.config_obj.auto_accept_single:
            self._start_processing(photos, photos[0])
            return
        SeriesSelectorDialog(self, photos, on_confirm=lambda selected: self._start_processing(photos, selected))

    def _start_processing(self, series_photos: List[Path], selected: Path) -> None:
        self._log_message(f"Verarbeite ausgewähltes Foto: {selected.name}")
        threading.Thread(
            target=self._background_remove_worker, args=(series_photos, selected), daemon=True
        ).start()

    def _background_remove_worker(self, series_photos: List[Path], selected: Path) -> None:
        try:
            result = remove_background(selected)
        except ProcessingError as exc:
            self.after(0, lambda: self._handle_processing_error(series_photos, str(exc)))
            return
        self.after(0, lambda: self._open_circle_editor(series_photos, selected, result))

    def _handle_processing_error(self, series_photos: List[Path], message: str) -> None:
        self._log_message(f"Fehler: {message}")
        messagebox.showerror("Verarbeitung fehlgeschlagen", message, parent=self)
        self._finish_series(series_photos, None)

    def _open_circle_editor(self, series_photos: List[Path], selected: Path, image: Image.Image) -> None:
        CircleCropEditor(
            self,
            image,
            on_confirm=lambda cropped: self._export_result(series_photos, cropped),
            on_cancel=lambda: self._finish_series(series_photos, None),
        )

    def _export_result(self, series_photos: List[Path], cropped: Image.Image) -> None:
        series_id = get_photo_timestamp(series_photos[0]).strftime("%Y%m%d_%H%M%S")
        customer = simpledialog.askstring("Kundenname", "Kundenname (optional):", parent=self) or ""
        try:
            out_path = scale_and_export(
                cropped,
                dpi=self.config_obj.target_dpi,
                target_mm=self.config_obj.target_size_mm,
                output_folder=Path(self.config_obj.output_folder),
                series_id=series_id,
                customer_name=customer,
            )
        except Exception as exc:
            self._handle_processing_error(series_photos, f"Export fehlgeschlagen: {exc}")
            return
        self._log_message(f"Export gespeichert: {out_path}")
        self._finish_series(series_photos, series_id)

    def _finish_series(self, series_photos: List[Path], series_id: Optional[str]) -> None:
        done_root = Path(self.config_obj.done_folder)
        subfolder = done_root / (series_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
        subfolder.mkdir(parents=True, exist_ok=True)
        for photo in series_photos:
            try:
                shutil.move(str(photo), str(subfolder / photo.name))
            except OSError as exc:
                self._log_message(f"Konnte {photo.name} nicht verschieben: {exc}")
        self._log_message(f"Serie abgeschlossen, verschoben nach {subfolder}")
        self._dialog_active = False

    def _open_settings(self) -> None:
        SettingsDialog(self, self.config_obj, on_save=self._save_settings)

    def _save_settings(self, config: Config) -> None:
        self.config_obj = config
        config.save(DEFAULT_CONFIG_PATH)
        self._log_message("Einstellungen gespeichert")
        if self._watching:
            messagebox.showinfo(
                "Hinweis",
                "Ordner- und Zeitfenster-Änderungen werden erst nach Neustart der Überwachung wirksam.",
                parent=self,
            )

    def _on_close(self) -> None:
        if self._watcher:
            self._watcher.stop()
        self.destroy()
