# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-purpose Windows desktop app (Python + Tkinter): **Photo Batch Tool**. It watches a folder for
incoming photos, groups them into series by EXIF timestamp, lets the user pick one photo per series,
removes the background (`rembg`), lets the user position/resize a circular crop, scales it to an exact
physical size at a configured DPI (e.g. 19×19 mm at 300 DPI for laser engraving), and exports a PNG —
then moves every photo of the series out of the watch folder into a "done" folder. Everything is
German-language UI text; the full user-facing behavior (every setting, every automatic mode, every
timing/quality tradeoff) is documented in `README.md` — read it before changing behavior described there,
and update it when behavior changes.

There is no test suite in this repo.

## Commands

```powershell
# Install deps (Windows, Python 3.10+ — needs Tkinter, which ships with python.org installers)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Run
python main.py

# Build the standalone .exe (also runs automatically on push via
# .github/workflows/build-windows-exe.yml on a windows-latest runner)
pip install pyinstaller
pyinstaller PhotoBatchTool.spec   # -> dist/PhotoBatchTool.exe
```

Syntax-check a file without Tkinter: `python3 -m py_compile <file>`.

### Developing without Windows/Tkinter

This is routinely developed from a Linux sandbox that has **no `tkinter` module and no display**, so the
`gui/` package cannot be imported or run there. The working pattern used throughout this codebase:

- Verify GUI files with `python3 -m py_compile` (syntax only).
- Verify pure-logic modules (`series_builder.py`, `image_similarity.py`, `processing/*.py`,
  `watcher.py`'s helpers) by importing and exercising them directly with synthetic data / `unittest.mock`
  — none of them import `tkinter`.
- Never claim GUI behavior is "tested" from this environment — say explicitly that it's unverified on
  Windows/Tkinter when that's the case.

## Architecture

### Data flow

`watcher.py` (`FolderWatcher`, using `watchdog`) detects new files in the watch folder, waits for each
file's size to stabilize (so half-copied files aren't picked up), then feeds paths one at a time into
`series_builder.py` (`SeriesBuilder`). `SeriesBuilder` buffers photos and flushes them as one or more
"series" via a debounce `threading.Timer` that resets on every new arrival and fires `window_seconds`
after the *last* one — so the configured time window doubles as both the "how long to wait before
considering a series done" delay and the "how large a gap still counts as the same series" threshold.
Gaps larger than the window can still be bridged into the same series via `image_similarity.py`
(perceptual dHash + Hamming distance) if enabled, but only if the later photo arrives *before* the
buffer would otherwise have already flushed — bridging a gap that spans an already-completed flush is
not possible by construction.

`gui/main_window.py` (`MainWindow`) owns everything downstream of series detection: quality filtering
→ photo selection → background removal → circle crop → export → move-to-done. Per-series photos always
end up moved out of the watch folder (never deleted) — either into `done_folder/<series_id>/`, or into
`done_folder/_aussortiert/<date>/` for photos a quality check auto-rejected (deliberately grouped by
date, not by series). The export step itself never creates subfolders under `output_folder`.

### Concurrency model in `main_window.py`

Several series can have their (slow) background-removal + export step running **at the same time**, via
a shared, bounded `ThreadPoolExecutor` (`self._bg_executor`, sized from CPU count). This is intentional
for throughput. But every *interactive* Tk popup (`SeriesSelectorDialog`, `CircleCropEditor`, and the
customer-name/voucher-count `simpledialog` prompts) calls `grab_set()`, and Tkinter can't sensibly show
two grabbed windows at once — so those are serialized through a small explicit queue on `MainWindow`
(`_gui_queue` / `_gui_busy` / `_enqueue_gui()` / `_gui_done()`), independent of the background-processing
concurrency. When adding a new interactive step, route it through `_enqueue_gui()` rather than opening a
`Toplevel` directly, and always guard its body so `_gui_done()` is still called on any exception —
otherwise the queue deadlocks for every subsequent series for the rest of the session.

Because several series can be mid-pipeline simultaneously, per-series state (`excluded_low_quality`,
`started_at`, etc.) is threaded through function parameters/closures end-to-end (`_present_series` →
`_start_processing` → `_background_remove_worker` → `_open_circle_editor` → `_export_result` →
`_finish_series`), never stored on `self` — that would race across concurrently-running series.

