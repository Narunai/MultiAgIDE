"""
Modern Dark Glassmorphic Theme for MultiAgIDE Studio
"""

DARK_THEME_QSS = """
/* Global Defaults - Ensures NO white backgrounds anywhere */
QWidget {
    background-color: #0b0f17;
    color: #f1f5f9;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #0b0f17;
}

/* Scroll Area & Viewport */
QScrollArea {
    border: none;
    background-color: #0b0f17;
}

QScrollArea > QWidget > QWidget {
    background-color: #0b0f17;
}

QScrollBar:vertical {
    background: #0b0f17;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #1e293b;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #334155;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Header & Banner */
QFrame#HeaderCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #111827, stop:1 #1e1b4b);
    border: 1px solid #312e81;
    border-radius: 12px;
    padding: 10px;
}

QLabel#AppTitle {
    color: #38bdf8;
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 0.5px;
    background: transparent;
}

QLabel#AppSubtitle {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 400;
    background: transparent;
}

/* Slot Cards - Multiple selectors for 100% PySide6 compatibility */
QFrame#SlotCard, QFrame.SlotCard, QFrame[class="SlotCard"] {
    background-color: #131b29;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 8px;
}

QFrame#SlotCard:hover, QFrame.SlotCard:hover {
    border: 1px solid #38bdf8;
    background-color: #162032;
}

/* Quota Pill */
QFrame#QuotaPill {
    background-color: #0a0e14;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 6px;
}

QLabel {
    background: transparent;
}

/* Status Badges */
QLabel[class="BadgeRunning"], QLabel.BadgeRunning {
    background-color: #064e3b;
    color: #34d399;
    border: 1px solid #059669;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}

QLabel[class="BadgeStopped"], QLabel.BadgeStopped {
    background-color: #1e293b;
    color: #94a3b8;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 500;
}

/* Buttons */
QPushButton {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #273549;
    border-color: #475569;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #0f172a;
}

/* Primary Action Buttons */
QPushButton[class="PrimaryBtn"], QPushButton.PrimaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #4f46e5);
    border: 1px solid #3b82f6;
    color: #ffffff;
    font-weight: bold;
}

QPushButton[class="PrimaryBtn"]:hover, QPushButton.PrimaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #4338ca);
    border-color: #60a5fa;
}

/* Success Launch Button */
QPushButton[class="SuccessBtn"], QPushButton.SuccessBtn {
    background-color: #059669;
    border: 1px solid #10b981;
    color: #ffffff;
    font-weight: bold;
}

QPushButton[class="SuccessBtn"]:hover, QPushButton.SuccessBtn:hover {
    background-color: #047857;
}

/* Stop Button */
QPushButton[class="DangerBtn"], QPushButton.DangerBtn {
    background-color: #991b1b;
    border: 1px solid #dc2626;
    color: #ffffff;
}

QPushButton[class="DangerBtn"]:hover, QPushButton.DangerBtn:hover {
    background-color: #7f1d1d;
}

/* Preset Buttons */
QPushButton[class="PresetBtn"], QPushButton.PresetBtn {
    background-color: #111827;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
    color: #93c5fd;
}

QPushButton[class="PresetBtn"]:hover, QPushButton.PresetBtn:hover {
    background-color: #1e3a8a;
    border-color: #60a5fa;
    color: #ffffff;
}

/* Text Inputs */
QLineEdit {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px 8px;
    color: #f8fafc;
    font-size: 12px;
}

QLineEdit:focus {
    border: 1px solid #38bdf8;
    background-color: #131c2e;
}
"""
