from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Qt, QPoint, Signal

from core.process_manager import ProcessManager


class FloatingDock(QWidget):
    request_show_dashboard = Signal()
    layout_changed = Signal()

    def __init__(self, proc_mgr: ProcessManager, parent=None):
        super().__init__(parent)
        self.proc_mgr = proc_mgr
        self.drag_position = QPoint()

        # Frameless, Always on Top, Tool Window
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Outer Frame
        self.frame = QFrame()
        self.frame.setObjectName("FloatingDock")
        self.frame.setStyleSheet("""
            QFrame#FloatingDock {
                background-color: rgba(15, 23, 42, 0.92);
                border: 1px solid #38bdf8;
                border-radius: 10px;
                padding: 4px 8px;
            }
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
                border-color: #60a5fa;
                color: #ffffff;
            }
        """)

        frame_layout = QHBoxLayout(self.frame)
        frame_layout.setContentsMargins(6, 4, 6, 4)
        frame_layout.setSpacing(6)

        # Title / Drag handle
        title = QLabel("⚡ MultiAgIDE")
        title.setStyleSheet("color: #38bdf8; font-weight: 800; font-size: 11px; margin-right: 4px;")
        frame_layout.addWidget(title)

        # Quick Layout Presets
        for count in [1, 2, 3, 4, 6]:
            btn = QPushButton(str(count))
            btn.setFixedWidth(28)
            btn.setToolTip(f"จัดหน้าจอ {count} ส่วน")
            btn.clicked.connect(lambda checked, c=count: self.set_active_slots_count(c))
            frame_layout.addWidget(btn)

        # Separator
        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #475569;")
        frame_layout.addWidget(sep1)

        # Snap All Button
        btn_snap = QPushButton("🔄 Snap")
        btn_snap.setToolTip("จัดหน้าต่างเข้า Grid ทันที")
        btn_snap.clicked.connect(self.on_snap_clicked)
        frame_layout.addWidget(btn_snap)

        # Separator
        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #475569;")
        frame_layout.addWidget(sep2)

        # Slots Focus buttons
        for sid in range(1, 7):
            btn = QPushButton(f"S{sid}")
            btn.setFixedWidth(28)
            btn.setToolTip(f"ขยาย Slot {sid} เต็มจอ")
            btn.clicked.connect(lambda checked, s=sid: self.focus_slot(s))
            frame_layout.addWidget(btn)

        # Restore Dashboard button
        btn_dash = QPushButton("🗔 คอนโซล")
        btn_dash.setStyleSheet("background-color: #4f46e5; color: white;")
        btn_dash.setToolTip("เปิดหน้าต่าง Dashboard หลัก")
        btn_dash.clicked.connect(self.request_show_dashboard.emit)
        frame_layout.addWidget(btn_dash)

        layout.addWidget(self.frame)

    def set_active_slots_count(self, count: int):
        """เปิด N สล็อตแรก ซ่อนสล็อตที่เหลือ"""
        self.proc_mgr.maximized_slot_id = None
        for sid in list(self.proc_mgr.slots.keys()):
            state = self.proc_mgr.ensure_slot(sid)
            if sid <= count:
                state.is_hidden = False
            else:
                state.is_hidden = True
                if state.ide_hwnd:
                    self.proc_mgr.win_ctrl.hide_window(state.ide_hwnd)
        self.proc_mgr.apply_layout()
        self.layout_changed.emit()

    def focus_slot(self, slot_id: int):
        self.proc_mgr.toggle_slot_maximize(slot_id)
        self.layout_changed.emit()

    def on_snap_clicked(self):
        self.proc_mgr.apply_layout()
        self.layout_changed.emit()

    # Drag window handlers
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
