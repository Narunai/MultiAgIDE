import os
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Tuple, List, Optional

from .process_manager import ProcessManager
from .config_manager import ConfigManager


class SwapManager:
    """
    ระบบ Swap User และ Slot อัตโนมัติสำหรับ MultiAgIDE Studio
    - สลับบัญชี Google / Auth Tokens ข้ามสล็อต เพื่อให้โปรเจกต์เดิมสามารถเปลี่ยนไปใช้โควตาของอีกบัญชีได้ทันที
    - มีเงื่อนไขความปลอดภัย: ทั้ง 2 สล็อตต้อง STOPPED (ไม่รันอยู่) ถึงจะอนุญาตให้ทำการ Swap
    """

    def __init__(self, proc_mgr: ProcessManager, config_mgr: ConfigManager):
        self.proc_mgr = proc_mgr
        self.config_mgr = config_mgr
        self.profiles_dir = Path(__file__).resolve().parent.parent / "profiles"
        self.history_file = self.profiles_dir / "slot_history.json"

    def can_swap(self, sid_a: int, sid_b: int) -> Tuple[bool, str]:
        """ตรวจสอบเงื่อนไขความปลอดภัยก่อนอนุญาตให้ Swap"""
        if sid_a == sid_b:
            return False, "ไม่สามารถ Swap กับสล็อตเดียวกันได้"

        if self.proc_mgr.is_running(sid_a):
            return False, f"Slot #{sid_a} กำลังทำงานอยู่ (RUNNING) กรุณากด Stop ก่อนทำการ Swap"

        if self.proc_mgr.is_running(sid_b):
            return False, f"Slot #{sid_b} กำลังทำงานอยู่ (RUNNING) กรุณากด Stop ก่อนทำการ Swap"

        dir_a = self.profiles_dir / f"slot_{sid_a}"
        dir_b = self.profiles_dir / f"slot_{sid_b}"

        if not dir_a.exists() or not dir_b.exists():
            return False, "ไม่พบโฟลเดอร์โปรไฟล์ของสล็อตที่เลือก"

        return True, "OK"

    def get_swap_candidates(self, current_sid: int) -> List[dict]:
        """ดึงรายการสล็อตทั้งหมดที่สามารถเลือก Swap ได้ พร้อมสถานะและโควตา"""
        candidates = []
        is_current_running = self.proc_mgr.is_running(current_sid)

        slots_cfg = self.config_mgr.config.get("slots", [])
        for s in slots_cfg:
            sid = s["id"]
            if sid == current_sid:
                continue

            running = self.proc_mgr.is_running(sid)
            q, is_last, is_empty, is_cd, is_gen = self.proc_mgr.get_slot_display_quota(sid)

            # ตรวจสอบโปรเจกต์ใน workspace
            ws_dir = self.profiles_dir / f"slot_{sid}" / "workspace"
            projects = []
            if ws_dir.exists():
                for item in os.listdir(ws_dir):
                    if (ws_dir / item).is_dir() and not item.startswith("."):
                        projects.append(item)

            candidates.append({
                "slot_id": sid,
                "name": s.get("name", f"Slot {sid}"),
                "email": q.email,
                "plan": q.plan,
                "gemini_pct": q.gemini_pct,
                "rolling_5h_pct": q.rolling_5h_pct,
                "reset_5h_str": q.reset_5h_str,
                "weekly_str": q.weekly_str,
                "projects": projects,
                "is_running": running,
                "can_swap": (not is_current_running) and (not running)
            })

        return candidates

    def get_slot_summary(self, sid: int) -> dict:
        """ดึงข้อมูลสรุปของสล็อตที่ระบุ สำหรับแสดงผลใน UI Swap Dialog"""
        running = self.proc_mgr.is_running(sid)
        q, is_last, is_empty, is_cd, is_gen = self.proc_mgr.get_slot_display_quota(sid)
        slots_cfg = self.config_mgr.config.get("slots", [])
        cfg = next((s for s in slots_cfg if s["id"] == sid), {})

        ws_dir = self.profiles_dir / f"slot_{sid}" / "workspace"
        projects = []
        if ws_dir.exists():
            for item in os.listdir(ws_dir):
                if (ws_dir / item).is_dir() and not item.startswith("."):
                    projects.append(item)

        return {
            "slot_id": sid,
            "name": cfg.get("name", f"Slot {sid}"),
            "email": q.email,
            "plan": q.plan,
            "gemini_pct": q.gemini_pct,
            "rolling_5h_pct": q.rolling_5h_pct,
            "reset_5h_str": q.reset_5h_str,
            "weekly_str": q.weekly_str,
            "projects": projects,
            "is_running": running,
        }

    def _safe_move(self, src: Path, dst: Path, retries: int = 3, delay: float = 0.5):
        """ย้ายโฟลเดอร์พร้อม retry ป้องกัน Windows file lock ชั่วคราว"""
        import time
        for i in range(retries):
            try:
                shutil.move(str(src), str(dst))
                return True
            except PermissionError as e:
                if i < retries - 1:
                    time.sleep(delay)
                else:
                    raise e

    def swap_users(self, sid_a: int, sid_b: int, swap_mode: str = "user") -> Tuple[bool, str]:
        """
        ดำเนินการ Swap ระหว่าง 2 สล็อต
        swap_mode:
        - "user": สลับเฉพาะบัญชี Google / Auth Profile (ide/) โฟลเดอร์โปรเจกต์ (workspace/) ยังอยู่ที่เดิม
        - "slot": สลับทั้งสล็อต (ทั้งโปรเจกต์และบัญชีผู้ใช้)
        """
        ok, msg = self.can_swap(sid_a, sid_b)
        if not ok:
            return False, msg

        dir_a = self.profiles_dir / f"slot_{sid_a}"
        dir_b = self.profiles_dir / f"slot_{sid_b}"

        try:
            if swap_mode == "user":
                # 1. สลับโฟลเดอร์ ide/ (Auth, State, Extensions, Tokens)
                ide_a = dir_a / "ide"
                ide_b = dir_b / "ide"
                temp_ide = self.profiles_dir / f"_temp_swap_ide_{sid_a}_{sid_b}"

                if temp_ide.exists():
                    shutil.rmtree(temp_ide)

                # ย้ายแบบ atomic
                if ide_a.exists():
                    self._safe_move(ide_a, temp_ide)
                if ide_b.exists():
                    self._safe_move(ide_b, ide_a)
                if temp_ide.exists():
                    self._safe_move(temp_ide, ide_b)

                # 2. ปรับแต่ง Path references ใน ide/ ของทั้งสองสล็อต
                self._remap_slot_tag(ide_a, from_slot=sid_b, to_slot=sid_a)
                self._remap_slot_tag(ide_b, from_slot=sid_a, to_slot=sid_b)

                # 3. สลับประวัติและโควตาใน slot_history.json
                self._swap_history_records(sid_a, sid_b)

            elif swap_mode == "slot":
                # สลับโฟลเดอร์สล็อตทั้งหมด
                temp_slot = self.profiles_dir / f"_temp_swap_slot_{sid_a}_{sid_b}"
                if temp_slot.exists():
                    shutil.rmtree(temp_slot)

                self._safe_move(dir_a, temp_slot)
                self._safe_move(dir_b, dir_a)
                self._safe_move(temp_slot, dir_b)

                # สลับการตั้งค่าชื่อใน config.json
                cfg_slots = self.config_mgr.config.get("slots", [])
                slot_a_cfg = next((s for s in cfg_slots if s["id"] == sid_a), None)
                slot_b_cfg = next((s for s in cfg_slots if s["id"] == sid_b), None)
                if slot_a_cfg and slot_b_cfg:
                    slot_a_cfg["name"], slot_b_cfg["name"] = slot_b_cfg["name"], slot_a_cfg["name"]
                    slot_a_cfg["notes"], slot_b_cfg["notes"] = slot_b_cfg["notes"], slot_a_cfg["notes"]
                    self.config_mgr.save_config()

                # สลับประวัติและโควตาใน slot_history.json
                self._swap_history_records(sid_a, sid_b)

            # ล้างแคชใน ProcessManager
            self.proc_mgr.quota_svc.cache.pop(sid_a, None)
            self.proc_mgr.quota_svc.cache.pop(sid_b, None)
            self.proc_mgr.history_mgr._load()

            # บันทึกเหตุการณ์ใน Logger
            self.proc_mgr.logger.log_event(sid_a, "SWAP", f"Swapped ({swap_mode}) with Slot #{sid_b}")
            self.proc_mgr.logger.log_event(sid_b, "SWAP", f"Swapped ({swap_mode}) with Slot #{sid_a}")

            mode_text = "บัญชีผู้ใช้ (User Auth & Quota)" if swap_mode == "user" else "ข้อมูลสล็อตทั้งหมด"
            return True, f"สลับ{mode_text} ระหว่าง Slot #{sid_a} และ Slot #{sid_b} สำเร็จเรียบร้อย"

        except Exception as e:
            return False, f"เกิดข้อผิดพลาดขณะทำการ Swap: {e}"

    def _swap_history_records(self, sid_a: int, sid_b: int):
        """สลับข้อมูลประวัติการใช้งานและโควตาใน slot_history.json"""
        if not self.history_file.exists():
            return

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            s_a = str(sid_a)
            s_b = str(sid_b)

            rec_a = data.get(s_a, {"slot_id": sid_a})
            rec_b = data.get(s_b, {"slot_id": sid_b})

            # สลับฟิลด์ข้อมูลผู้ใช้
            fields = [
                "email", "plan", "gemini_pct", "rolling_5h_pct",
                "reset_5h_str", "weekly_str", "reset_5h_ts", "weekly_ts"
            ]
            for fld in fields:
                val_a = rec_a.get(fld)
                val_b = rec_b.get(fld)
                rec_a[fld] = val_b
                rec_b[fld] = val_a

            data[s_a] = rec_a
            data[s_b] = rec_b

            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error swapping history records: {e}")

    def _remap_slot_tag(self, ide_dir: Path, from_slot: int, to_slot: int):
        """ปรับแต่งพาธของสล็อตในไฟล์ตั้งค่าของ VS Code / Antigravity IDE หลังการย้าย"""
        if not ide_dir.exists():
            return

        old_tag = f"slot_{from_slot}"
        new_tag = f"slot_{to_slot}"

        # 1. storage.json
        storage_file = ide_dir / "User" / "globalStorage" / "storage.json"
        if storage_file.exists():
            try:
                content = storage_file.read_text(encoding="utf-8", errors="ignore")
                if old_tag in content:
                    storage_file.write_text(content.replace(old_tag, new_tag), encoding="utf-8")
            except Exception:
                pass

        # 2. workspace.json
        ws_storage = ide_dir / "User" / "workspaceStorage"
        if ws_storage.exists():
            for root, _, files in os.walk(ws_storage):
                for f in files:
                    if f == "workspace.json":
                        p = Path(root) / f
                        try:
                            content = p.read_text(encoding="utf-8", errors="ignore")
                            if old_tag in content:
                                p.write_text(content.replace(old_tag, new_tag), encoding="utf-8")
                        except Exception:
                            pass

        # 3. state.vscdb (SQLite)
        vscdb_file = ide_dir / "User" / "globalStorage" / "state.vscdb"
        if vscdb_file.exists():
            try:
                conn = sqlite3.connect(str(vscdb_file))
                cur = conn.cursor()
                cur.execute(f"UPDATE ItemTable SET value = replace(value, '{old_tag}', '{new_tag}') WHERE value LIKE '%{old_tag}%'")
                conn.commit()
                conn.close()
            except Exception:
                pass
