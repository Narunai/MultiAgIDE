import os
import time
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QMessageBox, QApplication,
    QSystemTrayIcon
)
from PySide6.QtCore import Qt, QTimer

from core.config_manager import ConfigManager
from core.layout_calculator import LayoutCalculator
from core.window_controller import WindowController
from core.process_manager import ProcessManager
from core.package_manager import PackageManager

from .styles import DARK_THEME_QSS
from .slot_card import SlotCard
from .dark_title_bar import apply_dark_title_bar, create_minimal_app_icon
from .package_dialogs import ExportDialog, ImportDialog


class DashboardWindow(QMainWindow):
    """
    Pure Minimalist Control Deck (Zero Icons, Zero Scroll)
    - แสดงผลครบทั้ง 6 สล็อตในหน้าจอเดียวโดยไม่ต้องเลื่อน Scroll
    - ไม่มีไอคอนหรืออิโมจิใดๆ ใช้ Typography และปุ่มข้อความเรียบง่าย
    - พื้นหลังสีดำเทา Flat Matte (#121214 / #18181b) ไร้กรอบ Border
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MultiAgIDE Control Deck")
        app_icon = create_minimal_app_icon()
        self.setWindowIcon(app_icon)
        apply_dark_title_bar(self)

        # Core Engines
        self.config_mgr = ConfigManager()
        self.layout_calc = LayoutCalculator()
        self.win_ctrl = WindowController()
        self.proc_mgr = ProcessManager(self.config_mgr, self.win_ctrl, self.layout_calc)

        # Apply Stylesheet
        self.setStyleSheet(DARK_THEME_QSS)

        # Window Dimension & Position
        self.init_geometry()

        self.slot_cards = []
        self.notified_cooldown_slots = set()

        # System Tray for Windows toast notifications
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(app_icon)
        self.tray_icon.show()

        self.init_ui()

        # Real-time Auto-Refresh Timer (every 1 second for exact real-time clock countdown)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.poll_realtime_status)
        self.refresh_timer.start(1000)

    def init_geometry(self):
        """
        คำนวณขนาด Control Deck ให้แสดงผลได้สูงสุดถึง 12 สล็อตในหน้าจอ
        และหากมีจำนวนสล็อตมากกว่า 12 สล็อต ตัว ScrollArea จะเปิดให้เลื่อนดูได้อย่างราบรื่น
        """
        screen = QApplication.primaryScreen()
        deck_w = 360
        num_slots = len(self.config_mgr.config.get("slots", []))
        visible_target_count = min(max(num_slots, 6), 12)
        target_h = 100 + (visible_target_count * 67)

        if screen:
            geom = screen.availableGeometry()
            max_h = geom.height() - 50
            deck_h = min(target_h, max_h)
            deck_x = geom.x() + 30
            deck_y = geom.y() + 30
            self.setGeometry(deck_x, deck_y, deck_w, deck_h)
            self.setMaximumHeight(min(100 + (12 * 67), geom.height() - 40))
        else:
            deck_h = min(target_h, 904)
            self.resize(deck_w, deck_h)

        self.setFixedWidth(360)
        self.setMinimumHeight(400)

    def init_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(4)

        # 1. Minimal Header Card
        header_card = QFrame()
        header_card.setObjectName("HeaderCard")
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(6, 4, 6, 4)
        h_layout.setSpacing(3)

        # Header Line 1: Title & Position Buttons
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(3)

        app_title = QLabel("MultiAgIDE")
        app_title.setObjectName("AppTitle")
        top_row.addWidget(app_title)

        top_row.addStretch()

        pos_label = QLabel("Pos:")
        pos_label.setStyleSheet("color: #71717a; font-size: 10px;")
        top_row.addWidget(pos_label)

        btn_left = QPushButton("Left")
        btn_left.setToolTip("Dock to Left")
        btn_left.setFixedHeight(18)
        btn_left.clicked.connect(self.dock_left)
        top_row.addWidget(btn_left)

        btn_center = QPushButton("Mid")
        btn_center.setToolTip("Center on Screen")
        btn_center.setFixedHeight(18)
        btn_center.clicked.connect(self.dock_center)
        top_row.addWidget(btn_center)

        btn_right = QPushButton("Right")
        btn_right.setToolTip("Dock to Right")
        btn_right.setFixedHeight(18)
        btn_right.clicked.connect(self.dock_right)
        top_row.addWidget(btn_right)

        h_layout.addLayout(top_row)

        # Header Line 2: Grid Presets & Action Buttons
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        ctrl_row.setSpacing(3)

        grid_lbl = QLabel("Grid:")
        grid_lbl.setStyleSheet("color: #71717a; font-size: 10px; font-weight: 600;")
        ctrl_row.addWidget(grid_lbl)

        for count in [1, 2, 3, 4, 6]:
            btn = QPushButton(str(count))
            btn.setProperty("class", "PresetBtn")
            btn.setFixedSize(20, 18)
            btn.clicked.connect(lambda checked, c=count: self.apply_preset_count(c))
            ctrl_row.addWidget(btn)

        ctrl_row.addStretch()

        self.btn_snap = QPushButton("Snap")
        self.btn_snap.setFixedHeight(18)
        self.btn_snap.clicked.connect(self.on_snap_clicked)
        ctrl_row.addWidget(self.btn_snap)

        self.btn_launch_all = QPushButton("Run All")
        self.btn_launch_all.setProperty("class", "PrimaryBtn")
        self.btn_launch_all.setFixedHeight(18)
        self.btn_launch_all.clicked.connect(self.on_launch_all_clicked)
        ctrl_row.addWidget(self.btn_launch_all)

        self.btn_stop_all = QPushButton("Stop")
        self.btn_stop_all.setProperty("class", "DangerBtn")
        self.btn_stop_all.setFixedHeight(18)
        self.btn_stop_all.clicked.connect(self.on_stop_all_clicked)
        ctrl_row.addWidget(self.btn_stop_all)

        h_layout.addLayout(ctrl_row)
        root_layout.addWidget(header_card)

        # Alert Banner: แสดงเตือนเมื่อโควตาพร้อมใช้งานอีกครั้ง ("อีเมลนี้พร้อมใช้งานอีกครั้ง")
        self.alert_banner = QFrame()
        self.alert_banner.setObjectName("AlertBanner")
        self.alert_banner.setStyleSheet("""
            QFrame#AlertBanner {
                background-color: #064e3b;
                border: 1px solid #10b981;
                border-radius: 4px;
                padding: 3px 6px;
            }
        """)
        ab_layout = QHBoxLayout(self.alert_banner)
        ab_layout.setContentsMargins(6, 3, 6, 3)
        ab_layout.setSpacing(4)

        self.alert_label = QLabel()
        self.alert_label.setStyleSheet("color: #ecfdf5; font-size: 10px; font-weight: 700;")
        ab_layout.addWidget(self.alert_label, 1)

        btn_dismiss = QPushButton("X")
        btn_dismiss.setFixedSize(14, 14)
        btn_dismiss.setStyleSheet("background: transparent; color: #a7f3d0; font-size: 9px; font-weight: bold; border: none;")
        btn_dismiss.clicked.connect(self.alert_banner.hide)
        ab_layout.addWidget(btn_dismiss)

        self.alert_banner.hide()
        root_layout.addWidget(self.alert_banner)

        # 2. Slots Container (Scales up to 12 slots on screen, scrollable beyond)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.cards_container = QWidget()
        self.cards_container.setObjectName("CardsContainer")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(3)

        slots_data = self.config_mgr.config.get("slots", [])
        for s_data in slots_data:
            card = SlotCard(s_data, self.proc_mgr, self.config_mgr)
            card.layout_changed.connect(self.on_layout_or_status_changed)
            card.slot_deleted.connect(self.on_slot_deleted)
            self.cards_layout.addWidget(card)
            self.slot_cards.append(card)

        self.scroll.setWidget(self.cards_container)
        root_layout.addWidget(self.scroll, 1)

        # 3. Minimal Footer
        footer = QHBoxLayout()
        footer.setContentsMargins(4, 0, 4, 0)

        self.status_summary = QLabel(f"Active: 0/{len(self.slot_cards)} Slots")
        self.status_summary.setStyleSheet("color: #71717a; font-size: 10px;")
        footer.addWidget(self.status_summary)

        footer.addStretch()

        btn_add = QPushButton("+ Add Slot")
        btn_add.setFixedHeight(16)
        btn_add.setStyleSheet("font-size: 9px; padding: 0px 5px; font-weight: 600; color: #38bdf8; background-color: #18181b; border: 1px solid #27272a; border-radius: 3px;")
        btn_add.setToolTip("Add new account slot")
        btn_add.clicked.connect(self.on_add_slot_clicked)
        footer.addWidget(btn_add)

        btn_export = QPushButton("Export")
        btn_export.setFixedHeight(16)
        btn_export.setStyleSheet("font-size: 9px; padding: 0px 4px; font-weight: 600; color: #a78bfa; background-color: #18181b; border: 1px solid #27272a; border-radius: 3px;")
        btn_export.setToolTip("Export all profiles, auth tokens, and projects to a portable package")
        btn_export.clicked.connect(self.on_export_clicked)
        footer.addWidget(btn_export)

        btn_import = QPushButton("Import")
        btn_import.setFixedHeight(16)
        btn_import.setStyleSheet("font-size: 9px; padding: 0px 4px; font-weight: 600; color: #10b981; background-color: #18181b; border: 1px solid #27272a; border-radius: 3px;")
        btn_import.setToolTip("Import and restore a portable package onto this machine")
        btn_import.clicked.connect(self.on_import_clicked)
        footer.addWidget(btn_import)

        btn_profiles = QPushButton("Profiles")
        btn_profiles.setFixedHeight(16)
        btn_profiles.setStyleSheet("font-size: 9px; padding: 0px 4px;")
        btn_profiles.clicked.connect(lambda: os.startfile(self.config_mgr.PROFILES_DIR if hasattr(self.config_mgr, 'PROFILES_DIR') else os.path.dirname(self.config_mgr.get_slot_paths(1)['ide_dir'])))
        footer.addWidget(btn_profiles)

        root_layout.addLayout(footer)

    def dock_left(self):
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            self.move(geom.x() + 20, geom.y() + 20)

    def dock_center(self):
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + (geom.height() - self.height()) // 2
            self.move(x, y)

    def dock_right(self):
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            self.move(geom.x() + geom.width() - self.width() - 20, geom.y() + 20)

    def on_launch_all_clicked(self):
        self.proc_mgr.launch_all()
        self.on_layout_or_status_changed()

    def on_snap_clicked(self):
        self.proc_mgr.apply_layout(reserve_deck_width=self.width())

    def on_stop_all_clicked(self):
        reply = QMessageBox.question(
            self,
            "Confirm",
            "Stop all Antigravity IDE instances?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.proc_mgr.stop_all()
            self.on_layout_or_status_changed()

    def on_add_slot_clicked(self):
        new_slot_data = self.config_mgr.add_slot()
        new_id = new_slot_data["id"]
        self.proc_mgr.ensure_slot(new_id)

        card = SlotCard(new_slot_data, self.proc_mgr, self.config_mgr)
        card.layout_changed.connect(self.on_layout_or_status_changed)
        card.slot_deleted.connect(self.on_slot_deleted)
        self.cards_layout.addWidget(card)
        self.slot_cards.append(card)

        self.adjust_window_height()
        self.on_layout_or_status_changed()

    def on_slot_deleted(self, slot_id: int):
        target_card = None
        for card in self.slot_cards:
            if card.slot_id == slot_id:
                target_card = card
                break
        if target_card:
            self.cards_layout.removeWidget(target_card)
            self.slot_cards.remove(target_card)
            target_card.deleteLater()

        self.adjust_window_height()
        self.on_layout_or_status_changed()

    def on_export_clicked(self):
        pkg_mgr = PackageManager(self.config_mgr.BASE_DIR)
        dialog = ExportDialog(pkg_mgr, self)
        dialog.exec()

    def on_import_clicked(self):
        pkg_mgr = PackageManager(self.config_mgr.BASE_DIR)
        dialog = ImportDialog(pkg_mgr, self)
        dialog.import_completed.connect(self.on_import_completed)
        dialog.exec()

    def on_import_completed(self, result: dict):
        self.reload_all_slots()

    def reload_all_slots(self):
        """โหลดรายการสล็อตทั้งหมดใหม่หลังการนำเข้า (Import) หรือการเปลี่ยนแปลงโครงสร้าง"""
        self.config_mgr.config = self.config_mgr.load_config()
        self.config_mgr.ensure_profiles_dirs()

        # นำการ์ดเดิมออก
        for card in list(self.slot_cards):
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self.slot_cards.clear()

        # สร้างการ์ดใหม่ตามข้อมูลล่าสุด
        slots_data = self.config_mgr.config.get("slots", [])
        for s_data in slots_data:
            sid = s_data["id"]
            self.proc_mgr.ensure_slot(sid)
            card = SlotCard(s_data, self.proc_mgr, self.config_mgr)
            card.layout_changed.connect(self.on_layout_or_status_changed)
            card.slot_deleted.connect(self.on_slot_deleted)
            self.cards_layout.addWidget(card)
            self.slot_cards.append(card)

        self.adjust_window_height()
        self.on_layout_or_status_changed()

    def adjust_window_height(self):
        screen = QApplication.primaryScreen()
        num_slots = len(self.slot_cards)
        visible_count = min(max(num_slots, 6), 12)
        target_h = 100 + (visible_count * 67)
        if screen:
            geom = screen.availableGeometry()
            max_h = geom.height() - 50
            new_h = min(target_h, max_h)
            self.setMaximumHeight(min(100 + (12 * 67), geom.height() - 40))
            self.resize(self.width(), new_h)
        else:
            self.resize(self.width(), target_h)

    def apply_preset_count(self, count: int):
        self.proc_mgr.maximized_slot_id = None
        for card in self.slot_cards:
            sid = card.slot_id
            state = self.proc_mgr.ensure_slot(sid)
            if sid <= count:
                state.is_hidden = False
            else:
                state.is_hidden = True
                if state.ide_hwnd:
                    self.win_ctrl.hide_window(state.ide_hwnd)
        self.proc_mgr.apply_layout(reserve_deck_width=self.width())
        self.on_layout_or_status_changed()

    def _update_status_summary(self, running_count: int):
        total_slots = len(self.slot_cards)
        running_sids = {c.slot_id for c in self.slot_cards if self.proc_mgr.is_running(c.slot_id)}
        last_sid = self.proc_mgr.history_mgr.get_last_used_slot_id()
        best_sid = self.proc_mgr.history_mgr.get_best_available_slot_id(running_sids)

        parts = [f"Active: {running_count}/{total_slots}"]
        if last_sid:
            rec_last = self.proc_mgr.history_mgr.get_record(last_sid)
            email_part = rec_last.email.split('@')[0] if '@' in rec_last.email else rec_last.email
            parts.append(f"Last: #{last_sid} ({email_part})")
        if best_sid:
            rec_best = self.proc_mgr.history_mgr.get_record(best_sid)
            parts.append(f"Best: #{best_sid} ({rec_best.gemini_pct}%)")

        self.status_summary.setText(" | ".join(parts))

    def on_layout_or_status_changed(self):
        running_count = 0
        for card in self.slot_cards:
            card.update_status_display()
            if self.proc_mgr.is_running(card.slot_id):
                running_count += 1
        self._update_status_summary(running_count)

    def show_cooldown_alert(self, slot_id: int, email: str):
        msg = f"อีเมล {email} พร้อมใช้งานอีกครั้ง"
        self.alert_label.setText(f"[READY] {msg} (สล็อต #{slot_id})")
        self.alert_banner.show()
        QTimer.singleShot(15000, self.alert_banner.hide)

        # Native Windows Toast Notification
        if QSystemTrayIcon.isSystemTrayAvailable():
            try:
                self.tray_icon.showMessage("MultiAgIDE", f"{msg} (Slot #{slot_id})", QSystemTrayIcon.Information, 8000)
            except Exception:
                pass

    def poll_realtime_status(self):
        running_count = 0
        now = time.time()
        for card in self.slot_cards:
            card.update_status_display()
            if self.proc_mgr.is_running(card.slot_id):
                running_count += 1

            # ตรวจสอบสถานะ Cooldown Real-time เพื่อแจ้งเตือนเมื่อเหลือศูนย์
            q, is_last_used, is_empty, is_cooldown_finished, is_generating = self.proc_mgr.get_slot_display_quota(card.slot_id)
            if q.reset_5h_ts > 0:
                if now < q.reset_5h_ts:
                    # อยู่ระหว่างการนับถอยหลัง: รีเซ็ตสถานะแจ้งเตือน เพื่อให้สามารถแจ้งเตือนเมื่อนับถึงศูนย์
                    self.notified_cooldown_slots.discard(card.slot_id)
                elif now >= q.reset_5h_ts or is_cooldown_finished:
                    # นับถอยหลังถึง 0 แล้ว! แจ้งเตือน 1 ครั้ง
                    if card.slot_id not in self.notified_cooldown_slots:
                        self.notified_cooldown_slots.add(card.slot_id)
                        if q.email and q.email not in ("offline", "Unknown"):
                            self.show_cooldown_alert(card.slot_id, q.email)

        self._update_status_summary(running_count)

    def showEvent(self, event):
        super().showEvent(event)
        apply_dark_title_bar(self)
