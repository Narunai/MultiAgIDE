import os
import subprocess
import time
import threading
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import psutil

from .config_manager import ConfigManager
from .window_controller import WindowController
from .layout_calculator import LayoutCalculator
from .quota_service import QuotaService, QuotaInfo
from .conversation_logger import ConversationLogger
from .slot_history_manager import SlotHistoryManager, SlotHistoryRecord


class SlotState:
    def __init__(self, slot_id: int):
        self.slot_id = slot_id
        self.ide_proc: Optional[subprocess.Popen] = None
        self.ide_pid: Optional[int] = None
        self.ide_hwnd: Optional[int] = None
        self.is_hidden: bool = False
        self.is_maximized: bool = False
        self.quota_info: QuotaInfo = QuotaInfo()
        self.ls_proc = None
        self.last_io_bytes: int = 0
        self.is_generating: bool = False
        self.high_io_ticks: int = 0
        self.low_io_ticks: int = 0


class ProcessManager:
    def __init__(self, config_mgr: ConfigManager, win_ctrl: WindowController, layout_calc: LayoutCalculator):
        self.config_mgr = config_mgr
        self.win_ctrl = win_ctrl
        self.layout_calc = layout_calc
        self.quota_svc = QuotaService()

        base_dir = Path(__file__).resolve().parent.parent
        self.profiles_dir = base_dir / "profiles"
        self.logger = ConversationLogger(self.profiles_dir)
        self.history_mgr = SlotHistoryManager(self.profiles_dir)

        slots_cfg = self.config_mgr.config.get("slots", [])
        self.slots: Dict[int, SlotState] = {s["id"]: SlotState(s["id"]) for s in slots_cfg}
        if not self.slots:
            self.slots = {i: SlotState(i) for i in range(1, 13)}
        self._lock = threading.Lock()
        self.maximized_slot_id: Optional[int] = None

    def ensure_slot(self, slot_id: int) -> SlotState:
        with self._lock:
            if slot_id not in self.slots:
                self.slots[slot_id] = SlotState(slot_id)
            return self.slots[slot_id]

    def get_slot_state(self, slot_id: int) -> SlotState:
        return self.ensure_slot(slot_id)

    def _cleanup_slot_orphans(self, slot_id: int):
        """ทำความสะอาดโปรเซสลูกหลานหรือ helper ที่ค้างอยู่ของสล็อตนี้"""
        slot_tag = f"slot_{slot_id}"
        for p in psutil.process_iter(['pid', 'name']):
            try:
                cmd = " ".join(p.cmdline() or []).lower()
                if slot_tag in cmd:
                    if "appdata\\roaming\\antigravity" not in cmd:
                        try:
                            psutil.Process(p.info['pid']).kill()
                        except Exception:
                            pass
            except Exception:
                continue

    def is_running(self, slot_id: int) -> bool:
        """ตรวจสอบว่า Antigravity IDE ประจำสล็อตนี้กำลังทำงานอยู่หรือไม่"""
        state = self.slots[slot_id]

        # 1. ถ้ามี HWND หน้าต่าง แต่หน้าต่างถูกปิดไปแล้ว (ผู้ใช้กด X บนหน้าต่าง IDE)
        if state.ide_hwnd:
            if not self.win_ctrl.is_window_alive(state.ide_hwnd):
                state.ide_hwnd = None
                state.ide_pid = None
                state.ide_proc = None
                self._cleanup_slot_orphans(slot_id)
                state.quota_info = QuotaInfo()
                return False

        # 2. ตรวจสอบว่า Main IDE process ยังมีชีวิตอยู่หรือไม่ (เร็วมาก O(1))
        if state.ide_pid:
            if psutil.pid_exists(state.ide_pid):
                try:
                    proc = psutil.Process(state.ide_pid)
                    if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                        cmd = " ".join(proc.cmdline() or []).lower()
                        # โปรเซสหลักของ IDE ต้องไม่ใช่ child helper ที่มี --type=
                        if "--type=" not in cmd:
                            return True
                except Exception:
                    pass
            # ถ้า PID เดิมตายไปแล้ว ให้เคลียร์ orphans และรีเซ็ตสถานะ
            state.ide_pid = None
            state.ide_hwnd = None
            state.ide_proc = None
            self._cleanup_slot_orphans(slot_id)
            state.quota_info = QuotaInfo()
            return False

        # 3. ค้นหาเฉพาะโปรเซสหลักของ IDE (ต้องมี user-data-dir ของสล็อตนี้ และไม่มี --type=)
        slot_tag = f"slot_{slot_id}"
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if "antigravity" in p.info['name'].lower():
                    cmd = " ".join(p.cmdline() or []).lower()
                    if slot_tag in cmd and "user-data-dir" in cmd and "--type=" not in cmd:
                        state.ide_pid = p.info['pid']
                        return True
            except Exception:
                continue

        state.ide_hwnd = None
        state.ide_pid = None
        state.ide_proc = None
        state.quota_info = QuotaInfo()
        return False

    def refresh_quota(self, slot_id: int) -> QuotaInfo:
        state = self.slots[slot_id]
        if not self.is_running(slot_id):
            state.quota_info = QuotaInfo()
            state.is_generating = False
            return state.quota_info

        if not state.ls_proc or not state.ls_proc.is_running():
            state.ls_proc = self.quota_svc._find_language_server_for_slot(slot_id, state.ide_pid)
            state.last_io_bytes = 0
            state.is_generating = False

        if state.ls_proc and state.ls_proc.is_running():
            try:
                io = state.ls_proc.io_counters()
                total_io = io.read_bytes + io.write_bytes + io.other_bytes
                if state.last_io_bytes > 0:
                    diff = total_io - state.last_io_bytes
                    if diff > 15000:
                        state.high_io_ticks = 2
                        state.low_io_ticks = 0
                    elif diff > 2000:
                        state.high_io_ticks += 1
                        state.low_io_ticks = 0
                    else:
                        state.high_io_ticks = 0
                        state.low_io_ticks += 1
                        
                    if state.high_io_ticks >= 2:
                        state.is_generating = True
                    elif state.low_io_ticks >= 2:
                        state.is_generating = False
                state.last_io_bytes = total_io
            except Exception:
                state.is_generating = False
                state.ls_proc = None
        else:
            state.is_generating = False

        q = self.quota_svc.fetch_slot_quota(slot_id, state.ide_pid, state.ls_proc)
        state.quota_info = q
        if q.connected:
            self.history_mgr.record_quota(slot_id, q)
        return q

    def _format_ts_remaining(self, ts: float, show_days: bool = True) -> str:
        if not ts or ts <= 0:
            return "Ready"
        now = time.time()
        if ts <= now:
            return "Ready"
        sec = int(ts - now)
        days = sec // 86400
        hours = (sec % 86400) // 3600
        mins = (sec % 3600) // 60
        secs = sec % 60
        if show_days and days > 0:
            return f"{days}d {hours:02d}h"
        elif hours > 0:
            return f"{hours}h {mins:02d}m"
        elif mins > 0:
            return f"{mins}m {secs:02d}s"
        else:
            return f"{secs}s"

    def get_slot_display_quota(self, slot_id: int) -> Tuple[QuotaInfo, bool, bool, bool, bool]:
        """
        ส่งคืนข้อมูล Quota สำหรับแสดงผลบนการ์ด:
        - QuotaInfo (ค่าสดหากรันอยู่ หรือค่าล่าสุดที่จำไว้หากปิดอยู่)
        - is_last_used (เป็นสล็อตที่ใช้งานล่าสุดหรือไม่)
        - is_empty (โควตาหมดแล้วหรือไม่ <= 5%)
        - is_cooldown_finished (ปิดอยู่แต่เวลารีเซ็ตครบแล้วตามเวลาจริง ให้ขึ้นตัวเขียวพร้อมใช้งาน)
        - is_generating (กำลังถูกใช้งานเจมิไนอยู่หรือไม่)
        """
        running = self.is_running(slot_id)
        last_used_sid = self.history_mgr.get_last_used_slot_id()
        is_last_used = (last_used_sid == slot_id)
        is_generating = self.ensure_slot(slot_id).is_generating

        if running:
            q = self.refresh_quota(slot_id)
            if q.reset_5h_ts > 0:
                q.reset_5h_str = self._format_ts_remaining(q.reset_5h_ts, show_days=False)
            if q.weekly_ts > 0:
                q.weekly_str = self._format_ts_remaining(q.weekly_ts, show_days=True)
            is_empty = (q.gemini_pct <= 5 and q.rolling_5h_pct <= 5)
            is_cooldown_finished = (q.reset_5h_str == "Ready" and q.reset_5h_ts > 0)
            return q, is_last_used, is_empty, is_cooldown_finished, is_generating

        # หากปิดอยู่: ดึงค่าจากประวัติล่าสุดที่จำไว้ (Offline Display Mode)
        rec = self.history_mgr.get_record(slot_id)
        q = QuotaInfo()
        q.connected = False
        q.email = rec.email
        q.plan = rec.plan
        q.gemini_pct = rec.gemini_pct
        q.rolling_5h_pct = rec.rolling_5h_pct
        q.weekly_ts = rec.weekly_ts
        q.reset_5h_ts = rec.reset_5h_ts

        now = time.time()
        # คำนวณเวลาที่เหลือตามเวลาจริง (Real-time Cooldown Countdown)
        if q.reset_5h_ts > 0:
            if now >= q.reset_5h_ts:
                q.reset_5h_str = "Ready"
            else:
                q.reset_5h_str = self._format_ts_remaining(q.reset_5h_ts, show_days=False)
        else:
            q.reset_5h_str = rec.reset_5h_str

        if q.weekly_ts > 0:
            if now >= q.weekly_ts:
                q.weekly_str = "Ready"
            else:
                q.weekly_str = self._format_ts_remaining(q.weekly_ts, show_days=True)
        else:
            q.weekly_str = rec.weekly_str

        is_empty = (rec.gemini_pct <= 5 and rec.rolling_5h_pct <= 5)
        is_cooldown_finished = False

        # ตรวจสอบว่า cooldown เสร็จแล้วหรือไม่ (เวลาปัจจุบันผ่านเวลา reset ไปแล้ว)
        if q.reset_5h_ts > 0 and now >= q.reset_5h_ts:
            is_cooldown_finished = True
            is_empty = False
            q.reset_5h_str = "Ready"

        return q, is_last_used, is_empty, is_cooldown_finished, False

    def _handle_display1_swap(self, target_slot_id: int):
        """
        สำหรับ Account 7 เป็นต้นไป และ Slot 1 ซึ่งใช้ Display 1 ร่วมกัน:
        เมื่อเปิดหรือแสดงสล็อตหนึ่ง ให้ซ่อน (Hide) สล็อตอื่นในกลุ่ม Display 1 เดียวกัน
        เพื่อไม่ให้หน้าต่างทับซ้อนกัน และสลับกันเปิดปิดตามคำขอ
        """
        if target_slot_id != 1 and target_slot_id < 7:
            return

        display1_sids = [s_id for s_id in self.slots.keys() if s_id == 1 or s_id >= 7]
        for sid in display1_sids:
            if sid != target_slot_id:
                state = self.slots.get(sid)
                if state and state.ide_hwnd and not state.is_hidden:
                    state.is_hidden = True
                    self.win_ctrl.hide_window(state.ide_hwnd)

    def launch_slot(self, slot_id: int):
        """
        สั่งเปิด Antigravity IDE พร้อมผูก Workspace ประจำสล็อตอย่างถาวร
        ทำให้ประวัติการแชท (Chat History) ไม่สูญหายเมื่อปิดแล้วเปิดใหม่
        """
        self.ensure_slot(slot_id)
        if self.is_running(slot_id):
            return

        # สลับปิด/ซ่อนหน้าต่างอื่นที่แชร์ Display 1 เดียวกัน
        self._handle_display1_swap(slot_id)

        cfg = self.config_mgr.config
        paths = self.config_mgr.get_slot_paths(slot_id)
        state = self.slots[slot_id]

        ide_path = cfg.get("ide_path")
        if os.path.exists(ide_path):
            workspace_dir = paths["workspace_dir"]
            os.makedirs(workspace_dir, exist_ok=True)
            os.makedirs(paths["ide_dir"], exist_ok=True)

            # ผูก Workspace ถาวร: เมื่อปิดแล้วเปิดใหม่ แชทและบริบทจะกลับมาครบ 100%
            cmd = [
                ide_path,
                "--user-data-dir", paths["ide_dir"],
                workspace_dir
            ]
            proc = subprocess.Popen(cmd, close_fds=True)
            state.ide_proc = proc
            state.ide_pid = proc.pid
            self.history_mgr.record_launch(slot_id)
            self.logger.log_event(slot_id, "LAUNCH", f"Launched IDE with workspace {workspace_dir} (PID {proc.pid})")
            print(f"[Slot {slot_id}] Antigravity IDE launched with persistent workspace {workspace_dir}")

            threading.Thread(target=self._resolve_slot_after_launch, args=(slot_id,), daemon=True).start()

    def launch_all(self):
        # เลือกรันสล็อตหลักสำหรับหน้าจอ (Display 1 ถึง 6)
        # สำหรับกลุ่ม Display 1 (Slot 1 และ Slot 7+) ให้เลือกรันเพียง 1 สล็อตที่กำลังทำงานอยู่หรือ Slot 1
        active_d1 = 1
        for s_id in self.slots.keys():
            if (s_id == 1 or s_id >= 7) and self.is_running(s_id):
                active_d1 = s_id
                break

        slots_to_run = [active_d1] + [s_id for s_id in range(2, 7) if s_id in self.slots]
        for s_id in slots_to_run:
            self.launch_slot(s_id)
            time.sleep(0.5)

    def stop_slot(self, slot_id: int):
        """ปิด Antigravity IDE ในสล็อตนั้นโดยเฉพาะ"""
        self.ensure_slot(slot_id)
        state = self.slots[slot_id]
        slot_tag = f"slot_{slot_id}"

        # 1. ปิดหน้าต่างนุ่มนวล
        if state.ide_hwnd:
            self.win_ctrl.close_window(state.ide_hwnd)

        # 2. ปิดโปรเซสลูกหลานของสล็อตนี้ทั้งหมด
        pids_to_kill = set()
        if state.ide_pid and psutil.pid_exists(state.ide_pid):
            try:
                parent = psutil.Process(state.ide_pid)
                for child in parent.children(recursive=True):
                    pids_to_kill.add(child.pid)
                pids_to_kill.add(state.ide_pid)
            except Exception:
                pass

        # สแกนหาโปรเซสที่ใช้ user-data-dir ของสล็อตนี้
        for p in psutil.process_iter(['pid', 'name']):
            try:
                cmd = " ".join(p.cmdline() or []).lower()
                if slot_tag in cmd and "appdata\\roaming\\antigravity" not in cmd:
                    pids_to_kill.add(p.info['pid'])
            except Exception:
                continue

        for pid in pids_to_kill:
            try:
                if psutil.pid_exists(pid):
                    p = psutil.Process(pid)
                    p.kill()
            except Exception:
                pass

        self.logger.log_event(slot_id, "STOP", "Stopped slot processes")
        self.history_mgr.record_stop(slot_id)
        state.ide_pid = None
        state.ide_hwnd = None
        state.ide_proc = None
        state.quota_info = QuotaInfo()

    def stop_all(self):
        for s_id in list(self.slots.keys()):
            self.stop_slot(s_id)

    def _resolve_slot_after_launch(self, slot_id: int):
        self.ensure_slot(slot_id)
        state = self.slots[slot_id]
        slot_tag = f"slot_{slot_id}"
        start_time = time.time()

        while time.time() - start_time < 12:
            time.sleep(1.0)
            if not state.ide_hwnd:
                # ค้นหาหน้าต่างที่มี slot_id ใน cmdline หรือชื่อ
                for p in psutil.process_iter(['pid', 'name']):
                    try:
                        if "antigravity" in p.info['name'].lower():
                            cmd = " ".join(p.cmdline() or []).lower()
                            if slot_tag in cmd:
                                pids = self.win_ctrl.get_descendant_pids(p.info['pid'])
                                hwnd = self.win_ctrl.find_window_by_pids(pids)
                                if hwnd:
                                    state.ide_hwnd = hwnd
                                    state.ide_pid = p.info['pid']
                                    print(f"[Slot {slot_id}] Found HWND: {hwnd} for PID {p.info['pid']}")
                                    break
                    except Exception:
                        continue
            if state.ide_hwnd:
                break

        self.refresh_quota(slot_id)
        self.apply_layout()

    def toggle_slot_visibility(self, slot_id: int) -> bool:
        self.ensure_slot(slot_id)
        state = self.slots[slot_id]
        state.is_hidden = not state.is_hidden

        if state.is_hidden:
            if state.ide_hwnd:
                self.win_ctrl.hide_window(state.ide_hwnd)
            if self.maximized_slot_id == slot_id:
                self.maximized_slot_id = None
        else:
            self._handle_display1_swap(slot_id)
            if state.ide_hwnd:
                self.win_ctrl.show_window(state.ide_hwnd)

        self.apply_layout()
        return not state.is_hidden

    def bring_slot_to_front(self, slot_id: int, force_max: Optional[bool] = None) -> bool:
        """
        เรียกหน้าต่างงานของสล็อตนั้นขึ้นมาด้านหน้าสุด (Unhide + Bring to Top)
        พร้อมสลับกลุ่ม Display 1 อัตโนมัติหากเป็นสล็อต 1 หรือสล็อต 7+
        
        force_max:
        - True: สั่ง Maximize เต็มหน้าจอทันที
        - False: สั่งโหมด Grid หน้าจอเล็ก (Tile Mode)
        - None: รักษาโหมดเดิม (ถ้ากำลัง Max อยู่ ให้ Max สล็อตนี้, ถ้ากำลัง Grid ให้คง Grid)
        """
        self.ensure_slot(slot_id)
        if not self.is_running(slot_id):
            return False

        state = self.slots[slot_id]

        # 1. จัดการสล็อตกลุ่ม Display 1 (สล็อต 1, 7+)
        self._handle_display1_swap(slot_id)

        # 2. ถ้ายกเลิกซ่อน (Unhide)
        if state.is_hidden:
            state.is_hidden = False
            if state.ide_hwnd:
                self.win_ctrl.show_window(state.ide_hwnd)

        # 3. ถ้าไม่มี HWND หรือ HWND หลุด ให้ลองค้นหาใหม่อีกครั้ง
        if not state.ide_hwnd or not self.win_ctrl.is_window_alive(state.ide_hwnd):
            if state.ide_pid:
                pids = self.win_ctrl.get_descendant_pids(state.ide_pid)
                state.ide_hwnd = self.win_ctrl.find_window_by_pids(pids)

        # 4. จัดการเรื่องโหมด Max vs โหมด Grid เล็ก อย่างอิสระ
        if force_max is True:
            self.maximized_slot_id = slot_id
            for s_id, s in self.slots.items():
                if s_id != slot_id and s.ide_hwnd:
                    self.win_ctrl.hide_window(s.ide_hwnd)
        elif force_max is False:
            if self.maximized_slot_id is not None:
                self.maximized_slot_id = None
                for s_id, s in self.slots.items():
                    if not s.is_hidden and s.ide_hwnd:
                        self.win_ctrl.show_window(s.ide_hwnd)
        else:
            # force_max is None:
            # ถ้าอยู่ในโหมด Max หน้าจออยู่แล้ว ให้สลับสล็อต Max มาเป็นสล็อตนี้โดยไม่หลุดเป็นจอเล็ก!
            if self.maximized_slot_id is not None:
                self.maximized_slot_id = slot_id
                for s_id, s in self.slots.items():
                    if s_id != slot_id and s.ide_hwnd:
                        self.win_ctrl.hide_window(s.ide_hwnd)

        # 5. แสดงและดึงหน้าต่างมาข้างหน้าสุด
        if state.ide_hwnd:
            self.win_ctrl.show_window(state.ide_hwnd)
            self.win_ctrl.bring_to_front(state.ide_hwnd)
            self.apply_layout()
            return True
        return False

    def toggle_slot_maximize(self, slot_id: int) -> bool:
        if self.maximized_slot_id == slot_id:
            self.maximized_slot_id = None
            for s_id, s in self.slots.items():
                if not s.is_hidden and s.ide_hwnd:
                    self.win_ctrl.show_window(s.ide_hwnd)
            self.apply_layout()
            return False
        else:
            self.maximized_slot_id = slot_id
            for s_id, s in self.slots.items():
                if s_id != slot_id and s.ide_hwnd:
                    self.win_ctrl.hide_window(s.ide_hwnd)
            self.apply_layout()
            return True

    def apply_layout(self, reserve_deck_width: int = 370):
        work_area = self.layout_calc.get_working_area()

        if self.maximized_slot_id is not None:
            max_state = self.slots[self.maximized_slot_id]
            ide_aw = max(600, work_area["width"] - reserve_deck_width)
            if max_state.ide_hwnd:
                self.win_ctrl.show_window(max_state.ide_hwnd)
                self.win_ctrl.set_window_bounds(max_state.ide_hwnd, work_area["x"], work_area["y"], ide_aw, work_area["height"])
            return

        visible_slot_ids = [s_id for s_id, s in self.slots.items() if not s.is_hidden]
        slot_rects = self.layout_calc.compute_slot_rects(visible_slot_ids, work_area, reserve_deck_width=reserve_deck_width)

        for s_id in visible_slot_ids:
            if s_id not in slot_rects:
                continue
            r = slot_rects[s_id]
            state = self.slots[s_id]
            if state.ide_hwnd:
                self.win_ctrl.show_window(state.ide_hwnd)
                self.win_ctrl.set_window_bounds(state.ide_hwnd, r["x"], r["y"], r["width"], r["height"])
