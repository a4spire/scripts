from __future__ import annotations

import concurrent.futures
import os
import queue
import shutil
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
from ..processing.export import compute_pixel_size, scale_and_export
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


def _default_bg_removal_workers() -> int:
    """How many photos may run background removal at the same time. rembg's
    CPU inference is compute-heavy, so this is deliberately capped well below
    the core count instead of one-per-series -- otherwise many series
    arriving at once would make every single one slower by fighting over the
    CPU, rather than actually finishing sooner."""
    cpu_count = os.cpu_count() or 2
    return max(1, min(4, cpu_count // 2))


_MAX_CONCURRENT_BACKGROUND_REMOVALS = _default_bg_removal_workers()


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
        self._watching = False

        # GUI popups (photo-selection dialog, circle-crop editor) each take an
        # exclusive Tk grab, so only one can sensibly be shown at a time --
        # they queue here. Everything else (background removal, export,
        # moving files) is NOT gated by this and can run for several series
        # concurrently; see `_bg_executor` below.
        self._gui_queue: List[Callable[[], None]] = []
        self._gui_busy = False

        self._bg_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=_MAX_CONCURRENT_BACKGROUND_REMOVALS
        )

        self._build_ui()
        self._setup_drop_target()
        self._log_message(
            f"Bis zu {_MAX_CONCURRENT_BACKGROUND_REMOVALS} Foto(s) können gleichzeitig "
            "im Hintergrund verarbeitet werden."
        )
        self.after(150, self._poll_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        self._toggle_button = tk.Button(top, text="Überwachung starten", command=self._toggle_watch)
        self._toggle_button.pack(side="left")
        tk.Button(top, text="Jetzt scannen", command=self._scan_now).pack(side="left", padx=6)
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

    def _enqueue_gui(self, show: Callable[[], None]) -> None:
        """Queues a GUI popup (selection dialog or circle-crop editor). Only one
        such popup is ever open at a time (they use an exclusive Tk grab), but
        this does not hold up background removal/export for other series --
        those keep running concurrently regardless of the GUI queue."""
        self._gui_queue.append(show)
        self._advance_gui_queue()

    def _advance_gui_queue(self) -> None:
        if self._gui_busy or not self._gui_queue:
            return
        self._gui_busy = True
        show = self._gui_queue.pop(0)
        show()

    def _gui_done(self) -> None:
        self._gui_busy = False
        self._advance_gui_queue()

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

    def _scan_now(self) -> None:
        """Manually triggers the detection/processing pipeline immediately,
        instead of waiting for the debounce timer (`time_window_seconds`) to
        elapse on its own. Starts monitoring first if it isn't running yet."""
        if not self._watching:
            self._start_watch()

        watch_folder = Path(self.config_obj.watch_folder)
        found = 0
        if watch_folder.exists():
            for path in sorted(
                p for p in watch_folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
            ):
                self._series_builder.add_photo(path)
                found += 1

        self._series_builder.flush_now()
        self._log_message(
            f"Jetzt scannen: {found} Foto(s) im Überwachungsordner gefunden, Verarbeitung wird sofort gestartet."
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
        # Drain everything currently queued -- series are no longer gated one-at-a-time
        # here; each one starts its own (possibly concurrent) processing pipeline below.
        while True:
            try:
                photos, first_arrival = self._series_queue.get_nowait()
            except queue.Empty:
                break
            recognition_elapsed = time.monotonic() - first_arrival
            self._log_message(
                f"Neue Serie erkannt ({len(photos)} Foto(s), Erkennung nach {recognition_elapsed:.1f}s)"
            )
            self._present_series(photos, first_arrival)
        self.after(150, self._poll_queue)

    def _present_series(self, photos: List[Path], started_at: float) -> None:
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
            self._start_processing(photos, best, excluded, started_at)
            return

        if len(photos) == 1 and self.config_obj.auto_accept_single:
            assessment = assessments.get(photos[0])
            if assessment is None or not assessment.is_low_quality:
                self._start_processing(photos, photos[0], excluded, started_at)
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
                self._start_processing(photos, sole_candidate, excluded, started_at)
                return

        timeout_seconds = (
            self.config_obj.selection_timeout_seconds if self.config_obj.enable_selection_timeout else None
        )

        def show_selector() -> None:
            def on_confirm(selected: Path, exc: List[Path]) -> None:
                self._gui_done()
                self._start_processing(photos, selected, exc, started_at)

            try:
                SeriesSelectorDialog(
                    self,
                    selectable,
                    excluded,
                    assessments,
                    on_confirm=on_confirm,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                # Never leave the GUI queue stuck if e.g. a thumbnail fails to load
                # (photo deleted/corrupted between detection and now).
                self._gui_done()
                self._handle_processing_error(
                    photos, f"Auswahldialog konnte nicht geöffnet werden: {exc}", excluded, started_at
                )

        self._enqueue_gui(show_selector)

    def _start_processing(
        self, series_photos: List[Path], selected: Path, excluded_low_quality: List[Path], started_at: float
    ) -> None:
        if is_model_cached():
            hint = ""
        else:
            hint = " (erster Lauf: lädt ein ~170 MB KI-Modell herunter, kann mehrere Minuten dauern)"
        self._log_message(f"Verarbeite ausgewähltes Foto: {selected.name}{hint}")
        self._bg_executor.submit(
            self._background_remove_worker, series_photos, selected, excluded_low_quality, started_at
        )

    def _background_remove_worker(
        self, series_photos: List[Path], selected: Path, excluded_low_quality: List[Path], started_at: float
    ) -> None:
        model_cached = is_model_cached()
        timeout = _PROCESSING_TIMEOUT_SECONDS if model_cached else _MODEL_DOWNLOAD_TIMEOUT_SECONDS
        max_dimension = max(1200, compute_pixel_size(self.config_obj.target_size_mm, self.config_obj.target_dpi) * 4)
        step_started = time.monotonic()
        # remove_background() can hang indefinitely (e.g. a firewall silently dropping the
        # model-download connection instead of refusing it), so it must run behind a hard
        # timeout -- otherwise a network hang looks exactly like a frozen app, with no error.
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(remove_background, selected, max_dimension)
        try:
            result = future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            if model_cached:
                message = (
                    f"Die Hintergrundentfernung hat nach {timeout} Sekunden nicht reagiert. Das KI-Modell "
                    "ist bereits lokal vorhanden -- vermutlich ist das Foto ungewöhnlich groß/komplex oder "
                    "die Hardware gerade ausgelastet, kein Hinweis auf ein Internet-/Firewall-Problem."
                )
            else:
                message = (
                    f"Die Hintergrundentfernung hat nach {timeout} Sekunden nicht reagiert. "
                    "Vermutlich hängt der Download des rembg-KI-Modells fest (kein Internet oder "
                    "eine Firewall/ein Proxy blockiert die Verbindung, statt sie abzulehnen). "
                    "Siehe README, Abschnitt 'rembg-Modell manuell installieren'."
                )
            self.after(
                0, lambda: self._handle_processing_error(series_photos, message, excluded_low_quality, started_at)
            )
            return
        except ProcessingError as exc:
            self.after(
                0,
                lambda: self._handle_processing_error(series_photos, str(exc), excluded_low_quality, started_at),
            )
            return
        except Exception as exc:  # pragma: no cover - safety net for truly unexpected failures
            self.after(
                0,
                lambda: self._handle_processing_error(
                    series_photos, f"Unerwarteter Fehler: {exc}", excluded_low_quality, started_at
                ),
            )
            return
        finally:
            executor.shutdown(wait=False)
        step_elapsed = time.monotonic() - step_started
        self.after(
            0, lambda: self._log_message(f"Hintergrundentfernung abgeschlossen in {step_elapsed:.1f}s: {selected.name}")
        )
        self.after(
            0,
            lambda: self._safe_step(
                series_photos,
                excluded_low_quality,
                started_at,
                lambda: self._open_circle_editor(series_photos, selected, result, excluded_low_quality, started_at),
            ),
        )

    def _safe_step(
        self, series_photos: List[Path], excluded_low_quality: List[Path], started_at: float, step: Callable[[], None]
    ) -> None:
        """Runs a GUI step scheduled via `after`; any exception here would otherwise be
        swallowed silently (no console in the packaged EXE) and leave the app stuck
        forever on this series, so we always surface it and free up the app again."""
        try:
            step()
        except Exception as exc:
            self._handle_processing_error(series_photos, f"Unerwarteter Fehler: {exc}", excluded_low_quality, started_at)

    def _handle_processing_error(
        self, series_photos: List[Path], message: str, excluded_low_quality: List[Path], started_at: float
    ) -> None:
        self._log_message(f"Fehler: {message}")
        messagebox.showerror("Verarbeitung fehlgeschlagen", message, parent=self)
        self._finish_series(series_photos, None, excluded_low_quality, started_at)

    def _open_circle_editor(
        self,
        series_photos: List[Path],
        selected: Path,
        image: Image.Image,
        excluded_low_quality: List[Path],
        started_at: float,
    ) -> None:
        if self.config_obj.enable_circle_crop_timeout and self.config_obj.circle_crop_timeout_seconds <= 0:
            try:
                cropped = auto_crop_circle(image)
            except Exception as exc:
                self._handle_processing_error(
                    series_photos, f"Automatischer Kreisausschnitt fehlgeschlagen: {exc}", excluded_low_quality, started_at
                )
                return
            self._log_message("Kreisausschnitt-Zeitlimit auf 0 gesetzt -- Ausschnitt sofort automatisch übernommen.")
            self._safe_step(
                series_photos,
                excluded_low_quality,
                started_at,
                lambda: self._export_result(series_photos, cropped, excluded_low_quality, started_at),
            )
            return

        circle_timeout = (
            self.config_obj.circle_crop_timeout_seconds if self.config_obj.enable_circle_crop_timeout else None
        )

        def show_circle_editor() -> None:
            def on_confirm(cropped: Image.Image) -> None:
                self._gui_done()
                self._safe_step(
                    series_photos,
                    excluded_low_quality,
                    started_at,
                    lambda: self._export_result(series_photos, cropped, excluded_low_quality, started_at),
                )

            def on_cancel() -> None:
                self._gui_done()
                self._finish_series(series_photos, None, excluded_low_quality, started_at)

            try:
                CircleCropEditor(
                    self,
                    image,
                    on_confirm=on_confirm,
                    on_cancel=on_cancel,
                    timeout_seconds=circle_timeout,
                )
            except Exception as exc:
                self._gui_done()
                self._handle_processing_error(
                    series_photos, f"Kreisausschnitt-Editor konnte nicht geöffnet werden: {exc}",
                    excluded_low_quality, started_at,
                )

        self._enqueue_gui(show_circle_editor)

    def _export_result(
        self, series_photos: List[Path], cropped: Image.Image, excluded_low_quality: List[Path], started_at: float
    ) -> None:
        # simpledialog.askstring() is also a modal Tk popup (it pumps a nested event
        # loop while open), so -- like the selector dialog and circle editor -- it
        # has to go through the same GUI queue to avoid two modal grabs at once
        # when several series finish around the same time.
        if self.config_obj.ask_customer_name:

            def ask_and_export() -> None:
                try:
                    customer = simpledialog.askstring("Kundenname", "Kundenname (optional):", parent=self) or ""
                except Exception as exc:
                    self._gui_done()
                    self._handle_processing_error(
                        series_photos, f"Kundennamen-Abfrage fehlgeschlagen: {exc}", excluded_low_quality, started_at
                    )
                    return
                self._gui_done()
                self._safe_step(
                    series_photos,
                    excluded_low_quality,
                    started_at,
                    lambda: self._finish_export(series_photos, cropped, customer, excluded_low_quality, started_at),
                )

            self._enqueue_gui(ask_and_export)
            return

        self._finish_export(series_photos, cropped, "", excluded_low_quality, started_at)

    def _finish_export(
        self,
        series_photos: List[Path],
        cropped: Image.Image,
        customer_name: str,
        excluded_low_quality: List[Path],
        started_at: float,
    ) -> None:
        series_id = get_photo_timestamp(series_photos[0]).strftime("%Y%m%d_%H%M%S")
        try:
            out_path = scale_and_export(
                cropped,
                dpi=self.config_obj.target_dpi,
                target_mm=self.config_obj.target_size_mm,
                output_folder=Path(self.config_obj.output_folder),
                series_id=series_id,
                customer_name=customer_name,
            )
        except Exception as exc:
            self._handle_processing_error(series_photos, f"Export fehlgeschlagen: {exc}", excluded_low_quality, started_at)
            return
        self._log_message(f"Export gespeichert: {out_path}")
        self._finish_series(series_photos, series_id, excluded_low_quality, started_at)

    def _finish_series(
        self,
        series_photos: List[Path],
        series_id: Optional[str],
        excluded_low_quality: List[Path],
        started_at: float,
    ) -> None:
        done_root = Path(self.config_obj.done_folder)
        folder_name = series_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        subfolder = done_root / folder_name

        # Aussortierte Fotos werden bewusst NICHT pro Serie getrennt, sondern
        # nur nach Datum gruppiert, damit an einem Tag aussortierte Fotos aus
        # mehreren Serien in einem gemeinsamen Ordner landen statt in vielen
        # einzelnen Serien-Unterordnern.
        date_part = folder_name.split("_")[0]
        reject_subfolder = done_root / "_aussortiert" / date_part
        excluded_set = set(excluded_low_quality)

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
        total_elapsed = time.monotonic() - started_at
        self._log_message(f"Gesamtdauer seit Erkennung: {total_elapsed:.1f}s")

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
        self._bg_executor.shutdown(wait=False)
        self.destroy()
