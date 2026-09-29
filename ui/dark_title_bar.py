"""
Windows DWM Dark Title Bar utility for MultiAgIDE Studio.
Enables immersive dark mode on Windows 10 (1809+) and Windows 11,
and custom dark caption / text / border colors on Windows 11.
"""
import sys
import ctypes
from ctypes import c_int, byref, sizeof
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt


def apply_dark_title_bar(window):
    """
    Applies Windows DWM Immersive Dark Mode and matches the title bar
    color directly with MultiAgIDE's ultra-minimal dark theme (#121214).
    """
    if sys.platform != "win32":
        return

    try:
        hwnd = int(window.winId())
        if not hwnd:
            return

        dwmapi = ctypes.windll.dwmapi

        # 1. DWMWA_USE_IMMERSIVE_DARK_MODE
        # 20 for Windows 10 20H1+ and Windows 11
        # 19 for Windows 10 1809-1909
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19

        val = c_int(1)
        res = dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, byref(val), sizeof(val)
        )
        if res != 0:
            dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, byref(val), sizeof(val)
            )

        # 2. Windows 11 Custom Title Bar Colors (Build 22000+)
        # COLORREF in Windows is 0x00bbggrr (Blue, Green, Red)

        # DWMWA_CAPTION_COLOR = 35 -> #121214 (R=12, G=12, B=14) -> 0x00141212
        caption_color = c_int(0x00141212)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 35, byref(caption_color), sizeof(caption_color)
        )

        # DWMWA_TEXT_COLOR = 36 -> #d4d4d8 (R=d4, G=d4, B=d8) -> 0x00d8d4d4
        text_color = c_int(0x00d8d4d4)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 36, byref(text_color), sizeof(text_color)
        )

        # DWMWA_BORDER_COLOR = 34 -> #27272a (R=27, G=27, B=2a) -> 0x002a2727
        border_color = c_int(0x002a2727)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 34, byref(border_color), sizeof(border_color)
        )
    except Exception:
        pass


def create_minimal_app_icon() -> QIcon:
    """
    Creates a sleek, minimal typography-based application icon
    (Zero-emoji, dark rounded tile with cyan 'M') to replace
    the generic default Qt window icon.
    """
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Dark rounded background matching theme
    painter.setBrush(QColor("#18181b"))
    painter.setPen(QColor("#27272a"))
    painter.drawRoundedRect(1, 1, 30, 30, 6, 6)

    # Cyan typography "M"
    painter.setPen(QColor("#38bdf8"))
    font = QFont("Segoe UI", 13, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "M")
    painter.end()

    return QIcon(pixmap)