Background threads never touch Tk widgets directly; they marshal back to the main thread via
`self.after(0, lambda: ...)` before calling `_log_message`, opening dialogs, etc.

### `processing/background_removal.py`

- Imports `rembg` lazily but exactly once, behind a lock, caching either the imported functions or the
  raised exception (`_get_rembg()`). This matters because a naive per-call `import rembg` is not safe
  under the concurrency above: if the first import fails partway (e.g. missing transitive-dependency
  metadata in the frozen EXE), Python leaves a half-initialized module in `sys.modules`, and a second
  thread racing in at the same time would get a confusing, unrelated-looking error instead of the real
  one.
- Caches a single rembg `Session` (`_get_session()`) instead of letting `rembg.remove()` create a new one
  per call — reloading the ~170 MB ONNX model from disk on every photo was the dominant cost.
  onnxruntime sessions are safe to share across threads.
- Downscales the source image before handing it to rembg (`_resize_for_processing`), sized from the
  configured export DPI/mm with generous headroom — the exported crop is only a few hundred pixels, so
  this cuts inference time on large camera photos without visible quality loss.
- Downloads the U2Net model itself (`ensure_model_available`) instead of relying on rembg's own
  downloader, which has no timeout and can hang forever behind a firewall that silently drops
  connections. Own downloader: bounded timeout + retries, writes to a temp file and only renames it into
  place after an MD5 check, so a crash mid-download can never leave a corrupt file at the path rembg
  expects.

### Other `processing/` modules

- `face_detection.py`: OpenCV Haar cascades (bundled in the `opencv-python-headless` wheel, no model
  download) propose a default circle center/radius covering all detected faces. Fails open — no
  faces/any OpenCV error just falls back to centering on the whole image.
- `quality_check.py`: blur (Laplacian variance), over/under-exposure, and a "possibly closed eyes"
  heuristic (face detected but no eye found in the upper face region). `split_by_quality()` is the single
  source of truth for the selectable/excluded split, shared between the selector dialog and
  `main_window.py`'s auto-confirm logic — don't duplicate that logic elsewhere. `pick_best_photo()` ranks
  candidates (unflagged > flagged, then sharper, then closer to neutral brightness) for pre-selecting the
  best photo in the UI.
- `circle_crop.py` / `export.py`: geometry clamping (`max_radius_for_center`) and the final
  resize-to-exact-physical-size + DPI-tagged PNG write.
- `errors.py`: `ProcessingError` is the base for all expected, user-facing failures; catch this
  specifically where you want a clean message instead of a stack trace, and let anything else surface as
  "unerwarteter Fehler" (see `MainWindow._safe_step`).

### Design conventions to preserve

- **Fail-open**: face detection, quality checks, and image-similarity hashing all catch broadly and
  return a neutral/safe default rather than raising — a detection glitch must never block the core
  export pipeline.
- **Non-destructive**: photos are moved, never deleted. `_unique_destination()` (in `main_window.py`)
  appends a numeric suffix instead of overwriting when a destination filename collides.
- **Transparency in the log**: every automatic decision (auto-confirm, timeout firing, quality rejection,
  step timing) gets a `_log_message()` line in the on-screen Protokoll — this is relied on for debugging
  since the packaged EXE has no console. Keep this up when adding new automatic behavior.
- Countdown timers in `SeriesSelectorDialog`/`CircleCropEditor` are aborted (not just paused) the moment
  the user manually interacts — see `_cancel_pending_tick(manual_edit=True)` in both files.

### PyInstaller packaging gotchas (`PhotoBatchTool.spec`)

- `opencv-python-headless` is pinned `<5.0` in `requirements.txt`: 5.x dropped the bundled Haar cascade
  XML files that `face_detection.py` depends on (verified empirically, not from changelogs).
- `copy_metadata("pymatting")` is required in the spec on top of `collect_all("rembg")` — rembg imports
  `pymatting` at load time, and `pymatting` reads its own version via `importlib.metadata` at import
  time; without its dist-info bundled, `import rembg` fails only in the frozen EXE, not in a normal venv.
  If a new dependency causes a similar "No package metadata was found for X" error in a built EXE (but
  not when run from source), the fix is the same: add `copy_metadata("X")`.
- The rembg model itself is deliberately *not* bundled into the EXE; it downloads on first run into
  `%USERPROFILE%\.u2net\` (see `background_removal.py`'s own downloader above).
