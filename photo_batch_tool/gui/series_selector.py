from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable, Dict, List

from PIL import Image, ImageTk

from ..processing.quality_check import QualityAssessment

THUMB_SIZE = (220, 220)
COLOR_SELECTED = "#3a7bd5"
COLOR_UNSELECTED = "#cccccc"
COLOR_WARNING = "#b3760a"


class SeriesSelectorDialog(tk.Toplevel):
    """Shows the selectable photos of one detected series and lets the user
    pick one.

    Selection can happen by mouse click, by number keys 1-9, by arrow keys
    plus Enter, or by double-click. Single-photo series still go through this
    dialog (unless auto-accept is enabled elsewhere), satisfying the
    requirement that nothing gets silently skipped.

    `photos` is the already-filtered gallery to display (quality-based
    exclusion, if any, has already happened in the caller via
    `quality_check.split_by_quality`); `excluded` and `assessments` are
    passed through only for bookkeeping and for showing warnings on
    photos that stayed selectable despite a flagged quality issue
    ("warn" mode).
    """

    def __init__(
        self,
        master: tk.Misc,
        photos: List[Path],
        excluded: List[Path],
        assessments: Dict[Path, QualityAssessment],
        on_confirm: Callable[[Path, List[Path]], None],
    ):
        super().__init__(master)
        self.title("Foto für Serie auswählen")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self._photos = photos
        self._excluded = excluded
        self._on_confirm = on_confirm
        self._selected_index = 0
        self._thumb_images: List[ImageTk.PhotoImage] = []
        self._frames: List[tk.Frame] = []

        info_parts = [
            f"{len(photos)} Foto(s) in dieser Serie erkannt."
            if len(photos) > 1
            else "Diese Serie enthält nur ein Foto."
        ]
        if excluded:
            info_parts.append(f"{len(excluded)} davon wegen Qualitätsproblemen automatisch aussortiert.")
        tk.Label(self, text=" ".join(info_parts), font=("Segoe UI", 11, "bold")).pack(pady=(10, 4))
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

            assessment = assessments.get(photo)
            if assessment is not None and assessment.is_low_quality:
                tk.Label(
                    frame,
                    text=", ".join(assessment.reasons),
                    fg=COLOR_WARNING,
                    wraplength=THUMB_SIZE[0],
                    justify="center",
                ).pack()

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
        self._on_confirm(selected, self._excluded)
