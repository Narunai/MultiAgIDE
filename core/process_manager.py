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

        self.slots: Dict[int, SlotState] = {i: SlotState(i) for i in range(1, 7)}
        self._lock = threading.Lock()
        self.maximized_slot_id: Optional[int] = None

    def get_slot_state(self, slot_id: int) -> SlotState:
        return self.slots[slot_id]

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
            return state.quota_info

        q = self.quota_svc.fetch_slot_quota(slot_id, state.ide_pid)
        state.quota_info = q
        if q.connected:
            self.history_mgr.record_quota(slot_id, q)
        return q

    def get_slot_display_quota(self, slot_id: int) -> Tuple[QuotaInfo, bool, bool]:
        """
        ส่งคืนข้อมูล Quota สำหรับแสดงผลบนการ์ด:
        - QuotaInfo (ค่าสดหากรันอยู่ หรือค่าล่าสุดที่จำไว้หากปิดอยู่)
        - is_last_used (เป็นสล็อตที่ใช้งานล่าสุดหรือไม่)
        - is_empty (โควตาหมดแล้วหรือไม่ <= 5%)
        """
        running = self.is_running(slot_id)
        last_used_sid = self.history_mgr.get_last_used_slot_id()
        is_last_used = (last_used_sid == slot_id)

        if running:
            q = self.refresh_quota(slot_id)
            is_empty = (q.gemini_pct <= 5 and q.rolling_5h_pct <= 5)
            return q, is_last_used, is_empty

        # หากปิดอยู่: ดึงค่าจากประวัติล่าสุดที่จำไว้ (Offline Display Mode)
        rec = self.history_mgr.get_record(slot_id)
        q = QuotaInfo()
        q.connected = False
        q.email = rec.email
        q.plan = rec.plan
        q.gemini_pct = rec.gemini_pct
        q.rolling_5h_pct = rec.rolling_5h_pct
        q.weekly_str = rec.weekly_str
        q.reset_5h_str = rec.reset_5h_str
        is_empty = (rec.gemini_pct <= 5 and rec.rolling_5h_pct <= 5)
        return q, is_last_used, is_empty

    def launch_slot(self, slot_id: int):
        """
        สั่งเปิด Antigravity IDE พร้อมผูก Workspace ประจำสล็อตอย่างถาวร
        ทำให้ประวัติการแชท (Chat History) ไม่สูญหายเมื่อปิดแล้วเปิดใหม่
        """
        if self.is_running(slot_id):
            return

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
        visible_slots = [s["id"] for s in self.config_mgr.get_visible_slots()]
        for s_id in visible_slots:
            self.launch_slot(s_id)
            time.sleep(0.5)

    def stop_slot(self, slot_id: int):
        """ปิด Antigravity IDE ในสล็อตนั้นโดยเฉพาะ"""
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
        for s_id in range(1, 7):
            self.stop_slot(s_id)

    def _resolve_slot_after_launch(self, slot_id: int):
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
        state = self.slots[slot_id]
        state.is_hidden = not state.is_hidden

        if state.is_hidden:
            if state.ide_hwnd:
                self.win_ctrl.hide_window(state.ide_hwnd)
            if self.maximized_slot_id == slot_id:
                self.maximized_slot_id = None
        else:
            if state.ide_hwnd:
                self.win_ctrl.show_window(state.ide_hwnd)

        self.apply_layout()
        return not state.is_hidden

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
