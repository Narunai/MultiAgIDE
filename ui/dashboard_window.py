import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, QTimer

from core.config_manager import ConfigManager
from core.layout_calculator import LayoutCalculator
from core.window_controller import WindowController
from core.process_manager import ProcessManager

from .styles import DARK_THEME_QSS
from .slot_card import SlotCard
from .dark_title_bar import apply_dark_title_bar, create_minimal_app_icon


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
        self.setWindowIcon(create_minimal_app_icon())
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
        self.init_ui()

        # Real-time Auto-Refresh Timer (every 1.5 seconds)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.poll_realtime_status)
        self.refresh_timer.start(1500)

    def init_geometry(self):
        """ขนาดกะทัดรัด (กว้าง 360px, สูง 490px) มองเห็นครบ 6 สล็อตในจอเดียว 100%"""
        screen = QApplication.primaryScreen()
        deck_w = 360
        deck_h = 490
        if screen:
            geom = screen.availableGeometry()
            deck_x = geom.x() + 30
            deck_y = geom.y() + 30
            self.setGeometry(deck_x, deck_y, deck_w, deck_h)
        else:
            self.resize(deck_w, deck_h)

        self.setFixedWidth(360)
        self.setFixedHeight(490)

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

        # 2. Slots Container (Zero-Scroll: fits all 6 slots in single view)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        cards_container = QWidget()
        cards_container.setObjectName("CardsContainer")
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(3)

        slots_data = self.config_mgr.config.get("slots", [])
        for s_data in slots_data[:6]:
            card = SlotCard(s_data, self.proc_mgr, self.config_mgr)
            card.layout_changed.connect(self.on_layout_or_status_changed)
            cards_layout.addWidget(card)
            self.slot_cards.append(card)

        scroll.setWidget(cards_container)
        root_layout.addWidget(scroll, 1)

        # 3. Minimal Footer
        footer = QHBoxLayout()
        footer.setContentsMargins(4, 0, 4, 0)

        self.status_summary = QLabel("Active: 0/6 Slots")
        self.status_summary.setStyleSheet("color: #71717a; font-size: 10px;")
        footer.addWidget(self.status_summary)

        footer.addStretch()

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

    def apply_preset_count(self, count: int):
        self.proc_mgr.maximized_slot_id = None
        for sid in range(1, 7):
            state = self.proc_mgr.slots[sid]
            if sid <= count:
                state.is_hidden = False
            else:
                state.is_hidden = True
                if state.ide_hwnd:
                    self.win_ctrl.hide_window(state.ide_hwnd)
        self.proc_mgr.apply_layout(reserve_deck_width=self.width())
        self.on_layout_or_status_changed()

    def _update_status_summary(self, running_count: int):
        running_sids = {c.slot_id for c in self.slot_cards if self.proc_mgr.is_running(c.slot_id)}
        last_sid = self.proc_mgr.history_mgr.get_last_used_slot_id()
        best_sid = self.proc_mgr.history_mgr.get_best_available_slot_id(running_sids)

        parts = [f"Active: {running_count}/6"]
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

    def poll_realtime_status(self):
        running_count = 0
        for card in self.slot_cards:
            card.update_status_display()
            if self.proc_mgr.is_running(card.slot_id):
                running_count += 1
        self._update_status_summary(running_count)

    def showEvent(self, event):
        super().showEvent(event)
        apply_dark_title_bar(self)
