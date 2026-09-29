import os
import json
import datetime
from pathlib import Path


class ConversationLogger:
    def __init__(self, profiles_base_dir: Path):
        self.base_dir = profiles_base_dir

    def get_slot_log_dir(self, slot_id: int) -> Path:
        log_dir = self.base_dir / f"slot_{slot_id}" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    def log_event(self, slot_id: int, event_type: str, message: str, extra: dict = None):
        """บันทึกเหตุการณ์ของสล็อตลงไฟล์ activity.jsonl ประจำสล็อต"""
        log_dir = self.get_slot_log_dir(slot_id)
        log_file = log_dir / "activity.jsonl"

        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "slot_id": slot_id,
            "event": event_type,
            "message": message,
            "extra": extra or {}
        }

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Failed to write log for Slot {slot_id}: {e}")

    def get_recent_logs(self, slot_id: int, limit: int = 50) -> list:
        log_file = self.get_slot_log_dir(slot_id) / "activity.jsonl"
        if not log_file.exists():
            return []
        try:
            lines = []
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        lines.append(json.loads(line.strip()))
            return lines[-limit:]
        except Exception:
            return []
