import os
import subprocess
import time
import threading
import ctypes
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import psutil

from .config_manager import ConfigManager
from .window_controller import WindowController
from .layout_calculator import LayoutCalculator
from .quota_service import QuotaService, QuotaInfo
from .conversation_logger import ConversationLogger
from .slot_history_manager import SlotHistoryManager, SlotHistoryRecord

kernel32 = ctypes.windll.kernel32
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259


def _is_pid_alive(pid: Optional[int]) -> bool:
    """ตรวจสอบว่า PID ยังคงทำงานอยู่หรือไม่ ผ่าน Win32 API ความเร็วสูง O(1) <0.001 ms"""
    if not pid or pid <= 0:
        return False
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    exit_code = ctypes.c_ulong()
    success = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
    kernel32.CloseHandle(handle)
    return bool(success and exit_code.value == STILL_ACTIVE)


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

        # เริ่มต้น Background Worker ทำหน้าที่สแกน instance และดึง Quota แบบ Asynchronous นอก UI Thread
        self._bg_thread = threading.Thread(target=self._bg_monitor_loop, daemon=True)
        self._bg_thread.start()

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

    def _cleanup_slot_orphans_async(self, slot_id: int):
        threading.Thread(target=self._cleanup_slot_orphans, args=(slot_id,), daemon=True).start()

    def is_running(self, slot_id: int) -> bool:
        """
        ตรวจสอบว่า Antigravity IDE ประจำสล็อตนี้กำลังทำงานอยู่หรือไม่
        ความเร็ว O(1) ไม่บล็อก UI Thread (<0.001 ms)
        """
        state = self.slots.get(slot_id)
        if not state:
            return False

        # 1. ถ้ามี HWND หน้าต่าง แต่หน้าต่างถูกปิดไปแล้ว (ผู้ใช้กด X บนหน้าต่าง IDE)
        if state.ide_hwnd:
            if not self.win_ctrl.is_window_alive(state.ide_hwnd):
                state.ide_hwnd = None
                state.ide_pid = None
                state.ide_proc = None
                state.quota_info = QuotaInfo()
                state.is_generating = False
                self._cleanup_slot_orphans_async(slot_id)
                return False

        # 2. ถ้าเปิดด้วย subprocess.Popen ให้ตรวจสอบด้วย poll() ทันที
        if state.ide_proc is not None:
            if state.ide_proc.poll() is not None:
                state.ide_proc = None
                state.ide_pid = None
                state.ide_hwnd = None
                state.quota_info = QuotaInfo()
                state.is_generating = False
                self._cleanup_slot_orphans_async(slot_id)
                return False
            return True

        # 3. ถ้ามี PID ให้ตรวจสอบผ่าน Win32 API ความเร็วสูง (<0.001 ms)
        if state.ide_pid is not None:
            if _is_pid_alive(state.ide_pid):
                return True
            state.ide_pid = None
            state.ide_hwnd = None
            state.ide_proc = None
            state.quota_info = QuotaInfo()
            state.is_generating = False
            self._cleanup_slot_orphans_async(slot_id)
            return False

        return False

    def _scan_external_instances(self):
        """
        สแกนโปรเซสในระบบใน Background Daemon Thread
        เพื่อตรวจจับสล็อตที่อาจเปิดค้างอยู่หรือเปิดจาก session ก่อนหน้า
        กฎเหล็ก: ห้ามแตะต้องหรือจับคู่กับ Antigravity ปกติของเครื่อง (AppData\\Roaming\\Antigravity IDE) เด็ดขาด
        """
        found_pids = {}
        for p in psutil.process_iter(['pid', 'name']):
            try:
                name = p.info['name'] or ""
                if "antigravity" in name.lower():
                    cmd = " ".join(p.cmdline() or []).lower()
                    if "appdata\\roaming\\antigravity" in cmd:
                        continue
                    if "--user-data-dir" in cmd and "--type=" not in cmd:
                        for slot_id in list(self.slots.keys()):
                            slot_tag = f"slot_{slot_id}"
                            if slot_tag in cmd:
                                found_pids[slot_id] = p.info['pid']
            except Exception:
                continue

        for slot_id, pid in found_pids.items():
            state = self.ensure_slot(slot_id)
            if state.ide_pid is None or not _is_pid_alive(state.ide_pid):
                state.ide_pid = pid
                if not state.ide_hwnd or not self.win_ctrl.is_window_alive(state.ide_hwnd):
                    pids = self.win_ctrl.get_descendant_pids(pid)
                    hwnd = self.win_ctrl.find_window_by_pids(pids)
                    if hwnd:
                        state.ide_hwnd = hwnd

    def _bg_refresh_slot(self, slot_id: int):
        """ดึง Quota และสถานะการเจนเนอเรตคำตอบใน Background Thread"""
        state = self.slots.get(slot_id)
        if not state or not self.is_running(slot_id):
            return

        # 1. ค้นหา Language Server Process หากยังไม่มี
        if not state.ls_proc or not state.ls_proc.is_running():
            state.ls_proc = self.quota_svc._find_language_server_for_slot(slot_id, state.ide_pid)
            state.last_io_bytes = 0
            state.is_generating = False

        # 2. ตรวจสอบ I/O bytes เพื่อดูว่ากำลัง Generating หรือไม่
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

        # 3. ดึง Quota ข้อมูลสดผ่าน HTTP (เบื้องหลัง)
        try:
            q = self.quota_svc.fetch_slot_quota(slot_id, state.ide_pid, state.ls_proc)
            state.quota_info = q
            if q.connected:
                self.history_mgr.record_quota(slot_id, q)
        except Exception:
            pass

    def _bg_monitor_loop(self):
        """
        Background Daemon Thread:
        ทำงานแบบ Asynchronous นอก Qt GUI Thread 100%
        """
        last_scan_time = 0.0
        while True:
            try:
                now = time.time()
                # สแกนหา instance ภายนอกทุก 4 วินาที
                if now - last_scan_time >= 4.0:
                    self._scan_external_instances()
                    last_scan_time = now

                # อัปเดตข้อมูล Quota และ I/O ของสล็อตที่กำลังรันอยู่
                for slot_id in list(self.slots.keys()):
                    if self.is_running(slot_id):
                        self._bg_refresh_slot(slot_id)

            except Exception:
                pass

            time.sleep(2.0)

    def refresh_quota(self, slot_id: int) -> QuotaInfo:
        """รีเฟรช Quota ทันที (สามารถเรียกใช้งานได้แบบ On-Demand)"""
        self._bg_refresh_slot(slot_id)
        state = self.slots.get(slot_id)
        return state.quota_info if state else QuotaInfo()

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
        - ทำงานในหน่วยความจำ 100% ไม่ยิง HTTP ไม่สแกนโปรเซส (<0.001 ms)
        """
        running = self.is_running(slot_id)
        last_used_sid = self.history_mgr.get_last_used_slot_id()
        is_last_used = (last_used_sid == slot_id)
        state = self.ensure_slot(slot_id)
        is_generating = state.is_generating

        if running:
            # ใช้ข้อมูล QuotaInfo ที่แคชไว้จาก Background Worker
            q = state.quota_info
            # Fallback หากเพิ่งเปิดโปรเซสและ Quota ยังไม่ได้เชื่อมต่อ
            if not q.connected:
                rec = self.history_mgr.get_record(slot_id)
                if rec and rec.email and rec.email not in ("offline", "Unknown"):
                    q.email = rec.email
                    if q.gemini_pct == 0 and rec.gemini_pct > 0:
                        q.gemini_pct = rec.gemini_pct
                        q.rolling_5h_pct = rec.rolling_5h_pct
                        q.weekly_ts = rec.weekly_ts
                        q.reset_5h_ts = rec.reset_5h_ts

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

    def get_slot_user_email(self, slot_id: int) -> Optional[str]:
        """
        ดึงอีเมลของผู้ใช้ที่ล็อกอินในสล็อตนี้ (หากยังไม่เคยล็อกอินหรือเป็นออฟไลน์ จะส่งกลับ None)
        """
        # 1. ตรวจสอบจาก QuotaInfo สดของโปรเซสที่กำลังรันอยู่
        state = self.slots.get(slot_id)
        if state and state.quota_info and state.quota_info.email:
            e = state.quota_info.email.strip()
            if e and e.lower() not in ("offline", "unknown", "none", "--"):
                return e

        # 2. ตรวจสอบจากประวัติการใช้งานใน history_mgr
        rec = self.history_mgr.get_record(slot_id)
        if rec and rec.email:
            e = rec.email.strip()
            if e and e.lower() not in ("offline", "unknown", "none", "--"):
                return e

        # 3. ตรวจสอบจากแคชของ quota_svc
        q_cache = self.quota_svc.cache.get(slot_id)
        if q_cache and q_cache.email:
            e = q_cache.email.strip()
            if e and e.lower() not in ("offline", "unknown", "none", "--"):
                return e

        return None

    def launch_slot(self, slot_id: int, swap_d1: bool = True):
        """
        สั่งเปิด Antigravity IDE พร้อมผูก Workspace ประจำสล็อตอย่างถาวร
        ทำให้ประวัติการแชท (Chat History) ไม่สูญหายเมื่อปิดแล้วเปิดใหม่
        """
        self.ensure_slot(slot_id)
        if self.is_running(slot_id):
            return

        # สลับปิด/ซ่อนหน้าต่างอื่นที่แชร์ Display 1 เดียวกัน (หากสั่งเปิดรายสล็อต)
        if swap_d1:
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

    def launch_all(self, on_done_callback=None):
        """
        สตาร์ททุกสล็อตที่มี user เคยล็อกอินไว้ และไม่ซ้ำกัน
        - รันแบบ Asynchronous ใน Daemon Thread ไม่บล็อก UI Thread
        """
        def _runner():
            slots_cfg = self.config_mgr.config.get("slots", [])
            sorted_slots = sorted(slots_cfg, key=lambda s: s["id"])

            seen_emails = set()
            slots_to_run = []

            for s in sorted_slots:
                sid = s["id"]
                email = self.get_slot_user_email(sid)
                if not email:
                    continue  # ข้ามสล็อตที่ยังไม่มี user ล็อกอิน (offline)

                norm_email = email.lower()
                if norm_email in seen_emails:
                    print(f"[Run All] Slot #{sid} has duplicate user ({email}), skipping.")
                    continue  # ซ้ำกัน ให้เปิดแค่อันแรกที่พบ

                seen_emails.add(norm_email)
                slots_to_run.append(sid)

            # กรณีพิเศษ: หากยังไม่มีสล็อตใดเคยล็อกอินเลย (เช่น ติดตั้งใหม่) ให้เปิดสล็อตแรก
            if not slots_to_run and sorted_slots:
                first_sid = sorted_slots[0]["id"]
                slots_to_run = [first_sid]

            print(f"[Run All] Launching unique user slots: {slots_to_run}")
            self.logger.log_event(0, "RUN_ALL", f"Launching unique logged-in slots: {slots_to_run}")

            for s_id in slots_to_run:
                self.launch_slot(s_id, swap_d1=False)
                time.sleep(0.5)

            if on_done_callback:
                on_done_callback()

        threading.Thread(target=_runner, daemon=True).start()

    def stop_slot(self, slot_id: int):
        """ปิด Antigravity IDE ในสล็อตนั้นโดยเฉพาะ (ตอบสนองทันที 0ms)"""
        self.ensure_slot(slot_id)
        state = self.slots[slot_id]
        slot_tag = f"slot_{slot_id}"
        old_pid = state.ide_pid
        old_hwnd = state.ide_hwnd

        # รีเซ็ตสถานะในหน่วยความจำทันทีเพื่อให้ UI เปลี่ยนเป็น STOPPED แบบ 0-delay
        state.ide_pid = None
        state.ide_hwnd = None
        state.ide_proc = None
        state.quota_info = QuotaInfo()
        state.is_generating = False

        self.logger.log_event(slot_id, "STOP", "Stopped slot processes")
        self.history_mgr.record_stop(slot_id)

        def _do_kill():
            # 1. ปิดหน้าต่างนุ่มนวล
            if old_hwnd and self.win_ctrl.is_window_alive(old_hwnd):
                self.win_ctrl.close_window(old_hwnd)

            # 2. ปิดโปรเซสลูกหลานของสล็อตนี้
            pids_to_kill = set()
            if old_pid and _is_pid_alive(old_pid):
                try:
                    parent = psutil.Process(old_pid)
                    for child in parent.children(recursive=True):
                        pids_to_kill.add(child.pid)
                    pids_to_kill.add(old_pid)
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
                    if _is_pid_alive(pid):
                        p = psutil.Process(pid)
                        p.kill()
                except Exception:
                    pass

        threading.Thread(target=_do_kill, daemon=True).start()

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
