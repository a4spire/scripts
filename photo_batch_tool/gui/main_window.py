from __future__ import annotations

import concurrent.futures
import queue
import shutil
import threading
import time
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
from ..processing.face_detection import auto_crop_circle
from ..processing.quality_check import pick_best_photo, split_by_quality
from ..series_builder import SeriesBuilder
from ..watcher import SUPPORTED_EXTENSIONS, FolderWatcher
from .circle_crop_editor import CircleCropEditor
from .series_selector import SeriesSelectorDialog
from .settings_dialog import SettingsDialog

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    _DND_AVAILABLE = True
    _BaseWindow = TkinterDnD.Tk
except ImportError:  # pragma: no cover - exercised only when the optional dep is missing
    _DND_AVAILABLE = False
    DND_FILES = None
    _BaseWindow = tk.Tk

# First run downloads a ~170 MB model; later runs use the cached copy and should be fast.
_MODEL_DOWNLOAD_TIMEOUT_SECONDS = 300
_PROCESSING_TIMEOUT_SECONDS = 90


def _collect_dropped_photos(raw_paths: List[str]) -> List[Path]:
    """Expands a list of drag & drop paths (files and/or folders) into a
    flat, sorted list of supported image files, recursing into folders so
    the whole process can be fed by dropping an entire SD-card folder."""
    collected: List[Path] = []
    for raw in raw_paths:
        path = Path(raw)
        if path.is_dir():
            collected.extend(
                f for f in path.rglob("*") if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
            )
        elif path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            collected.append(path)
    return sorted(set(collected))


def _unique_destination(directory: Path, filename: str) -> Path:
    """Appends a counter suffix if `filename` already exists in `directory`,
    so moving a photo there never silently overwrites an unrelated file --
    this matters once multiple series can share the same folder (the
    per-date "_aussortiert" folder)."""
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = Path(filename).stem, Path(filename).suffix
    counter = 1
    while True:
        candidate = directory / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


