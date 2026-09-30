import os
import time
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QMessageBox, QWidget
)
from PySide6.QtCore import Qt, Signal

from core.process_manager import ProcessManager
from core.config_manager import ConfigManager
from core.swap_manager import SwapManager
from .dark_title_bar import apply_dark_title_bar, create_minimal_app_icon


class ModeOptionCard(QFrame):
    """
    การ์ดตัวเลือกโหมด Swap แสดงเครื่องหมาย [✓] หรือ [  ] ชัดเจน
    คลิกที่การ์ดเพื่อสลับโหมดได้ทันที
    """
    clicked = Signal(str)

    def __init__(self, mode_id: str, title: str, subtitle: str, is_recommended: bool = False, parent=None):
        super().__init__(parent)
        self.mode_id = mode_id
        self.is_selected = False
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        top_h = QHBoxLayout()
        top_h.setContentsMargins(0, 0, 0, 0)
        top_h.setSpacing(6)

        self.lbl_check = QLabel("[✓]" if is_recommended else "[  ]")
        self.lbl_check.setStyleSheet("font-weight: 800; font-size: 12px;")
        top_h.addWidget(self.lbl_check)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #f4f4f5;")
        top_h.addWidget(self.lbl_title, 1)

        if is_recommended:
            badge = QLabel("แนะนำ")
            badge.setStyleSheet("background-color: #065f46; color: #6ee7b7; font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 3px;")
            top_h.addWidget(badge)

        layout.addLayout(top_h)

        self.lbl_sub = QLabel(subtitle)
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setStyleSheet("font-size: 10px; color: #a1a1aa; padding-left: 20px;")
        layout.addWidget(self.lbl_sub)

        self.update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.mode_id)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update_style()

    def update_style(self):
        if self.is_selected:
            self.lbl_check.setText("[✓]")
            self.lbl_check.setStyleSheet("color: #38bdf8; font-weight: 800; font-size: 12px;")
            self.setStyleSheet("""
                QFrame {
                    background-color: #082f49;
                    border: 1.5px solid #0284c7;
                    border-radius: 6px;
                }
            """)
        else:
            self.lbl_check.setText("[  ]")
            self.lbl_check.setStyleSheet("color: #71717a; font-weight: 700; font-size: 12px;")
            self.setStyleSheet("""
                QFrame {
                    background-color: #18181b;
                    border: 1px solid #27272a;
                    border-radius: 6px;
                }
                QFrame:hover {
                    background-color: #202024;
                    border-color: #3f3f46;
                }
            """)


