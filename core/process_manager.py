import os
import subprocess
import time
import threading
from typing import Dict, List, Optional
from pathlib import Path
import psutil

from .config_manager import ConfigManager
from .window_controller import WindowController
from .layout_calculator import LayoutCalculator
from .quota_service import QuotaService, QuotaInfo
from .conversation_logger import ConversationLogger


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

        self.slots: Dict[int, SlotState] = {i: SlotState(i) for i in range(1, 7)}
        self._lock = threading.Lock()
        self.maximized_slot_id: Optional[int] = None

    def get_slot_state(self, slot_id: int) -> SlotState:
        return self.slots[slot_id]

    def is_running(self, slot_id: int) -> bool:
        """ตรวจสอบว่า Antigravity IDE ในสล็อตนี้กำลังทำงานอยู่หรือไม่"""
        state = self.slots[slot_id]
        if state.ide_pid and psutil.pid_exists(state.ide_pid):
            try:
                proc = psutil.Process(state.ide_pid)
                running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
                if running:
                    return True
            except Exception:
                pass
        state.ide_hwnd = None
        return False

    def refresh_quota(self, slot_id: int) -> QuotaInfo:
        state = self.slots[slot_id]
        q = self.quota_svc.fetch_slot_quota(slot_id, state.ide_pid)
        state.quota_info = q
        return q

    def launch_slot(self, slot_id: int):
        """
        สั่งเปิด Antigravity IDE แยกทั้ง User Data Directory และ Chat/Conversation Environment
        100% Isolated: แยก Session, บัญชี Google, ประวัติการแชท (Conversations) และ Brain ออกจากกันเด็ดขาด
        """
        if self.is_running(slot_id):
            return

        cfg = self.config_mgr.config
        paths = self.config_mgr.get_slot_paths(slot_id)
        state = self.slots[slot_id]

        ide_path = cfg.get("ide_path")
        if os.path.exists(ide_path):
            # แยก USERPROFILE เพื่อให้โฟลเดอร์ .gemini/ และประวัติแชทเก็บแยกเด็ดขาดในแต่ละสล็อต
            slot_dir = self.profiles_dir / f"slot_{slot_id}"
            slot_home = slot_dir / "home"
            slot_home.mkdir(parents=True, exist_ok=True)

            custom_env = os.environ.copy()
            custom_env["USERPROFILE"] = str(slot_home)
            custom_env["HOME"] = str(slot_home)
            custom_env["XDG_DATA_HOME"] = str(slot_home / ".local" / "share")
            custom_env["XDG_CONFIG_HOME"] = str(slot_home / ".config")

            cmd = [
                ide_path,
                "--user-data-dir", paths["ide_dir"],
                "-n"
            ]
            proc = subprocess.Popen(cmd, env=custom_env, close_fds=True)
            state.ide_proc = proc
            state.ide_pid = proc.pid
            self.logger.log_event(slot_id, "LAUNCH", f"Launched isolated IDE with PID {proc.pid}")
            print(f"[Slot {slot_id}] Antigravity IDE launched with PID {proc.pid} (Isolated Home: {slot_home})")

            # Start thread to resolve HWND and initial Quota
            threading.Thread(target=self._resolve_slot_after_launch, args=(slot_id,), daemon=True).start()

    def launch_all(self):
        visible_slots = [s["id"] for s in self.config_mgr.get_visible_slots()]
        for s_id in visible_slots:
            self.launch_slot(s_id)
            time.sleep(0.4)

    def stop_slot(self, slot_id: int):
        """ปิด Antigravity IDE ในสล็อตนั้น"""
        state = self.slots[slot_id]
        if state.ide_hwnd:
            self.win_ctrl.close_window(state.ide_hwnd)
        if state.ide_pid and psutil.pid_exists(state.ide_pid):
            try:
                parent = psutil.Process(state.ide_pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
            except Exception:
                pass
        self.logger.log_event(slot_id, "STOP", "Stopped Antigravity IDE")
        state.ide_pid = None
        state.ide_hwnd = None
        state.ide_proc = None
        state.quota_info.connected = False

    def stop_all(self):
        for s_id in range(1, 7):
            self.stop_slot(s_id)

    def _resolve_slot_after_launch(self, slot_id: int):
        state = self.slots[slot_id]
        start_time = time.time()

        while time.time() - start_time < 12:
            time.sleep(1.0)
            if state.ide_pid and not state.ide_hwnd:
                pids = self.win_ctrl.get_descendant_pids(state.ide_pid)
                hwnd = self.win_ctrl.find_window_by_pids(pids, title_filter="Antigravity")
                if not hwnd:
                    hwnd = self.win_ctrl.find_window_by_pids(pids)
                if hwnd:
                    state.ide_hwnd = hwnd
                    print(f"[Slot {slot_id}] Found IDE HWND: {hwnd}")
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
