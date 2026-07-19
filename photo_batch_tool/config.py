from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


def _default_config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "PhotoBatchTool"


DEFAULT_CONFIG_PATH = _default_config_dir() / "config.json"


@dataclass
class Config:
    watch_folder: str = str(_default_config_dir() / "eingang")
    output_folder: str = str(_default_config_dir() / "export")
    done_folder: str = str(_default_config_dir() / "erledigt")
    time_window_seconds: int = 15
    target_dpi: int = 300
    target_size_mm: float = 19.0
    auto_accept_single: bool = False
    enable_similarity_grouping: bool = True
    similarity_hamming_threshold: int = 8
    similarity_max_extra_seconds: int = 240
    ask_customer_name: bool = True
    enable_quality_filter: bool = True
    quality_action: str = "warn"  # "warn" (mark, still selectable) or "auto_move" (hide + move to aussortiert)
    quality_blur_threshold: float = 100.0
    quality_min_brightness: float = 40.0
    quality_max_brightness: float = 220.0
    auto_confirm_unambiguous_selection: bool = False
    enable_selection_timeout: bool = False
    selection_timeout_seconds: int = 10
    enable_circle_crop_timeout: bool = False
    circle_crop_timeout_seconds: int = 10

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> "Config":
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            valid_fields = cls.__dataclass_fields__.keys()
            return cls(**{k: v for k, v in data.items() if k in valid_fields})
        return cls()

    def save(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
