from __future__ import annotations

import concurrent.futures
import queue
import shutil
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, simpledialog
from typing import Callable, List, Optional

from PIL import Image

from ..config import DEFAULT_CONFIG_PATH, Config
from ..exif_utils import get_photo_timestamp
from ..processing.background_removal import is_model_cached, remove_background
from ..processing.errors import ProcessingError
from ..processing.export import scale_and_export
from ..series_builder import SeriesBuilder
from ..watcher import FolderWatcher
from .circle_crop_editor import CircleCropEditor
from .series_selector import SeriesSelectorDialog
from .settings_dialog import SettingsDialog

# First run downloads a ~170 MB model; later runs use the cached copy and should be fast.
_MODEL_DOWNLOAD_TIMEOUT_SECONDS = 300
_PROCESSING_TIMEOUT_SECONDS = 90


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Foto-Batch-Verarbeitung")
        self.geometry("620x440")
        self.minsize(560, 360)

        self.config_obj = Config.load(DEFAULT_CONFIG_PATH)
        self._watcher: Optional[FolderWatcher] = None
        self._series_builder: Optional[SeriesBuilder] = None
        self._series_queue: "queue.Queue[List[Path]]" = queue.Queue()
        self._dialog_active = False
        self._watching = False

        self._build_ui()
        self.after(300, self._poll_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        self._toggle_button = tk.Button(top, text="Überwachung starten", command=self._toggle_watch)
        self._toggle_button.pack(side="left")
        tk.Button(top, text="Einstellungen", command=self._open_settings).pack(side="left", padx=6)

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
        if is_model_cached():
            hint = ""
        else:
            hint = " (erster Lauf: lädt ein ~170 MB KI-Modell herunter, kann mehrere Minuten dauern)"
        self._log_message(f"Verarbeite ausgewähltes Foto: {selected.name}{hint}")
        threading.Thread(
            target=self._background_remove_worker, args=(series_photos, selected), daemon=True
        ).start()

    def _background_remove_worker(self, series_photos: List[Path], selected: Path) -> None:
        timeout = _PROCESSING_TIMEOUT_SECONDS if is_model_cached() else _MODEL_DOWNLOAD_TIMEOUT_SECONDS
        # remove_background() can hang indefinitely (e.g. a firewall silently dropping the
        # model-download connection instead of refusing it), so it must run behind a hard
        # timeout -- otherwise a network hang looks exactly like a frozen app, with no error.
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(remove_background, selected)
        try:
            result = future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            message = (
                f"Die Hintergrundentfernung hat nach {timeout} Sekunden nicht reagiert. "
                "Vermutlich hängt der Download des rembg-KI-Modells fest (kein Internet oder "
                "eine Firewall/ein Proxy blockiert die Verbindung, statt sie abzulehnen). "
                "Siehe README, Abschnitt 'rembg-Modell manuell installieren'."
            )
            self.after(0, lambda: self._handle_processing_error(series_photos, message))
            return
        except ProcessingError as exc:
            self.after(0, lambda: self._handle_processing_error(series_photos, str(exc)))
            return
        except Exception as exc:  # pragma: no cover - safety net for truly unexpected failures
            self.after(0, lambda: self._handle_processing_error(series_photos, f"Unerwarteter Fehler: {exc}"))
            return
        finally:
            executor.shutdown(wait=False)
        self.after(0, lambda: self._safe_step(series_photos, lambda: self._open_circle_editor(series_photos, selected, result)))

    def _safe_step(self, series_photos: List[Path], step: Callable[[], None]) -> None:
        """Runs a GUI step scheduled via `after`; any exception here would otherwise be
        swallowed silently (no console in the packaged EXE) and leave the app stuck
        forever on this series, so we always surface it and free up the app again."""
        try:
            step()
        except Exception as exc:
            self._handle_processing_error(series_photos, f"Unerwarteter Fehler: {exc}")

    def _handle_processing_error(self, series_photos: List[Path], message: str) -> None:
        self._log_message(f"Fehler: {message}")
        messagebox.showerror("Verarbeitung fehlgeschlagen", message, parent=self)
        self._finish_series(series_photos, None)

    def _open_circle_editor(self, series_photos: List[Path], selected: Path, image: Image.Image) -> None:
        CircleCropEditor(
            self,
            image,
            on_confirm=lambda cropped: self._safe_step(series_photos, lambda: self._export_result(series_photos, cropped)),
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
