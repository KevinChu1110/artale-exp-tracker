import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".artale-tracker"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "capture_region": None,  # {"x": int, "y": int, "w": int, "h": int}
    "ocr_interval": 5,  # seconds
    "ocr_threshold": 100,  # binary threshold for OCR preprocessing
    "ocr_scale": 3,  # resize multiplier
    "window_pos": None,  # {"x": int, "y": int}
    "window_size": None,  # {"w": int, "h": int}
    "compact_mode": False,
    "current_level": 1,
    "current_exp": 0,
    "target_exp": 0,  # EXP needed for next level (manual input or from table)
}


class Settings:
    def __init__(self):
        self._data = dict(DEFAULT_CONFIG)
        self._load()

    def _load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except (json.JSONDecodeError, IOError):
                pass

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value
