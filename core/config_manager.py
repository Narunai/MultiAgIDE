import os
import json
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
PROFILES_DIR = BASE_DIR / "profiles"
CONFIG_FILE = BASE_DIR / "config.json"

DEFAULT_IDE_PATH = r"C:\Users\COMPUTER\AppData\Local\Programs\Antigravity IDE\Antigravity IDE.exe"
DEFAULT_CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

DEFAULT_CONFIG = {
    "ide_path": DEFAULT_IDE_PATH,
    "chrome_path": DEFAULT_CHROME_PATH,
    "max_slots": 6,
    "pairing_mode": "side_by_side",  # "side_by_side" or "toggle"
    "ide_width_ratio": 0.60,         # 60% IDE, 40% Chrome in side_by_side mode
    "active_layout": "matrix_6",     # "focus_1", "split_2", "trio_3", "quad_4", "matrix_6"
    "slots": [
        {"id": 1, "name": "Slot 1 (Main)", "visible": True, "notes": "Google Account #1"},
        {"id": 2, "name": "Slot 2", "visible": True, "notes": "Google Account #2"},
        {"id": 3, "name": "Slot 3", "visible": True, "notes": "Google Account #3"},
        {"id": 4, "name": "Slot 4", "visible": True, "notes": "Google Account #4"},
        {"id": 5, "name": "Slot 5", "visible": True, "notes": "Google Account #5"},
        {"id": 6, "name": "Slot 6", "visible": True, "notes": "Google Account #6"},
    ]
}


class ConfigManager:
    def __init__(self):
        self.config = self.load_config()
        self.ensure_profiles_dirs()

    def load_config(self):
        if not CONFIG_FILE.exists():
            self.save_config(DEFAULT_CONFIG)
            return dict(DEFAULT_CONFIG)
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Merge missing keys from default
                for k, v in DEFAULT_CONFIG.items():
                    if k not in loaded:
                        loaded[k] = v
                return loaded
        except Exception:
            return dict(DEFAULT_CONFIG)

    def save_config(self, cfg=None):
        if cfg is not None:
            self.config = cfg
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def ensure_profiles_dirs(self):
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        for slot in self.config.get("slots", []):
            slot_id = slot["id"]
            slot_dir = PROFILES_DIR / f"slot_{slot_id}"
            (slot_dir / "ide").mkdir(parents=True, exist_ok=True)
            (slot_dir / "chrome").mkdir(parents=True, exist_ok=True)

    def get_slot_paths(self, slot_id: int):
        slot_dir = PROFILES_DIR / f"slot_{slot_id}"
        return {
            "ide_dir": str(slot_dir / "ide"),
            "chrome_dir": str(slot_dir / "chrome"),
            "workspace_dir": str(slot_dir / "workspace")
        }

    def update_slot_visibility(self, slot_id: int, visible: bool):
        for slot in self.config.get("slots", []):
            if slot["id"] == slot_id:
                slot["visible"] = visible
                break
        self.save_config()

    def get_visible_slots(self):
        return [s for s in self.config.get("slots", []) if s.get("visible", True)]
