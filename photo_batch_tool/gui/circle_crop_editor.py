from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional, Tuple

from PIL import Image, ImageTk

from ..processing.circle_crop import apply_circular_crop, max_radius_for_center

MAX_DISPLAY = 640
CHECKER_SIZE = 16
PREVIEW_SIZE = 180


def _make_checkerboard(size: Tuple[int, int]) -> Image.Image:
    width, height = max(1, size[0]), max(1, size[1])
    tile = Image.new("RGB", (CHECKER_SIZE * 2, CHECKER_SIZE * 2), "#ffffff")
    dark = Image.new("RGB", (CHECKER_SIZE, CHECKER_SIZE), "#dedede")
    tile.paste(dark, (0, 0))
    tile.paste(dark, (CHECKER_SIZE, CHECKER_SIZE))
    board = Image.new("RGB", (width, height))
    for y in range(0, height, tile.height):
        for x in range(0, width, tile.width):
            board.paste(tile, (x, y))
    return board


class CircleCropEditor(tk.Toplevel):
    """Interactive circle placement over the background-removed photo.

    The circle can be dragged with the mouse, resized with the mouse wheel
    or the radius slider, and a live preview shows the resulting circular
    cutout. The radius is automatically clamped so it can never extend past
    the image edges.
    """

    def __init__(
        self,
        master: tk.Misc,
        image: Image.Image,
        on_confirm: Callable[[Image.Image], None],
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        super().__init__(master)
        self.title("Kreisausschnitt festlegen")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self._source = image.convert("RGBA")
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._dragging = False

        self._scale = min(1.0, MAX_DISPLAY / max(self._source.width, self._source.height))
        self._display_size = (
            max(1, round(self._source.width * self._scale)),
            max(1, round(self._source.height * self._scale)),
        )

        checker = _make_checkerboard(self._display_size)
        preview_base = self._source.resize(self._display_size, Image.LANCZOS)
        checker.paste(preview_base, (0, 0), preview_base)
        self._base_photo = ImageTk.PhotoImage(checker)

        self._center = [self._source.width / 2, self._source.height / 2]
        self._radius = min(self._source.width, self._source.height) / 4

        main = tk.Frame(self)
        main.pack(padx=10, pady=10)

        self._canvas = tk.Canvas(
            main,
            width=self._display_size[0],
            height=self._display_size[1],
            highlightthickness=1,
            highlightbackground="#999999",
        )
        self._canvas.grid(row=0, column=0, padx=(0, 10))
        self._canvas.create_image(0, 0, anchor="nw", image=self._base_photo)
        self._circle_id = self._canvas.create_oval(0, 0, 0, 0, outline="#ff3b30", width=2)

        side = tk.Frame(main)
        side.grid(row=0, column=1, sticky="n")
        tk.Label(side, text="Vorschau").pack()
        self._preview_label = tk.Label(side)
        self._preview_label.pack(pady=(0, 10))

        tk.Label(side, text="Radius").pack()
        self._radius_var = tk.DoubleVar(value=self._radius)
        self._radius_scale = tk.Scale(
            side,
            from_=5,
            to=self._max_possible_radius(),
            orient="horizontal",
            variable=self._radius_var,
            command=self._on_radius_slider,
            length=200,
        )
        self._radius_scale.pack()

        self._status_var = tk.StringVar(value="")
        tk.Label(side, textvariable=self._status_var, fg="#b00020", wraplength=200, justify="left").pack(
            pady=(4, 10)
        )

        button_row = tk.Frame(side)
        button_row.pack(pady=(10, 0))
        tk.Button(button_row, text="Bestätigen", command=self._confirm).pack(side="left", padx=4)
        tk.Button(button_row, text="Abbrechen", command=self._cancel).pack(side="left", padx=4)

        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<MouseWheel>", self._on_wheel)
        self._canvas.bind("<Button-4>", lambda e: self._adjust_radius(10))
        self._canvas.bind("<Button-5>", lambda e: self._adjust_radius(-10))
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._redraw()

    def _max_possible_radius(self) -> float:
        return max(10.0, min(self._source.width, self._source.height) / 2)

    def _clamp_center_and_radius(self) -> None:
        max_r = max_radius_for_center(self._source.size, tuple(self._center))
        if self._radius > max_r:
            self._radius = max_r
            self._status_var.set("Radius wurde an den Bildrand angepasst.")
        else:
            self._status_var.set("")

    def _to_image_coords(self, x: float, y: float) -> Tuple[float, float]:
        return x / self._scale, y / self._scale

    def _on_press(self, event) -> None:
        cx, cy = self._to_image_coords(event.x, event.y)
        dist = ((cx - self._center[0]) ** 2 + (cy - self._center[1]) ** 2) ** 0.5
        self._dragging = dist <= self._radius

    def _on_drag(self, event) -> None:
        if not self._dragging:
            return
        cx, cy = self._to_image_coords(event.x, event.y)
        self._center = [
            min(max(cx, 0), self._source.width),
            min(max(cy, 0), self._source.height),
        ]
        self._clamp_center_and_radius()
        self._redraw()

    def _on_wheel(self, event) -> None:
        self._adjust_radius(10 if event.delta > 0 else -10)

    def _adjust_radius(self, delta_display_px: float) -> None:
        self._radius = max(5.0, self._radius + delta_display_px / self._scale)
        self._clamp_center_and_radius()
        self._radius_var.set(self._radius)
        self._redraw()

    def _on_radius_slider(self, value: str) -> None:
        self._radius = float(value)
        self._clamp_center_and_radius()
        self._redraw()

    def _redraw(self) -> None:
        cx, cy = self._center[0] * self._scale, self._center[1] * self._scale
        r = self._radius * self._scale
        self._canvas.coords(self._circle_id, cx - r, cy - r, cx + r, cy + r)
        self._update_preview()

    def _update_preview(self) -> None:
        try:
            cropped = apply_circular_crop(self._source, tuple(self._center), self._radius)
        except Exception:
            return
        preview = cropped.copy()
        preview.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE))
        checker = _make_checkerboard(preview.size)
        checker.paste(preview, (0, 0), preview)
        self._preview_photo = ImageTk.PhotoImage(checker)
        self._preview_label.config(image=self._preview_photo)

    def _confirm(self) -> None:
        try:
            cropped = apply_circular_crop(self._source, tuple(self._center), self._radius)
        except Exception as exc:
            self._status_var.set(str(exc))
            return
        self.grab_release()
        self.destroy()
        self._on_confirm(cropped)

    def _cancel(self) -> None:
        self.grab_release()
        self.destroy()
        if self._on_cancel:
            self._on_cancel()
