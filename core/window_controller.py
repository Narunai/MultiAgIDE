import time
from typing import List, Dict, Optional, Set
import win32gui
import win32con
import win32process
import psutil


class WindowController:
    """
    Win32 API Wrapper สำหรับควบคุมหน้าต่าง Antigravity IDE และ Google Chrome
    """

    def __init__(self):
        pass

    def get_descendant_pids(self, root_pid: int) -> Set[int]:
        """รวบรวม PID ของ root process และ child processes ทั้งหมด"""
        pids = {root_pid}
        try:
            parent = psutil.Process(root_pid)
            for child in parent.children(recursive=True):
                pids.add(child.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return pids

    def find_window_by_pids(self, target_pids: Set[int], title_filter: Optional[str] = None) -> Optional[int]:
        """ค้นหา HWND ของหน้าต่างหลักที่มองเห็นได้ จากกลุ่ม PID"""
        found_hwnds = []

        def enum_callback(hwnd, _):
            if not win32gui.IsWindow(hwnd):
                return True
            if not win32gui.IsWindowVisible(hwnd):
                return True

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid in target_pids:
                # Check rect size to exclude invisible/0-size helper windows
                rect = win32gui.GetWindowRect(hwnd)
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                if w > 100 and h > 100:
                    title = win32gui.GetWindowText(hwnd)
                    if title_filter:
                        if title_filter.lower() in title.lower():
                            found_hwnds.append((hwnd, w * h))
                    else:
                        found_hwnds.append((hwnd, w * h))
            return True

        try:
            win32gui.EnumWindows(enum_callback, None)
        except Exception:
            pass

        if not found_hwnds:
            return None

        # Sort by window area descending (หน้าต่างโปรแกรมหลักมักจะมีขนาดใหญ่ที่สุด)
        found_hwnds.sort(key=lambda x: x[1], reverse=True)
        return found_hwnds[0][0]

    def is_window_alive(self, hwnd: Optional[int]) -> bool:
        """ตรวจสอบว่าหน้าต่าง HWND ยังคงมีอยู่จริงในระบบหรือไม่"""
        if not hwnd:
            return False
        return bool(win32gui.IsWindow(hwnd))

    def set_window_bounds(self, hwnd: int, x: int, y: int, width: int, height: int):
        """ย้ายและปรับขนาดหน้าต่างไปยังพิกัดเป้าหมาย"""
        if not win32gui.IsWindow(hwnd):
            return False

        try:
            # If window is minimized, restore it first
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            flags = (
                win32con.SWP_NOZORDER
                | win32con.SWP_SHOWWINDOW
                | win32con.SWP_FRAMECHANGED
            )
            win32gui.SetWindowPos(hwnd, 0, x, y, width, height, flags)
            return True
        except Exception as e:
            print(f"Error setting window bounds for HWND {hwnd}: {e}")
            return False

    def hide_window(self, hwnd: int):
        """ซ่อนหน้าต่างชั่วคราว"""
        if win32gui.IsWindow(hwnd):
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                return True
            except Exception:
                pass
        return False

    def show_window(self, hwnd: int):
        """แสดงหน้าต่างกลับมา"""
        if win32gui.IsWindow(hwnd):
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                return True
            except Exception:
                pass
        return False

    def bring_to_front(self, hwnd: int):
        """ดึงหน้าต่างมาแสดงข้างหน้าสุด (Foreground)"""
        if win32gui.IsWindow(hwnd):
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                return True
            except Exception:
                pass
        return False

    def close_window(self, hwnd: int):
        """ส่งสัญญาณปิดหน้าต่างแบบนุ่มนวล (WM_CLOSE)"""
        if win32gui.IsWindow(hwnd):
            try:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return True
            except Exception:
                pass
        return False
