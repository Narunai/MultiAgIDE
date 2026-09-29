"""
Ultra-Minimal Modern Dark-Gray Theme for MultiAgIDE Studio
Design: Pure text-based typography, zero emoji icons, flat, borderless, matte dark-gray.
"""

DARK_THEME_QSS = """
/* Global Minimal Dark-Gray */
QWidget {
    background-color: #121214;
    color: #d4d4d8;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 11px;
    border: none;
    outline: none;
}

QMainWindow {
    background-color: #121214;
}

/* Header Container */
QFrame#HeaderCard {
    background-color: #18181b;
    border-radius: 6px;
    padding: 6px 8px;
}

QLabel#AppTitle {
    color: #38bdf8;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.5px;
    background: transparent;
}

/* Slot Cards - Flat, Clean, Borderless */
QFrame#SlotCard {
    background-color: #18181b;
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
}

QFrame#SlotCard:hover {
    background-color: #202024;
}

/* Quota Pill - Flat Dark Strip */
QFrame#QuotaPill {
    background-color: #0f0f11;
    border: none;
    border-radius: 4px;
    padding: 2px 6px;
}

QLabel {
    background: transparent;
    padding: 0px;
    margin: 0px;
}

/* Status Labels */
QLabel#BadgeRunning {
    color: #4ade80;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.5px;
    background: transparent;
}

QLabel#BadgeStopped {
    color: #52525b;
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.5px;
    background: transparent;
}

/* Text Buttons - Minimal Flat Style */
QPushButton {
    background-color: #27272a;
    color: #d4d4d8;
    border: none;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #3f3f46;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #18181b;
}

/* Primary Action Buttons */
QPushButton.PrimaryBtn, QPushButton[class="PrimaryBtn"] {
    background-color: #2563eb;
    color: #ffffff;
}

QPushButton.PrimaryBtn:hover, QPushButton[class="PrimaryBtn"]:hover {
    background-color: #1d4ed8;
}

/* Success Launch Button */
QPushButton.SuccessBtn, QPushButton[class="SuccessBtn"] {
    background-color: #14532d;
    color: #4ade80;
}

QPushButton.SuccessBtn:hover, QPushButton[class="SuccessBtn"]:hover {
    background-color: #166534;
    color: #ffffff;
}

/* Stop Danger Button */
QPushButton.DangerBtn, QPushButton[class="DangerBtn"] {
    background-color: #7f1d1d;
    color: #f87171;
}

QPushButton.DangerBtn:hover, QPushButton[class="DangerBtn"]:hover {
    background-color: #991b1b;
    color: #ffffff;
}

/* Header Grid Preset Buttons */
QPushButton.PresetBtn, QPushButton[class="PresetBtn"] {
    background-color: #202024;
    color: #a1a1aa;
    border-radius: 3px;
    padding: 2px 5px;
    font-size: 10px;
    font-weight: 600;
}

QPushButton.PresetBtn:hover, QPushButton[class="PresetBtn"]:hover {
    background-color: #38bdf8;
    color: #09090b;
}

/* Minimal Text Inputs */
QLineEdit {
    background-color: transparent;
    border: none;
    color: #f4f4f5;
    font-size: 11px;
    padding: 0px 2px;
}

QLineEdit:focus {
    background-color: #27272a;
    border-radius: 3px;
}

/* Scroll Area - Zero Scrollbar */
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical, QScrollBar:horizontal {
    width: 0px;
    height: 0px;
}
"""