class MainWindow(_BaseWindow):
    def __init__(self):
        super().__init__()
        self.title("Foto-Batch-Verarbeitung")
        self.geometry("620x480")
        self.minsize(560, 380)

        self.config_obj = Config.load(DEFAULT_CONFIG_PATH)
        self._watcher: Optional[FolderWatcher] = None
        self._series_builder: Optional[SeriesBuilder] = None
        self._series_queue: "queue.Queue[tuple[List[Path], float]]" = queue.Queue()
        self._dialog_active = False
        self._watching = False
        self._current_excluded_low_quality: List[Path] = []
        self._current_series_started_at: Optional[float] = None

        self._build_ui()
        self._setup_drop_target()
        self.after(150, self._poll_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        self._toggle_button = tk.Button(top, text="Überwachung starten", command=self._toggle_watch)
        self._toggle_button.pack(side="left")
        tk.Button(top, text="Einstellungen", command=self._open_settings).pack(side="left", padx=6)

        self._status_var = tk.StringVar(value="Gestoppt")
        tk.Label(self, textvariable=self._status_var, anchor="w").pack(fill="x", padx=10)

        drop_text = (
            "Fotos oder Ordner hierher ziehen für Batch-Verarbeitung"
            if _DND_AVAILABLE
            else "Drag & Drop nicht verfügbar (tkinterdnd2 fehlt) -- Fotos direkt in den Überwachungsordner legen"
        )
        self._drop_zone = tk.Label(
            self,
            text=drop_text,
            relief="ridge",
            borderwidth=2,
            bg="#f0f0f0",
            fg="#333333",
            pady=12,
        )
        self._drop_zone.pack(fill="x", padx=10, pady=(8, 0))

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

    def _setup_drop_target(self) -> None:
        if not _DND_AVAILABLE:
            self._log_message(
                "Hinweis: Drag & Drop ist deaktiviert (Paket 'tkinterdnd2' nicht installiert)."
            )
            return
        for widget in (self, self._drop_zone):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event) -> None:
        raw_paths = self.tk.splitlist(event.data)
        photos = _collect_dropped_photos(raw_paths)
        if not photos:
            self._log_message("Drag & Drop: keine unterstützten Bilddateien in der Ablage gefunden.")
            return

        if not self._watching:
            self._start_watch()

        watch_folder = Path(self.config_obj.watch_folder)
        copied = 0
        for src in photos:
            try:
                shutil.copy2(str(src), str(_unique_destination(watch_folder, src.name)))
                copied += 1
            except OSError as exc:
                self._log_message(f"Drag & Drop: {src.name} konnte nicht kopiert werden: {exc}")
        self._log_message(
            f"Drag & Drop: {copied} Foto(s) in den Überwachungsordner übernommen -- Originaldateien bleiben unverändert."
        )

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
            enable_similarity_grouping=self.config_obj.enable_similarity_grouping,
            similarity_hamming_threshold=self.config_obj.similarity_hamming_threshold,
            similarity_max_extra_seconds=self.config_obj.similarity_max_extra_seconds,
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

    def _on_series_ready(self, photos: List[Path], first_arrival: float) -> None:
        # Called from a watchdog/timer thread; hand off to the Tk main thread.
        self._series_queue.put((photos, first_arrival))

    def _poll_queue(self) -> None:
        if not self._dialog_active:
            try:
                photos, first_arrival = self._series_queue.get_nowait()
            except queue.Empty:
                photos = None
                first_arrival = None
            if photos:
                self._dialog_active = True
                self._current_series_started_at = first_arrival
                recognition_elapsed = time.monotonic() - first_arrival
                self._log_message(
                    f"Neue Serie erkannt ({len(photos)} Foto(s), Erkennung nach {recognition_elapsed:.1f}s)"
                )
                self._present_series(photos)
        self.after(150, self._poll_queue)

    def _present_series(self, photos: List[Path]) -> None:
        selectable, excluded, assessments = split_by_quality(
            photos,
            self.config_obj.enable_quality_filter,
            self.config_obj.quality_action,
            self.config_obj.quality_blur_threshold,
            self.config_obj.quality_min_brightness,
            self.config_obj.quality_max_brightness,
        )

        if self.config_obj.enable_selection_timeout and self.config_obj.selection_timeout_seconds <= 0:
            best = pick_best_photo(selectable, assessments)
            self._log_message(
                f"Auswahl-Zeitlimit auf 0 gesetzt -- {best.name} wird sofort automatisch übernommen."
            )
            self._start_processing(photos, best, excluded)
            return

        if len(photos) == 1 and self.config_obj.auto_accept_single:
            assessment = assessments.get(photos[0])
            if assessment is None or not assessment.is_low_quality:
                self._start_processing(photos, photos[0], excluded)
                return
            self._log_message(
                f"Einzelfoto der Serie zeigt mögliche Qualitätsprobleme "
                f"({', '.join(assessment.reasons)}) -- zeige trotz Auto-Übernahme zur Bestätigung."
            )
        elif (
            len(photos) > 1
            and self.config_obj.auto_confirm_unambiguous_selection
            and len(selectable) == 1
        ):
            sole_candidate = selectable[0]
            candidate_assessment = assessments.get(sole_candidate)
            if candidate_assessment is None or not candidate_assessment.is_low_quality:
                self._log_message(
                    f"Eindeutige Auswahl erkannt ({sole_candidate.name}, "
                    f"{len(excluded)} andere(s) aussortiert) -- automatisch bestätigt."
                )
                self._start_processing(photos, sole_candidate, excluded)
                return

        timeout_seconds = (
            self.config_obj.selection_timeout_seconds if self.config_obj.enable_selection_timeout else None
        )
        SeriesSelectorDialog(
            self,
            selectable,
            excluded,
            assessments,
            on_confirm=lambda selected, exc: self._start_processing(photos, selected, exc),
            timeout_seconds=timeout_seconds,
        )

    def _start_processing(self, series_photos: List[Path], selected: Path, excluded_low_quality: List[Path]) -> None:
        self._current_excluded_low_quality = excluded_low_quality
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
        if self.config_obj.enable_circle_crop_timeout and self.config_obj.circle_crop_timeout_seconds <= 0:
            try:
                cropped = auto_crop_circle(image)
            except Exception as exc:
                self._handle_processing_error(series_photos, f"Automatischer Kreisausschnitt fehlgeschlagen: {exc}")
                return
            self._log_message("Kreisausschnitt-Zeitlimit auf 0 gesetzt -- Ausschnitt sofort automatisch übernommen.")
            self._safe_step(series_photos, lambda: self._export_result(series_photos, cropped))
            return

        circle_timeout = (
            self.config_obj.circle_crop_timeout_seconds if self.config_obj.enable_circle_crop_timeout else None
        )
        CircleCropEditor(
            self,
            image,
            on_confirm=lambda cropped: self._safe_step(series_photos, lambda: self._export_result(series_photos, cropped)),
            on_cancel=lambda: self._finish_series(series_photos, None),
            timeout_seconds=circle_timeout,
        )

    def _export_result(self, series_photos: List[Path], cropped: Image.Image) -> None:
        series_id = get_photo_timestamp(series_photos[0]).strftime("%Y%m%d_%H%M%S")
        customer = ""
        if self.config_obj.ask_customer_name:
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
        folder_name = series_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        subfolder = done_root / folder_name

        # Aussortierte Fotos werden bewusst NICHT pro Serie getrennt, sondern
        # nur nach Datum gruppiert, damit an einem Tag aussortierte Fotos aus
        # mehreren Serien in einem gemeinsamen Ordner landen statt in vielen
        # einzelnen Serien-Unterordnern.
        date_part = folder_name.split("_")[0]
        reject_subfolder = done_root / "_aussortiert" / date_part
        excluded_set = set(self._current_excluded_low_quality)

        for photo in series_photos:
            target_dir = reject_subfolder if photo in excluded_set else subfolder
            target_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(photo), str(_unique_destination(target_dir, photo.name)))
            except OSError as exc:
                self._log_message(f"Konnte {photo.name} nicht verschieben: {exc}")

        self._log_message(f"Serie abgeschlossen, verschoben nach {subfolder}")
        if excluded_set:
            self._log_message(
                f"{len(excluded_set)} Foto(s) wegen Qualitätsprüfung nach {reject_subfolder} verschoben"
            )
        if self._current_series_started_at is not None:
            total_elapsed = time.monotonic() - self._current_series_started_at
            self._log_message(f"Gesamtdauer seit Erkennung: {total_elapsed:.1f}s")
        self._current_excluded_low_quality = []
        self._current_series_started_at = None
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
