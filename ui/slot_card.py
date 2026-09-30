import os
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QDialog, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal

from core.process_manager import ProcessManager
from core.config_manager import ConfigManager
from core.quota_service import QuotaInfo
from .quota_pill import QuotaPillWidget
from .dark_title_bar import apply_dark_title_bar, create_minimal_app_icon


class LogViewerDialog(QDialog):
    def __init__(self, slot_id: int, proc_mgr: ProcessManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Logs - Slot #{slot_id}")
        self.setWindowIcon(create_minimal_app_icon())
        apply_dark_title_bar(self)
        self.resize(560, 360)
        self.setStyleSheet("""
            QDialog {
                background-color: #121214;
                color: #e4e4e7;
            }
            QTextEdit {
                background-color: #18181b;
                border: none;
                color: #38bdf8;
                font-family: Consolas, monospace;
                font-size: 11px;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton {
                background-color: #27272a;
                color: #e4e4e7;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
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
            self.text_area.setPlainText("No logs recorded for this slot yet.")

        btn_box = QHBoxLayout()
        btn_open_folder = QPushButton("Open Folder")
        btn_open_folder.clicked.connect(lambda: os.startfile(proc_mgr.logger.get_slot_log_dir(slot_id)))
        btn_box.addWidget(btn_open_folder)

        btn_box.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def showEvent(self, event):
        super().showEvent(event)
        apply_dark_title_bar(self)


class SlotCard(QFrame):
    layout_changed = Signal()
    slot_deleted = Signal(int)

    def __init__(self, slot_data: dict, proc_mgr: ProcessManager, config_mgr: ConfigManager, parent=None):
        super().__init__(parent)
        self.slot_id = slot_data["id"]
        self.slot_name = slot_data.get("name", f"Slot {self.slot_id}")
        self.proc_mgr = proc_mgr
        self.config_mgr = config_mgr

        self.setObjectName("SlotCard")
        self.setFixedHeight(64)
        self.setCursor(Qt.PointingHandCursor)
        self.init_ui()
        self.update_status_display()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.on_focus_slot()
        super().mousePressEvent(event)

    def on_id_label_clicked(self, event):
        if event.button() == Qt.LeftButton:
            # กฎข้อ 1: ต้องกด Start ก่อนเท่านั้น ถ้าสล็อตปิดอยู่ การคลิกตัวเลขจะไม่เริ่มทำงาน
            if not self.proc_mgr.is_running(self.slot_id):
                return

            # กฎข้อ 2: คลิกที่ตัวเลข #ID โดยตรง เป็นการสลับโหมด Max เต็มจอกับโหมด Grid เล็ก อย่างอิสระ
            is_max = (self.proc_mgr.maximized_slot_id == self.slot_id)
            if is_max:
                self.proc_mgr.bring_slot_to_front(self.slot_id, force_max=False)
            else:
                self.proc_mgr.bring_slot_to_front(self.slot_id, force_max=True)

            self.update_status_display()
            self.layout_changed.emit()

    def on_focus_slot(self):
        """
        เรียกหน้าต่างงานของสล็อตนั้นขึ้นมาด้านหน้าสุด
        กฎข้อ 1: เมื่อกด Start แล้ว ถึงจะสามารถคลิกเพื่อเรียกหน้าต่างขึ้นมาได้
        หากยังไม่ได้กด Start (STOPPED) จะไม่เปิดขึ้นมาเด็ดขาด (ป้องกันการเปิดโดยไม่ตั้งใจ)
        
        กฎข้อ 2: ปรับโหมด Max vs โหมดหน้าจอเล็ก อย่างอิสระ ตามค่าที่เลือกใน Dashboard หรือรักษาสถานะ Max เดิม
        """
        if not self.proc_mgr.is_running(self.slot_id):
            return  # ห้าม Start อัตโนมัติ! ต้องกดปุ่ม Start เท่านั้น

        dashboard = self.window()
        click_mode = getattr(dashboard, "click_mode", "max")

        if click_mode == "max":
            self.proc_mgr.bring_slot_to_front(self.slot_id, force_max=True)
        elif click_mode == "tile":
            self.proc_mgr.bring_slot_to_front(self.slot_id, force_max=False)
        else:
            self.proc_mgr.bring_slot_to_front(self.slot_id, force_max=None)

        self.update_status_display()
        self.layout_changed.emit()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(2)

        # Line 1: #ID  Name  Status  [Start] [Max] [Hide] [Log] [X]
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)

        self.id_label = QLabel(f"#{self.slot_id}")
        self.id_label.setCursor(Qt.PointingHandCursor)
        if self.slot_id >= 7:
            self.id_label.setStyleSheet("font-weight: 800; color: #a78bfa; font-size: 11px; padding: 1px 3px; border-radius: 3px;")
            self.id_label.setToolTip(f"คลิก #{self.slot_id} เพื่อเรียกหน้าต่างงานออกมา (แชร์ Display 1)")
        else:
            self.id_label.setStyleSheet("font-weight: 800; color: #38bdf8; font-size: 11px; padding: 1px 3px; border-radius: 3px;")
            self.id_label.setToolTip(f"คลิก #{self.slot_id} เพื่อเรียกหน้าต่างงานออกมาด้านหน้า (Display {self.slot_id})")
        self.id_label.mousePressEvent = self.on_id_label_clicked
        top_row.addWidget(self.id_label)

        self.name_edit = QLineEdit(self.slot_name)
        self.name_edit.setPlaceholderText("Account name")
        self.name_edit.setStyleSheet("font-weight: 600; font-size: 11px;")
        self.name_edit.editingFinished.connect(self.on_name_changed)
        top_row.addWidget(self.name_edit, 1)

        self.status_badge = QLabel("STOPPED")
        self.status_badge.setObjectName("BadgeStopped")
        top_row.addWidget(self.status_badge)

        top_row.addSpacing(4)

        # Pure Text Action Buttons (NO EMOJIS / NO ICONS)
        self.btn_toggle_run = QPushButton("Start")
        self.btn_toggle_run.setProperty("class", "SuccessBtn")
        self.btn_toggle_run.setFixedHeight(18)
        self.btn_toggle_run.clicked.connect(self.on_toggle_run_clicked)
        top_row.addWidget(self.btn_toggle_run)

        self.btn_maximize = QPushButton("Max")
        self.btn_maximize.setFixedHeight(18)
        self.btn_maximize.clicked.connect(self.on_maximize_clicked)
        top_row.addWidget(self.btn_maximize)

        self.btn_hide = QPushButton("Hide")
        self.btn_hide.setFixedHeight(18)
        self.btn_hide.clicked.connect(self.on_hide_clicked)
        top_row.addWidget(self.btn_hide)

        self.btn_log = QPushButton("Log")
        self.btn_log.setFixedHeight(18)
        self.btn_log.clicked.connect(self.on_log_clicked)
        top_row.addWidget(self.btn_log)

        if self.slot_id > 6:
            self.btn_del = QPushButton("X")
            self.btn_del.setFixedHeight(18)
            self.btn_del.setFixedWidth(16)
            self.btn_del.setStyleSheet("background-color: #27272a; color: #a1a1aa; font-size: 9px; border-radius: 3px; font-weight: bold;")
            self.btn_del.setToolTip(f"Delete Slot #{self.slot_id}")
            self.btn_del.clicked.connect(self.on_delete_clicked)
            top_row.addWidget(self.btn_del)

        main_layout.addLayout(top_row)

        # Line 2: Minimal Flat Quota Strip
        self.quota_pill = QuotaPillWidget()
        main_layout.addWidget(self.quota_pill)

    def on_name_changed(self):
        new_name = self.name_edit.text().strip()
        for s in self.config_mgr.config.get("slots", []):
            if s["id"] == self.slot_id:
                s["name"] = new_name
                break
        self.config_mgr.save_config()

    def on_toggle_run_clicked(self):
        # ตัดสินใจจากข้อความบนปุ่มโดยตรง ป้องกัน race condition ไม่ให้กด Stop แล้วกลายเป็นการเปิด
        action = self.btn_toggle_run.text().strip()
        if action == "Stop":
            self.proc_mgr.stop_slot(self.slot_id)
            self.update_status_display(force_stopped=True)
        else:
            self.proc_mgr.launch_slot(self.slot_id)
            self.update_status_display(force_running=True)
        self.layout_changed.emit()

    def on_maximize_clicked(self):
        is_max = self.proc_mgr.toggle_slot_maximize(self.slot_id)
        if is_max:
            self.btn_maximize.setText("Restore")
            self.btn_maximize.setStyleSheet("background-color: #d97706; color: white;")
        else:
            self.btn_maximize.setText("Max")
            self.btn_maximize.setStyleSheet("")
        self.layout_changed.emit()

    def on_hide_clicked(self):
        is_visible = self.proc_mgr.toggle_slot_visibility(self.slot_id)
        if is_visible:
            self.btn_hide.setText("Hide")
            self.btn_hide.setStyleSheet("")
        else:
            self.btn_hide.setText("Show")
            self.btn_hide.setStyleSheet("background-color: #3f3f46; color: #71717a;")
        self.layout_changed.emit()

    def on_log_clicked(self):
        dialog = LogViewerDialog(self.slot_id, self.proc_mgr, self)
        dialog.exec()

    def on_delete_clicked(self):
        reply = QMessageBox.question(
            self,
            "Delete Slot",
            f"Are you sure you want to remove Slot #{self.slot_id} ({self.name_edit.text()})?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.proc_mgr.is_running(self.slot_id):
                self.proc_mgr.stop_slot(self.slot_id)
            self.config_mgr.delete_slot(self.slot_id)
            self.slot_deleted.emit(self.slot_id)

    def update_status_display(self, force_stopped: bool = False, force_running: bool = False):
        if force_stopped:
            running = False
        elif force_running:
            running = True
        else:
            running = self.proc_mgr.is_running(self.slot_id)

        q, is_last_used, is_empty, is_cooldown_finished, is_generating = self.proc_mgr.get_slot_display_quota(self.slot_id)

        if running:
            self.status_badge.setText("RUNNING")
            self.status_badge.setObjectName("BadgeRunning")
            self.btn_toggle_run.setText("Stop")
            self.btn_toggle_run.setProperty("class", "DangerBtn")
            self.btn_toggle_run.setToolTip(f"คลิกเพื่อปิดสล็อต #{self.slot_id} ({q.email})")
            self.quota_pill.update_quota(q, is_running=True, is_last_used=is_last_used, is_empty=is_empty, is_cooldown_finished=False, is_generating=is_generating)
        else:
            self.status_badge.setText("STOPPED")
            self.status_badge.setObjectName("BadgeStopped")
            self.btn_toggle_run.setText("Start")
            self.btn_toggle_run.setProperty("class", "SuccessBtn")

            if is_cooldown_finished:
                self.btn_toggle_run.setToolTip(f"[READY] พร้อมใช้งาน: {q.email} (Cooldown เสร็จสิ้นแล้ว, กดเปิดเพื่อรีเฟรชเปอร์เซ็นต์)")
            elif is_last_used:
                self.btn_toggle_run.setToolTip(f"[LAST USED] บัญชีใช้งานล่าสุด: {q.email} (โควตา {q.gemini_pct}%)")
            elif is_empty:
                self.btn_toggle_run.setToolTip(f"[EMPTY] โควตาหมด ({q.gemini_pct}%) รีเซ็ตใน {q.reset_5h_str}")
            else:
                self.btn_toggle_run.setToolTip(f"เปิดสล็อต #{self.slot_id} ({q.email}) โควตา {q.gemini_pct}%")

            self.quota_pill.update_quota(q, is_running=False, is_last_used=is_last_used, is_empty=is_empty, is_cooldown_finished=is_cooldown_finished, is_generating=False)

        # ซิงค์สถานะปุ่ม Maximize/Restore ให้ตรงกับ ProcessManager (กรณีไปกด Max สล็อตอื่น)
        is_max = (self.proc_mgr.maximized_slot_id == self.slot_id)
        if is_max:
            if self.btn_maximize.text() != "Restore":
                self.btn_maximize.setText("Restore")
                self.btn_maximize.setStyleSheet("background-color: #d97706; color: white;")
        else:
            if self.btn_maximize.text() != "Max":
                self.btn_maximize.setText("Max")
                self.btn_maximize.setStyleSheet("")
                
        # ซิงค์สถานะปุ่ม Hide/Show
        state = self.proc_mgr.slots.get(self.slot_id)
        if state:
            is_visible = not state.is_hidden
            if is_visible:
                if self.btn_hide.text() != "Hide":
                    self.btn_hide.setText("Hide")
                    self.btn_hide.setStyleSheet("")
            else:
                if self.btn_hide.text() != "Show":
                    self.btn_hide.setText("Show")
                    self.btn_hide.setStyleSheet("background-color: #3f3f46; color: #71717a;")

        self.status_badge.style().polish(self.status_badge)
        self.btn_toggle_run.style().polish(self.btn_toggle_run)
