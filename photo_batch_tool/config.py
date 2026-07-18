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
    time_window_seconds: int = 60
    target_dpi: int = 300
    target_size_mm: float = 19.0
    auto_accept_single: bool = False

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
