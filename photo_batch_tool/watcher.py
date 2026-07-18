from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Iterable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


def _wait_until_stable(path: Path, timeout: float = 20.0, interval: float = 0.5) -> bool:
    """Wait until a file's size stops changing, so we don't read a half-copied file."""
    deadline = time.monotonic() + timeout
    last_size = -1
    while time.monotonic() < deadline:
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size == last_size and size > 0:
            return True
        last_size = size
        time.sleep(interval)
    return False


class _Handler(FileSystemEventHandler):
    def __init__(self, on_new_photo: Callable[[Path], None]):
        self._on_new_photo = on_new_photo

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle(Path(event.src_path))

    def on_moved(self, event):
        if event.is_directory:
            return
        self._handle(Path(event.dest_path))

    def _handle(self, path: Path) -> None:
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        threading.Thread(target=self._wait_and_notify, args=(path,), daemon=True).start()

    def _wait_and_notify(self, path: Path) -> None:
        if _wait_until_stable(path):
            self._on_new_photo(path)


class FolderWatcher:
    def __init__(self, folder: Path, on_new_photo: Callable[[Path], None]):
        self._folder = folder
        self._handler = _Handler(on_new_photo)
        self._observer = Observer()

    def start(self) -> None:
        self._folder.mkdir(parents=True, exist_ok=True)
        self._observer.schedule(self._handler, str(self._folder), recursive=False)
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=5)

    def scan_existing(self) -> Iterable[Path]:
        """Photos already sitting in the watch folder when monitoring starts."""
        if not self._folder.exists():
            return []
        return sorted(
            p for p in self._folder.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )
