from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, List

from .exif_utils import get_photo_timestamp


class SeriesBuilder:
    """Groups incoming photos into series based on their EXIF capture time.

    New photos are buffered. Whenever `time_window_seconds` pass without a
    new arrival, the buffer is sorted by capture timestamp and split into
    series wherever the gap between consecutive photos exceeds the window.
    This makes grouping robust against photos arriving out of order (e.g.
    when a folder is bulk-copied).
    """

    def __init__(self, window_seconds: int, on_series_ready: Callable[[List[Path]], None]):
        self.window_seconds = window_seconds
        self.on_series_ready = on_series_ready
        self._pending: List[Path] = []
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def add_photo(self, path: Path) -> None:
        with self._lock:
            self._pending.append(path)
            self._reset_timer_locked()

    def flush_now(self) -> None:
        """Force processing of whatever is currently pending (e.g. on shutdown)."""
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
        self._flush()

    def _reset_timer_locked(self) -> None:
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self.window_seconds, self._flush)
        self._timer.daemon = True
        self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            pending = self._pending
            self._pending = []
            self._timer = None
        if not pending:
            return

        items = sorted(((p, get_photo_timestamp(p)) for p in pending), key=lambda item: item[1])

        series: List[List[Path]] = [[items[0][0]]]
        last_ts = items[0][1]
        for path, ts in items[1:]:
            if (ts - last_ts).total_seconds() <= self.window_seconds:
                series[-1].append(path)
            else:
                series.append([path])
            last_ts = ts

        for group in series:
            self.on_series_ready(group)
