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


class DashboardWindow(QMainWindow):
    """
    Compact 1/4 Screen Mission Control Deck
    เปิดขึ้นมาอยู่ตรงกลางหรือชิดซ้าย ไม่หลุดขอบจอ
    พร้อมปุ่มย้าย ซ้าย / กลาง / ขวา ในคลิกเดียว
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MultiAgIDE — Control Deck")

        # Core Engines
        self.config_mgr = ConfigManager()
        self.layout_calc = LayoutCalculator()
        self.win_ctrl = WindowController()
        self.proc_mgr = ProcessManager(self.config_mgr, self.win_ctrl, self.layout_calc)

        # Apply Stylesheet
        self.setStyleSheet(DARK_THEME_QSS)

        # Set Safe Dimensions & Center on Screen
        self.init_geometry()

        self.slot_cards = []
        self.init_ui()

        # Real-time Auto-Refresh Timer (every 2.5 seconds)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.poll_realtime_status)
        self.refresh_timer.start(2500)

    def init_geometry(self):
        """ตั้งค่าพิกัดให้แสดงผลตรงกลางจอหรือชิดซ้าย ไม่หลุดขอบจอ"""
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            deck_w = 400
            deck_h = min(760, geom.height() - 60)
            # เริ่มต้นที่ฝั่งซ้ายของหน้าจอ (มีระยะห่าง 30px สบายตา ลากง่าย)
            deck_x = geom.x() + 30
            deck_y = geom.y() + 30
            self.setGeometry(deck_x, deck_y, deck_w, deck_h)
            self.setMinimumWidth(360)
            self.setMaximumWidth(460)
        else:
            self.resize(400, 740)

    def init_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        central_widget.setStyleSheet("background-color: #0b0f17;")
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        # 1. Compact Header
        header_card = QFrame()
        header_card.setObjectName("HeaderCard")
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(10, 8, 10, 8)
        h_layout.setSpacing(6)

        top_row = QHBoxLayout()
        app_title = QLabel("⚡ MultiAgIDE Deck")
        app_title.setObjectName("AppTitle")
        app_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #38bdf8;")
        top_row.addWidget(app_title)

        top_row.addStretch()

        # Position Quick Buttons (Left, Center, Right)
        btn_left = QPushButton("⬅ ซ้าย")
        btn_left.setToolTip("ย้าย Control Deck ไปชิดซ้าย")
        btn_left.clicked.connect(self.dock_left)
        top_row.addWidget(btn_left)

        btn_center = QPushButton("⏺ กลาง")
        btn_center.setToolTip("ย้าย Control Deck มาไว้ตรงกลางจอ")
        btn_center.clicked.connect(self.dock_center)
        top_row.addWidget(btn_center)

        btn_right = QPushButton("➡ ขวา")
        btn_right.setToolTip("ย้าย Control Deck ไปชิดขวา")
        btn_right.clicked.connect(self.dock_right)
        top_row.addWidget(btn_right)

        h_layout.addLayout(top_row)

        # IDE Grid Presets Row
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        preset_lbl = QLabel("Grid:")
        preset_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        preset_row.addWidget(preset_lbl)

        for count in [1, 2, 3, 4, 6]:
            btn = QPushButton(str(count))
            btn.setProperty("class", "PresetBtn")
            btn.setFixedWidth(28)
            btn.setToolTip(f"จัดแบ่งหน้าจอ IDE {count} ส่วน")
            btn.clicked.connect(lambda checked, c=count: self.apply_preset_count(c))
            preset_row.addWidget(btn)

        preset_row.addStretch()

        # Master Actions
        self.btn_snap = QPushButton("🔄")
        self.btn_snap.setToolTip("จัดระเบียบ Snap หน้าต่างทั้งหมด")
        self.btn_snap.setFixedWidth(30)
        self.btn_snap.clicked.connect(self.on_snap_clicked)
        preset_row.addWidget(self.btn_snap)

        self.btn_launch_all = QPushButton("🚀")
        self.btn_launch_all.setProperty("class", "PrimaryBtn")
        self.btn_launch_all.setToolTip("เปิดใช้งานทั้ง 6 สล็อต")
        self.btn_launch_all.setFixedWidth(30)
        self.btn_launch_all.clicked.connect(self.on_launch_all_clicked)
        preset_row.addWidget(self.btn_launch_all)

        self.btn_stop_all = QPushButton("⏹")
        self.btn_stop_all.setProperty("class", "DangerBtn")
        self.btn_stop_all.setToolTip("ปิดสล็อตทั้งหมด")
        self.btn_stop_all.setFixedWidth(30)
        self.btn_stop_all.clicked.connect(self.on_stop_all_clicked)
        preset_row.addWidget(self.btn_stop_all)

        h_layout.addLayout(preset_row)
        root_layout.addWidget(header_card)

        # 2. Scroll Area containing all 6 Slots
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #0b0f17; border: none;")
        scroll.viewport().setStyleSheet("background-color: #0b0f17;")

        cards_container = QWidget()
        cards_container.setObjectName("CardsContainer")
        cards_container.setStyleSheet("background-color: #0b0f17;")
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)

        slots_data = self.config_mgr.config.get("slots", [])
        for s_data in slots_data[:6]:
            card = SlotCard(s_data, self.proc_mgr, self.config_mgr)
            card.layout_changed.connect(self.on_layout_or_status_changed)
            cards_layout.addWidget(card)
            self.slot_cards.append(card)

        scroll.setWidget(cards_container)
        root_layout.addWidget(scroll, 1)

        # 3. Compact Footer Status Bar
        footer = QHBoxLayout()
        self.status_summary = QLabel("🟢 ตรวจสอบสถานะอัตโนมัติ")
        self.status_summary.setStyleSheet("color: #64748b; font-size: 10px;")
        footer.addWidget(self.status_summary)

        footer.addStretch()

        btn_profiles = QPushButton("📂 Profiles")
        btn_profiles.setStyleSheet("font-size: 10px; padding: 2px 6px;")
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
            "ยืนยันการปิดทั้งหมด",
            "คุณต้องการปิด Antigravity IDE ทั้งหมด 6 ช่องใช่หรือไม่?",
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

    def on_layout_or_status_changed(self):
        running_count = 0
        for card in self.slot_cards:
            card.update_status_display()
            if self.proc_mgr.is_running(card.slot_id):
                running_count += 1
        self.status_summary.setText(f"🟢 กำลังทำงาน: {running_count}/6 Slots")

    def poll_realtime_status(self):
        running_count = 0
        for card in self.slot_cards:
            card.update_status_display()
            if self.proc_mgr.is_running(card.slot_id):
                running_count += 1
        self.status_summary.setText(f"🟢 กำลังทำงาน: {running_count}/6 Slots | Control Deck")
