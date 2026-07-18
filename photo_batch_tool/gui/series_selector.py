from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable, List

from PIL import Image, ImageTk

THUMB_SIZE = (220, 220)
COLOR_SELECTED = "#3a7bd5"
COLOR_UNSELECTED = "#cccccc"


class SeriesSelectorDialog(tk.Toplevel):
    """Shows all photos of one detected series and lets the user pick one.

    Selection can happen by mouse click, by number keys 1-9, by arrow keys
    plus Enter, or by double-click. Single-photo series still go through this
    dialog (unless auto-accept is enabled elsewhere), satisfying the
    requirement that nothing gets silently skipped.
    """

    def __init__(self, master: tk.Misc, photos: List[Path], on_confirm: Callable[[Path], None]):
        super().__init__(master)
        self.title("Foto für Serie auswählen")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self._photos = photos
        self._on_confirm = on_confirm
        self._selected_index = 0
        self._thumb_images: List[ImageTk.PhotoImage] = []
        self._frames: List[tk.Frame] = []

        info = (
            f"{len(photos)} Foto(s) in dieser Serie erkannt."
            if len(photos) > 1
            else "Diese Serie enthält nur ein Foto."
        )
        tk.Label(self, text=info, font=("Segoe UI", 11, "bold")).pack(pady=(10, 4))
        tk.Label(
            self,
            text="Auswahl per Klick, Zifferntaste (1-9) oder Pfeiltasten + Enter. Doppelklick bestätigt sofort.",
        ).pack(pady=(0, 10))

        gallery = tk.Frame(self)
        gallery.pack(padx=10, pady=10)

        for index, photo in enumerate(photos):
            frame = tk.Frame(gallery, highlightthickness=3, highlightbackground=COLOR_UNSELECTED)
            frame.grid(row=0, column=index, padx=6, pady=6)
            self._frames.append(frame)

            thumb = self._load_thumbnail(photo)
            self._thumb_images.append(thumb)

            label = tk.Label(frame, image=thumb, cursor="hand2")
            label.pack()
            label.bind("<Button-1>", lambda e, i=index: self._select(i))
            label.bind("<Double-Button-1>", lambda e, i=index: self._confirm(i))

            caption = f"[{index + 1}] {photo.name}"
            tk.Label(frame, text=caption, wraplength=THUMB_SIZE[0]).pack()

        button_row = tk.Frame(self)
        button_row.pack(pady=(0, 10))
        tk.Button(button_row, text="Verwenden (Enter)", command=self._confirm_selected).pack()

        self._update_highlight()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.focus_set()

    def _load_thumbnail(self, photo: Path) -> ImageTk.PhotoImage:
        with Image.open(photo) as image:
            image = image.convert("RGB")
            image.thumbnail(THUMB_SIZE)
            return ImageTk.PhotoImage(image)

    def _bind_keys(self) -> None:
        for i in range(1, min(9, len(self._photos)) + 1):
            self.bind(str(i), lambda e, i=i: self._confirm(i - 1))
        self.bind("<Left>", lambda e: self._move(-1))
        self.bind("<Right>", lambda e: self._move(1))
        self.bind("<Return>", lambda e: self._confirm_selected())

    def _move(self, delta: int) -> None:
        self._select((self._selected_index + delta) % len(self._photos))

    def _select(self, index: int) -> None:
        self._selected_index = index
        self._update_highlight()

    def _update_highlight(self) -> None:
        for i, frame in enumerate(self._frames):
            frame.config(highlightbackground=COLOR_SELECTED if i == self._selected_index else COLOR_UNSELECTED)

    def _confirm_selected(self) -> None:
        self._confirm(self._selected_index)

    def _confirm(self, index: int) -> None:
        selected = self._photos[index]
        self.grab_release()
        self.destroy()
        self._on_confirm(selected)
