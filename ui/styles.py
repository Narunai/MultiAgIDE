"""
Modern Dark Glassmorphic Theme for MultiAgIDE Studio
"""

DARK_THEME_QSS = """
QMainWindow, QWidget#MainContainer {
    background-color: #0b0f17;
    color: #f1f5f9;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13px;
}

QScrollArea {
    border: none;
    background: transparent;
}

QWidget#CentralWidget {
    background-color: #0b0f17;
}

/* Header & Banner */
QFrame#HeaderCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #111827, stop:1 #1e1b4b);
    border: 1px solid #312e81;
    border-radius: 12px;
    padding: 12px;
}

QLabel#AppTitle {
    color: #38bdf8;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: 0.5px;
}

QLabel#AppSubtitle {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 400;
}

/* Slot Cards */
QFrame.SlotCard {
    background-color: #131b29;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 14px;
}

QFrame.SlotCard:hover {
    border: 1px solid #38bdf8;
    background-color: #162032;
}

QFrame.SlotCardActive {
    border: 1px solid #10b981;
    background-color: #11202e;
}

QLabel.SlotTitle {
    font-size: 15px;
    font-weight: 700;
    color: #f8fafc;
}

QLabel.BadgeRunning {
    background-color: #064e3b;
    color: #34d399;
    border: 1px solid #059669;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}

QLabel.BadgeStopped {
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
    border-radius: 8px;
    padding: 7px 14px;
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
QPushButton.PrimaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #4f46e5);
    border: 1px solid #3b82f6;
    color: #ffffff;
    font-weight: bold;
}

QPushButton.PrimaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #4338ca);
    border-color: #60a5fa;
}

/* Success Launch Button */
QPushButton.SuccessBtn {
    background-color: #059669;
    border: 1px solid #10b981;
    color: #ffffff;
    font-weight: bold;
}

QPushButton.SuccessBtn:hover {
    background-color: #047857;
}

/* Stop Button */
QPushButton.DangerBtn {
    background-color: #991b1b;
    border: 1px solid #dc2626;
    color: #ffffff;
}

QPushButton.DangerBtn:hover {
    background-color: #7f1d1d;
}

/* Preset Layout Buttons */
QPushButton.PresetBtn {
    background-color: #111827;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
    color: #93c5fd;
}

QPushButton.PresetBtn:hover {
    background-color: #1e3a8a;
    border-color: #60a5fa;
    color: #ffffff;
}

QPushButton.PresetBtnActive {
    background-color: #2563eb;
    border: 1px solid #60a5fa;
    color: #ffffff;
}

/* Text Inputs */
QLineEdit {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 5px 10px;
    color: #f8fafc;
    font-size: 12px;
}

QLineEdit:focus {
    border: 1px solid #38bdf8;
    background-color: #131c2e;
}

/* Combo Box */
QComboBox {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 5px 10px;
    color: #f8fafc;
}

QComboBox::drop-down {
    border: none;
}

/* Floating Dock Theme */
QWidget#FloatingDock {
    background-color: rgba(15, 23, 42, 0.95);
    border: 1px solid #38bdf8;
    border-radius: 10px;
}
"""