class SwapUserDialog(QDialog):
    """
    หน้าต่าง Swap User Account สำหรับ MultiAgIDE Studio
    - สลับบัญชี Google และ Auth Tokens ข้ามสล็อต
    - ช่วยให้สล็อตที่โควตาหมดสามารถสลับไปใช้บัญชีของอีกสล็อตเพื่อทำงานต่อได้ทันที
    - มีการตรวจสอบเงื่อนไขความปลอดภัย: ทั้ง 2 สล็อตต้อง STOPPED (ไม่รันอยู่) ถึงจะอนุญาตให้สลับ
    """
    swap_completed = Signal(int, int)

    def __init__(self, source_slot_id: int, proc_mgr: ProcessManager, config_mgr: ConfigManager, parent=None):
        super().__init__(parent)
        self.source_slot_id = source_slot_id
        self.proc_mgr = proc_mgr
        self.config_mgr = config_mgr
        self.swap_mgr = SwapManager(proc_mgr, config_mgr)
        self.current_mode = "user"
        self.target_slot_to_stop = None

        self.setWindowTitle(f"Swap User Account - Slot #{source_slot_id}")
        self.setWindowIcon(create_minimal_app_icon())
        self.resize(480, 600)
        self.setMinimumWidth(460)

        self.candidates = []
        self.init_ui()
        self.load_data()
        apply_dark_title_bar(self)

    def showEvent(self, event):
        super().showEvent(event)
        apply_dark_title_bar(self)

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #121214;
                color: #e4e4e7;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QLabel {
                color: #e4e4e7;
            }
            QFrame.Card {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 8px;
            }
            QComboBox {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QComboBox QAbstractItemView {
                background-color: #18181b;
                color: #e4e4e7;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
                border: 1px solid #27272a;
                padding: 4px;
            }
            QPushButton {
                background-color: #27272a;
                color: #e4e4e7;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
                min-width: 0px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
            QPushButton.PrimaryBtn {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton.PrimaryBtn:hover {
                background-color: #0369a1;
            }
            QPushButton.PrimaryBtn:disabled {
                background-color: #27272a;
                color: #71717a;
            }
            QPushButton.StopBtn {
                background-color: #dc2626;
                color: #ffffff;
                font-weight: 700;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton.StopBtn:hover {
                background-color: #b91c1c;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header Title
        lbl_title = QLabel("SWAP USER ACCOUNT")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #38bdf8; letter-spacing: 0.5px;")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel("สลับบัญชี Google และโควตาระหว่างสล็อต เพื่อทำงานต่อบนโปรเจกต์เดิมได้ทันที")
        lbl_desc.setStyleSheet("font-size: 10px; color: #a1a1aa;")
        layout.addWidget(lbl_desc)

        # 1. Source Slot Card (Current Slot)
        self.card_source = QFrame()
        self.card_source.setProperty("class", "Card")
        cs_layout = QVBoxLayout(self.card_source)
        cs_layout.setContentsMargins(10, 8, 10, 8)
        cs_layout.setSpacing(4)

        cs_top = QHBoxLayout()
        self.lbl_src_title = QLabel(f"ต้นทาง: Slot #{self.source_slot_id}")
        self.lbl_src_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #38bdf8;")
        cs_top.addWidget(self.lbl_src_title)

        cs_top.addStretch()

        self.lbl_src_status = QLabel("STOPPED")
        self.lbl_src_status.setStyleSheet("font-size: 9px; font-weight: 700; color: #4ade80;")
        cs_top.addWidget(self.lbl_src_status)
        cs_layout.addLayout(cs_top)

        self.lbl_src_account = QLabel("Account: --")
        self.lbl_src_account.setStyleSheet("font-size: 11px; color: #ffffff; font-weight: 600;")
        cs_layout.addWidget(self.lbl_src_account)

        self.lbl_src_quota = QLabel("Quota: G: --% | 5H: --% | W: --")
        self.lbl_src_quota.setStyleSheet("font-size: 10px; color: #a1a1aa;")
        cs_layout.addWidget(self.lbl_src_quota)

        self.lbl_src_projects = QLabel("Projects: --")
        self.lbl_src_projects.setStyleSheet("font-size: 10px; color: #71717a;")
        cs_layout.addWidget(self.lbl_src_projects)

        layout.addWidget(self.card_source)

        # Divider Label
        lbl_divider = QLabel("สลับกับ (SWAP WITH)")
        lbl_divider.setAlignment(Qt.AlignCenter)
        lbl_divider.setStyleSheet("font-size: 10px; font-weight: 700; color: #71717a; padding: 1px 0;")
        layout.addWidget(lbl_divider)

        # 2. Target Slot Selection
        lbl_target_prompt = QLabel("เลือกสล็อตปลายทางที่ต้องการสลับบัญชีด้วย:")
        lbl_target_prompt.setStyleSheet("font-size: 11px; font-weight: 600; color: #e4e4e7;")
        layout.addWidget(lbl_target_prompt)

        self.cb_target = QComboBox()
        self.cb_target.currentIndexChanged.connect(self.on_target_selection_changed)
        layout.addWidget(self.cb_target)

        # Target Slot Preview Card
        self.card_target = QFrame()
        self.card_target.setProperty("class", "Card")
        ct_layout = QVBoxLayout(self.card_target)
        ct_layout.setContentsMargins(10, 8, 10, 8)
        ct_layout.setSpacing(4)

        ct_top = QHBoxLayout()
        self.lbl_tgt_title = QLabel("ปลายทาง: --")
        self.lbl_tgt_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #a78bfa;")
        ct_top.addWidget(self.lbl_tgt_title)

        ct_top.addStretch()

        self.lbl_tgt_status = QLabel("STOPPED")
        self.lbl_tgt_status.setStyleSheet("font-size: 9px; font-weight: 700; color: #4ade80;")
        ct_top.addWidget(self.lbl_tgt_status)
        ct_layout.addLayout(ct_top)

        self.lbl_tgt_account = QLabel("Account: --")
        self.lbl_tgt_account.setStyleSheet("font-size: 11px; color: #ffffff; font-weight: 600;")
        ct_layout.addWidget(self.lbl_tgt_account)

        self.lbl_tgt_quota = QLabel("Quota: G: --% | 5H: --% | W: --")
        self.lbl_tgt_quota.setStyleSheet("font-size: 10px; color: #a1a1aa;")
        ct_layout.addWidget(self.lbl_tgt_quota)

        self.lbl_tgt_projects = QLabel("Projects: --")
        self.lbl_tgt_projects.setStyleSheet("font-size: 10px; color: #71717a;")
        ct_layout.addWidget(self.lbl_tgt_projects)

        layout.addWidget(self.card_target)

        # 3. Swap Mode Options (Interactive Cards with [✓] checkmark)
        lbl_mode_title = QLabel("เลือกโหมดการสลับ (Swap Mode):")
        lbl_mode_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #e4e4e7;")
        layout.addWidget(lbl_mode_title)

        self.card_mode_user = ModeOptionCard(
            mode_id="user",
            title="สลับเฉพาะบัญชีผู้ใช้ (User / Quota)",
            subtitle="คงโปรเจกต์เดิมไว้ที่สล็อตเดิม สลับเฉพาะบัญชี Google / Auth เพื่อใช้งานต่อทันที",
            is_recommended=True
        )
        self.card_mode_user.clicked.connect(self.set_swap_mode)
        layout.addWidget(self.card_mode_user)

        self.card_mode_slot = ModeOptionCard(
            mode_id="slot",
            title="สลับทั้งสล็อต (Full Slot Swap)",
            subtitle="สลับข้อมูลทั้งหมดรวมถึงโปรเจกต์และชื่อสล็อตระหว่าง 2 สล็อต",
            is_recommended=False
        )
        self.card_mode_slot.clicked.connect(self.set_swap_mode)
        layout.addWidget(self.card_mode_slot)

        self.set_swap_mode("user")

        # 4. Status / Safety Alert Banner with Action Button
        self.banner = QFrame()
        b_layout = QHBoxLayout(self.banner)
        b_layout.setContentsMargins(10, 8, 10, 8)
        b_layout.setSpacing(10)

        self.lbl_banner = QLabel()
        self.lbl_banner.setWordWrap(True)
        self.lbl_banner.setStyleSheet("font-size: 10px; font-weight: 600;")
        b_layout.addWidget(self.lbl_banner, 1)

        self.btn_stop_action = QPushButton("Stop Slot")
        self.btn_stop_action.setProperty("class", "StopBtn")
        self.btn_stop_action.clicked.connect(self.on_stop_action_clicked)
        self.btn_stop_action.hide()
        b_layout.addWidget(self.btn_stop_action)

        layout.addWidget(self.banner)

        # 5. Action Buttons (Cancel / Execute Swap)
        btn_box = QHBoxLayout()
        btn_box.setContentsMargins(0, 4, 0, 0)
        btn_box.setSpacing(10)

        btn_box.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_swap = QPushButton("Swap Users")
        self.btn_swap.setProperty("class", "PrimaryBtn")
        self.btn_swap.clicked.connect(self.on_swap_clicked)
        btn_box.addWidget(self.btn_swap)

        layout.addLayout(btn_box)

    def set_swap_mode(self, mode: str):
        self.current_mode = mode
        if mode == "user":
            self.card_mode_user.set_selected(True)
            self.card_mode_slot.set_selected(False)
        else:
            self.card_mode_user.set_selected(False)
            self.card_mode_slot.set_selected(True)

    def load_data(self):
        # โหลดข้อมูล Source Slot
        src = self.swap_mgr.get_slot_summary(self.source_slot_id)
        self.lbl_src_title.setText(f"ต้นทาง: Slot #{src['slot_id']} ({src['name']})")
        self.lbl_src_account.setText(f"Account: {src['email']} ({src['plan']})")
        self.lbl_src_quota.setText(f"Quota: G: {src['gemini_pct']}% | 5H: {src['rolling_5h_pct']}% ({src['reset_5h_str']}) | W: {src['weekly_str']}")
        proj_str = ", ".join(src['projects']) if src['projects'] else "(ไม่มีโปรเจกต์)"
        self.lbl_src_projects.setText(f"Projects: {proj_str}")

        if src["is_running"]:
            self.lbl_src_status.setText("RUNNING")
            self.lbl_src_status.setStyleSheet("font-size: 9px; font-weight: 700; color: #ef4444;")
        else:
            self.lbl_src_status.setText("STOPPED")
            self.lbl_src_status.setStyleSheet("font-size: 9px; font-weight: 700; color: #4ade80;")

        # โหลดรายการ Candidates
        self.candidates = self.swap_mgr.get_swap_candidates(self.source_slot_id)
        self.cb_target.blockSignals(True)
        self.cb_target.clear()

        if not self.candidates:
            self.cb_target.addItem("ไม่มีสล็อตอื่นให้เลือก Swap", None)
            self.cb_target.blockSignals(False)
            self.btn_swap.setEnabled(False)
            self.set_banner(
                "ไม่พบสล็อตอื่นสำหรับทำการสลับบัญชี",
                is_error=True
            )
            return

        default_idx = 0
        found_stopped = False

        for idx, cand in enumerate(self.candidates):
            sid = cand["slot_id"]
            name = cand["name"]
            email = cand["email"]
            g_pct = cand["gemini_pct"]
            h_pct = cand["rolling_5h_pct"]
            status_tag = "[RUNNING: ห้ามสลับ]" if cand["is_running"] else f"(G: {g_pct}% | 5H: {h_pct}%) [STOPPED]"
            item_text = f"Slot #{sid}: {email} - {status_tag}"
            self.cb_target.addItem(item_text, cand)

            # เลือกสล็อตแรกที่ STOPPED เป็นค่าเริ่มต้นอัตโนมัติ เพื่อให้ผู้ใช้กด Swap ได้ทันที
            if not cand["is_running"] and not found_stopped:
                default_idx = idx
                found_stopped = True

        self.cb_target.blockSignals(False)
        self.cb_target.setCurrentIndex(default_idx)
        self.on_target_selection_changed(default_idx)

    def on_target_selection_changed(self, index: int):
        cand = self.cb_target.currentData()
        if not cand:
            self.btn_swap.setEnabled(False)
            return

        # อัปเดต Target Card Preview
        self.lbl_tgt_title.setText(f"ปลายทาง: Slot #{cand['slot_id']} ({cand['name']})")
        self.lbl_tgt_account.setText(f"Account: {cand['email']} ({cand['plan']})")
        self.lbl_tgt_quota.setText(f"Quota: G: {cand['gemini_pct']}% | 5H: {cand['rolling_5h_pct']}% ({cand['reset_5h_str']}) | W: {cand['weekly_str']}")
        proj_str = ", ".join(cand['projects']) if cand['projects'] else "(ไม่มีโปรเจกต์)"
        self.lbl_tgt_projects.setText(f"Projects: {proj_str}")

        if cand["is_running"]:
            self.lbl_tgt_status.setText("RUNNING")
            self.lbl_tgt_status.setStyleSheet("font-size: 9px; font-weight: 700; color: #ef4444;")
        else:
            self.lbl_tgt_status.setText("STOPPED")
            self.lbl_tgt_status.setStyleSheet("font-size: 9px; font-weight: 700; color: #4ade80;")

        # ตรวจสอบเงื่อนไขความปลอดภัย: ทั้ง 2 สล็อตต้อง STOPPED เท่านั้น
        is_src_running = self.proc_mgr.is_running(self.source_slot_id)
        is_tgt_running = cand["is_running"]

        if is_src_running:
            self.target_slot_to_stop = self.source_slot_id
            self.set_banner(
                f"ไม่อนุญาตให้สลับ: สล็อตต้นทาง (Slot #{self.source_slot_id}) กำลังทำงานอยู่ (RUNNING)\nกดปุ่ม 'Stop' ด้านขวาเพื่อหยุดการทำงานและปลดล็อกการ Swap ทันที",
                is_error=True,
                stop_slot_id=self.source_slot_id
            )
            self.btn_swap.setEnabled(False)
            self.btn_swap.setToolTip(f"สล็อต #{self.source_slot_id} กำลังทำงานอยู่ กรุณากด Stop ก่อน")
        elif is_tgt_running:
            self.target_slot_to_stop = cand["slot_id"]
            self.set_banner(
                f"ไม่อนุญาตให้สลับ: สล็อตปลายทาง (Slot #{cand['slot_id']}) กำลังทำงานอยู่ (RUNNING)\nกดปุ่ม 'Stop' ด้านขวาเพื่อหยุดการทำงานและปลดล็อกการ Swap ทันที",
                is_error=True,
                stop_slot_id=cand["slot_id"]
            )
            self.btn_swap.setEnabled(False)
            self.btn_swap.setToolTip(f"สล็อต #{cand['slot_id']} กำลังทำงานอยู่ กรุณากด Stop ก่อน")
        else:
            self.target_slot_to_stop = None
            self.set_banner(
                f"พร้อมสลับ: ทั้ง Slot #{self.source_slot_id} และ Slot #{cand['slot_id']} อยู่ในสถานะ STOPPED อย่างปลอดภัย",
                is_error=False
            )
            self.btn_swap.setEnabled(True)
            self.btn_swap.setToolTip("คลิกเพื่อยืนยันการสลับบัญชีผู้ใช้")

    def set_banner(self, text: str, is_error: bool = False, stop_slot_id: int = None):
        self.lbl_banner.setText(text)
        if is_error:
            self.banner.setStyleSheet("""
                QFrame {
                    background-color: #450a0a;
                    border: 1px solid #dc2626;
                    border-radius: 4px;
                }
            """)
            self.lbl_banner.setStyleSheet("color: #fca5a5; font-size: 10px; font-weight: 600;")
            if stop_slot_id:
                self.btn_stop_action.setText(f"Stop #{stop_slot_id}")
                self.btn_stop_action.show()
            else:
                self.btn_stop_action.hide()
        else:
            self.banner.setStyleSheet("""
                QFrame {
                    background-color: #064e3b;
                    border: 1px solid #10b981;
                    border-radius: 4px;
                }
            """)
            self.lbl_banner.setStyleSheet("color: #a7f3d0; font-size: 10px; font-weight: 600;")
            self.btn_stop_action.hide()

    def on_stop_action_clicked(self):
        if not self.target_slot_to_stop:
            return

        sid = self.target_slot_to_stop
        self.btn_stop_action.setEnabled(False)
        self.btn_stop_action.setText(f"Stopping #{sid}...")
        self.proc_mgr.stop_slot(sid)

        # รอ 0.5 วินาทีให้โปรเซสปิดตัวลงเรียบร้อย
        time.sleep(0.5)

        self.btn_stop_action.setEnabled(True)
        self.load_data()

    def on_swap_clicked(self):
        cand = self.cb_target.currentData()
        if not cand:
            return

        target_slot_id = cand["slot_id"]
        swap_mode = self.current_mode

        src_email = self.lbl_src_account.text().replace("Account: ", "")
        tgt_email = cand["email"]

        mode_desc = (
            f"- สล็อต #{self.source_slot_id} จะเปลี่ยนไปใช้บัญชี: {tgt_email}\n"
            f"- สล็อต #{target_slot_id} จะเปลี่ยนไปใช้บัญชี: {src_email}\n"
            f"- โฟลเดอร์โปรเจกต์เดิมจะยังคงอยู่ที่สล็อตเดิมทั้งสองฝั่ง"
            if swap_mode == "user" else
            f"- สล็อต #{self.source_slot_id} และ #{target_slot_id} จะสลับข้อมูลทั้งหมดรวมทั้งโปรเจกต์"
        )

        reply = QMessageBox.question(
            self,
            "ยืนยันการ Swap บัญชี",
            f"ยืนยันการสลับข้อมูลระหว่าง Slot #{self.source_slot_id} และ Slot #{target_slot_id}?\n\n"
            f"{mode_desc}\n\n"
            f"ต้องการดำเนินการต่อหรือไม่?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # ดำเนินการ Swap
        self.btn_swap.setEnabled(False)
        self.btn_cancel.setEnabled(False)

        ok, msg = self.swap_mgr.swap_users(self.source_slot_id, target_slot_id, swap_mode=swap_mode)

        self.btn_swap.setEnabled(True)
        self.btn_cancel.setEnabled(True)

        if ok:
            QMessageBox.information(
                self,
                "Swap สำเร็จ",
                f"{msg}\n\nระบบจะทำการรีเฟรชข้อมูลของทุกสล็อตบนหน้าต่าง MultiAgIDE Studio ทันที"
            )
            self.swap_completed.emit(self.source_slot_id, target_slot_id)
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "ไม่สามารถสลับได้",
                f"เกิดข้อผิดพลาด:\n{msg}"
            )
