import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from .quota_service import QuotaInfo


class SlotHistoryRecord:
    def __init__(self, slot_id: int):
        self.slot_id: int = slot_id
        self.email: str = "offline"
        self.plan: str = "Pro"
        self.gemini_pct: int = 100
        self.rolling_5h_pct: int = 100
        self.weekly_str: str = "--"
        self.reset_5h_str: str = "--"
        self.weekly_ts: float = 0
        self.reset_5h_ts: float = 0
        self.last_launched_at: float = 0
        self.last_stopped_at: float = 0
        self.last_active_at: float = 0

    def to_dict(self) -> dict:
        return {
            "slot_id": self.slot_id,
            "email": self.email,
            "plan": self.plan,
            "gemini_pct": self.gemini_pct,
            "rolling_5h_pct": self.rolling_5h_pct,
            "weekly_str": self.weekly_str,
            "reset_5h_str": self.reset_5h_str,
            "weekly_ts": self.weekly_ts,
            "reset_5h_ts": self.reset_5h_ts,
            "last_launched_at": self.last_launched_at,
            "last_stopped_at": self.last_stopped_at,
            "last_active_at": self.last_active_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SlotHistoryRecord":
        rec = cls(data.get("slot_id", 1))
        rec.email = data.get("email", "offline")
        rec.plan = data.get("plan", "Pro")
        rec.gemini_pct = data.get("gemini_pct", 100)
        rec.rolling_5h_pct = data.get("rolling_5h_pct", 100)
        rec.weekly_str = data.get("weekly_str", "--")
        rec.reset_5h_str = data.get("reset_5h_str", "--")
        rec.weekly_ts = data.get("weekly_ts", 0)
        rec.reset_5h_ts = data.get("reset_5h_ts", 0)
        rec.last_launched_at = data.get("last_launched_at", 0)
        rec.last_stopped_at = data.get("last_stopped_at", 0)
        rec.last_active_at = data.get("last_active_at", 0)
        return rec


class SlotHistoryManager:
    """
    บันทึกและจัดการประวัติการใช้งาน บัญชี Google และโควตาล่าสุดของแต่ละสล็อต
    เพื่อช่วยให้ผู้ใช้ทราบว่าสล็อตไหนใช้งานล่าสุด และสล็อตไหนโควตาหมดหรือพร้อมใช้งานที่สุด
    """
    def __init__(self, profiles_dir: Path):
        self.history_file = profiles_dir / "slot_history.json"
        self.records: Dict[int, SlotHistoryRecord] = {i: SlotHistoryRecord(i) for i in range(1, 7)}
        self._load()

    def _load(self):
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for sid_str, item in data.items():
                        sid = int(sid_str)
                        if 1 <= sid <= 6:
                            self.records[sid] = SlotHistoryRecord.from_dict(item)
            except Exception as e:
                print(f"[SlotHistory] Error loading history: {e}")
        else:
            # ค่าเริ่มต้นที่ตรวจพบจากเซสชันของระบบ (พรีโหลดเพื่อให้เห็นทันที)
            seed_data = {
                1: {"email": "191aum7@gmail.com", "gemini_pct": 0, "rolling_5h_pct": 0, "weekly_str": "6d 21h", "reset_5h_str": "2h 11m", "last_active_at": 1727600792},
                2: {"email": "191aum8@gmail.com", "gemini_pct": 63, "rolling_5h_pct": 63, "weekly_str": "6d 21h", "reset_5h_str": "3h 00m", "last_active_at": 1727600850},
                3: {"email": "191aum9@gmail.com", "gemini_pct": 100, "rolling_5h_pct": 100, "weekly_str": "6d 21h", "reset_5h_str": "Ready", "last_active_at": 1727600800},
                4: {"email": "191aum10@gmail.com", "gemini_pct": 100, "rolling_5h_pct": 100, "weekly_str": "6d 21h", "reset_5h_str": "Ready", "last_active_at": 1727600804},
                5: {"email": "191aum13@gmail.com", "gemini_pct": 99, "rolling_5h_pct": 99, "weekly_str": "6d 21h", "reset_5h_str": "Ready", "last_active_at": 1727600807},
                6: {"email": "191aum2@gmail.com", "gemini_pct": 1, "rolling_5h_pct": 1, "weekly_str": "6d 21h", "reset_5h_str": "20h 31m", "last_active_at": 1727600811},
            }
            for sid, val in seed_data.items():
                rec = self.records[sid]
                rec.email = val["email"]
                rec.gemini_pct = val["gemini_pct"]
                rec.rolling_5h_pct = val["rolling_5h_pct"]
                rec.weekly_str = val["weekly_str"]
                rec.reset_5h_str = val["reset_5h_str"]
                rec.last_active_at = val["last_active_at"]
                rec.last_stopped_at = val["last_active_at"]
            self._save()

    def _save(self):
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            data = {str(sid): rec.to_dict() for sid, rec in self.records.items()}
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[SlotHistory] Error saving history: {e}")

    def get_record(self, slot_id: int) -> SlotHistoryRecord:
        return self.records.get(slot_id, SlotHistoryRecord(slot_id))

    def record_launch(self, slot_id: int):
        rec = self.records[slot_id]
        now = time.time()
        rec.last_launched_at = now
        rec.last_active_at = now
        self._save()

    def record_stop(self, slot_id: int):
        rec = self.records[slot_id]
        now = time.time()
        rec.last_stopped_at = now
        rec.last_active_at = now
        self._save()

    def record_quota(self, slot_id: int, q: QuotaInfo):
        if not q.connected:
            return
        rec = self.records[slot_id]
        rec.email = q.email
        rec.plan = q.plan
        rec.gemini_pct = q.gemini_pct
        rec.rolling_5h_pct = q.rolling_5h_pct
        rec.weekly_str = q.weekly_str
        rec.reset_5h_str = q.reset_5h_str
        rec.weekly_ts = q.weekly_ts
        rec.reset_5h_ts = q.reset_5h_ts
        rec.last_active_at = time.time()
        self._save()

    def get_last_used_slot_id(self) -> Optional[int]:
        """หาสล็อตที่ถูกใช้งานล่าสุดที่สุด"""
        best_sid = None
        best_time = 0
        for sid, rec in self.records.items():
            t = max(rec.last_launched_at, rec.last_stopped_at, rec.last_active_at)
            if t > best_time:
                best_time = t
                best_sid = sid
        return best_sid

    def get_best_available_slot_id(self, running_slot_ids: set) -> Optional[int]:
        """
        ค้นหาสล็อตที่ยังไม่ได้เปิด และมีโควตาพร้อมใช้งานสูงที่สุด
        """
        best_sid = None
        highest_score = -1

        for sid, rec in self.records.items():
            if sid in running_slot_ids:
                continue
            # ให้คะแนนตามเปอร์เซ็นต์โควตาคงเหลือ
            score = rec.gemini_pct + rec.rolling_5h_pct
            if score > highest_score:
                highest_score = score
                best_sid = sid
        return best_sid
