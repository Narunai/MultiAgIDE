import os
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QDialog, QTextEdit
)
from PySide6.QtCore import Qt, Signal

from core.process_manager import ProcessManager
from core.config_manager import ConfigManager
from .quota_pill import QuotaPillWidget


class LogViewerDialog(QDialog):
    def __init__(self, slot_id: int, proc_mgr: ProcessManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Activity & Conversation Logs — Slot #{slot_id}")
        self.resize(600, 420)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #e2e8f0;
            }
            QTextEdit {
                background-color: #0b0f17;
                border: 1px solid #1e293b;
                color: #38bdf8;
                font-family: Consolas, monospace;
                font-size: 11px;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton {
                background-color: #1e293b;
                color: white;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)

        layout = QVBoxLayout(self)
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)

        logs = proc_mgr.logger.get_recent_logs(slot_id, limit=60)
        if logs:
            content = []
            for item in logs:
                content.append(f"[{item.get('timestamp', '')[:19]}] [{item.get('event')}] {item.get('message')}")
            self.text_area.setPlainText("\n".join(content))
        else:
            self.text_area.setPlainText("ยังไม่มีบันทึกกิจกรรมสำหรับสล็อตนี้ (จะบันทึกอัตโนมัติเมื่อเปิดใช้งาน IDE)")

        btn_box = QHBoxLayout()
        btn_open_folder = QPushButton("📂 เปิดโฟลเดอร์ Log")
        btn_open_folder.clicked.connect(lambda: os.startfile(proc_mgr.logger.get_slot_log_dir(slot_id)))
        btn_box.addWidget(btn_open_folder)

        btn_box.addStretch()
        btn_close = QPushButton("ปิดหน้าต่าง")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)


class SlotCard(QFrame):
    layout_changed = Signal()

    def __init__(self, slot_data: dict, proc_mgr: ProcessManager, config_mgr: ConfigManager, parent=None):
        super().__init__(parent)
        self.slot_id = slot_data["id"]
        self.slot_name = slot_data.get("name", f"Slot {self.slot_id}")
        self.proc_mgr = proc_mgr
        self.config_mgr = config_mgr

        self.setObjectName("SlotCard")
        self.setProperty("class", "SlotCard")

        self.init_ui()
        self.update_status_display()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        # 1. Header (ID, Name, Running Badge)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        self.id_label = QLabel(f"#{self.slot_id}")
        self.id_label.setStyleSheet("font-weight: 900; color: #38bdf8; font-size: 15px;")
        header_layout.addWidget(self.id_label)

        self.name_edit = QLineEdit(self.slot_name)
        self.name_edit.setPlaceholderText("ชื่อบัญชี Google")
        self.name_edit.setStyleSheet("font-weight: 600; padding: 4px 6px; font-size: 11px;")
        self.name_edit.editingFinished.connect(self.on_name_changed)
        header_layout.addWidget(self.name_edit, 1)

        self.status_badge = QLabel("STOPPED")
        self.status_badge.setProperty("class", "BadgeStopped")
        self.status_badge.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.status_badge)

        main_layout.addLayout(header_layout)

        # 2. Quota Pill Widget
        self.quota_pill = QuotaPillWidget()
        main_layout.addWidget(self.quota_pill)

        # 3. Action Buttons Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self.btn_toggle_run = QPushButton("▶ เปิด")
        self.btn_toggle_run.setProperty("class", "SuccessBtn")
        self.btn_toggle_run.setToolTip("เปิด Antigravity IDE ประจำสล็อตนี้")
        self.btn_toggle_run.clicked.connect(self.on_toggle_run_clicked)
        btn_layout.addWidget(self.btn_toggle_run)

        self.btn_maximize = QPushButton("🔍")
        self.btn_maximize.setToolTip("ขยายสล็อตนี้เต็มจอ (หรือคืน Grid)")
        self.btn_maximize.setFixedWidth(32)
        self.btn_maximize.clicked.connect(self.on_maximize_clicked)
        btn_layout.addWidget(self.btn_maximize)

        self.btn_hide = QPushButton("👁️")
        self.btn_hide.setToolTip("ซ่อน/แสดงสล็อตนี้")
        self.btn_hide.setFixedWidth(32)
        self.btn_hide.clicked.connect(self.on_hide_clicked)
        btn_layout.addWidget(self.btn_hide)

        self.btn_log = QPushButton("📜 Log")
        self.btn_log.setToolTip("ดูบันทึกกิจกรรมและ Conversation ประจำสล็อตนี้")
        self.btn_log.clicked.connect(self.on_log_clicked)
        btn_layout.addWidget(self.btn_log)

        main_layout.addLayout(btn_layout)

    def on_name_changed(self):
        new_name = self.name_edit.text().strip()
        for s in self.config_mgr.config.get("slots", []):
            if s["id"] == self.slot_id:
                s["name"] = new_name
                break
        self.config_mgr.save_config()

    def on_toggle_run_clicked(self):
        if self.proc_mgr.is_running(self.slot_id):
            self.proc_mgr.stop_slot(self.slot_id)
        else:
            self.proc_mgr.launch_slot(self.slot_id)
        self.update_status_display()
        self.layout_changed.emit()

    def on_maximize_clicked(self):
        is_max = self.proc_mgr.toggle_slot_maximize(self.slot_id)
        if is_max:
            self.btn_maximize.setText("🗗")
            self.btn_maximize.setStyleSheet("background-color: #d97706; color: white;")
        else:
            self.btn_maximize.setText("🔍")
            self.btn_maximize.setStyleSheet("")
        self.layout_changed.emit()

    def on_hide_clicked(self):
        is_visible = self.proc_mgr.toggle_slot_visibility(self.slot_id)
        if is_visible:
            self.btn_hide.setStyleSheet("")
        else:
            self.btn_hide.setStyleSheet("background-color: #475569; color: #94a3b8;")
        self.layout_changed.emit()

    def on_log_clicked(self):
        dialog = LogViewerDialog(self.slot_id, self.proc_mgr, self)
        dialog.exec()

    def update_status_display(self):
        running = self.proc_mgr.is_running(self.slot_id)

        if running:
            self.status_badge.setText("RUNNING")
            self.status_badge.setProperty("class", "BadgeRunning")
            self.btn_toggle_run.setText("⏹ ปิด")
            self.btn_toggle_run.setProperty("class", "DangerBtn")
            # Fetch / refresh quota
            q = self.proc_mgr.refresh_quota(self.slot_id)
            self.quota_pill.update_quota(q)
        else:
            self.status_badge.setText("STOPPED")
            self.status_badge.setProperty("class", "BadgeStopped")
            self.btn_toggle_run.setText("▶ เปิด")
            self.btn_toggle_run.setProperty("class", "SuccessBtn")
            state = self.proc_mgr.get_slot_state(self.slot_id)
            self.quota_pill.update_quota(state.quota_info)

        self.status_badge.style().polish(self.status_badge)
        self.btn_toggle_run.style().polish(self.btn_toggle_run)
