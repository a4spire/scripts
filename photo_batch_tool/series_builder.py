from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .exif_utils import get_photo_timestamp
from .image_similarity import compute_hash, hamming_distance


class SeriesBuilder:
    """Groups incoming photos into series based on their EXIF capture time.

    New photos are buffered. Whenever `time_window_seconds` pass without a
    new arrival, the buffer is sorted by capture timestamp and split into
    series wherever the gap between consecutive photos exceeds the window.
    This makes grouping robust against photos arriving out of order (e.g.
    when a folder is bulk-copied).

    If `enable_similarity_grouping` is set, a gap larger than the window
    doesn't automatically start a new series: consecutive photos are also
    compared with a perceptual image hash, and a close match (Hamming
    distance <= `similarity_hamming_threshold`) keeps them in the same
    series anyway, up to `similarity_max_extra_seconds` beyond the normal
    window. This catches series where the user paused between shots
    (reviewing a preview, repositioning, etc.) without merging genuinely
    unrelated photos taken much later.
    """

    def __init__(
        self,
        window_seconds: int,
        on_series_ready: Callable[[List[Path], float], None],
        enable_similarity_grouping: bool = True,
        similarity_hamming_threshold: int = 8,
        similarity_max_extra_seconds: int = 240,
    ):
        self.window_seconds = window_seconds
        self.on_series_ready = on_series_ready
        self.enable_similarity_grouping = enable_similarity_grouping
        self.similarity_hamming_threshold = similarity_hamming_threshold
        self.similarity_max_extra_seconds = similarity_max_extra_seconds
        self._pending: List[Path] = []
        self._arrival_times: Dict[Path, float] = {}
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None

    def add_photo(self, path: Path) -> None:
        with self._lock:
            if path in self._arrival_times:
                # Already pending -- e.g. a manual "scan now" re-discovering a file the
                # watcher already picked up. Ignore instead of queuing it twice.
                return
            self._pending.append(path)
            self._arrival_times[path] = time.monotonic()
            self._reset_timer_locked()

    def flush_now(self) -> None:
        """Force processing of whatever is currently pending (skips the debounce wait --
        used for shutdown and for a user-triggered manual scan)."""
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
            arrival_times = self._arrival_times
            self._pending = []
            self._arrival_times = {}
            self._timer = None
        if not pending:
            return

        items = sorted(((p, get_photo_timestamp(p)) for p in pending), key=lambda item: item[1])

        hash_cache: Dict[Path, Optional[int]] = {}

        def get_hash(path: Path) -> Optional[int]:
            if path not in hash_cache:
                try:
                    hash_cache[path] = compute_hash(path)
                except Exception:
                    hash_cache[path] = None
            return hash_cache[path]

        series: List[List[Path]] = [[items[0][0]]]
        last_ts = items[0][1]
        last_path = items[0][0]
        for path, ts in items[1:]:
            gap = (ts - last_ts).total_seconds()
            same_series = gap <= self.window_seconds

            if (
                not same_series
                and self.enable_similarity_grouping
                and gap <= self.window_seconds + self.similarity_max_extra_seconds
            ):
                hash_a, hash_b = get_hash(last_path), get_hash(path)
                if hash_a is not None and hash_b is not None:
                    same_series = hamming_distance(hash_a, hash_b) <= self.similarity_hamming_threshold

            if same_series:
                series[-1].append(path)
            else:
                series.append([path])
            last_ts = ts
            last_path = path

        now = time.monotonic()
        for group in series:
            first_arrival = min((arrival_times.get(p, now) for p in group), default=now)
            self.on_series_ready(group, first_arrival)
