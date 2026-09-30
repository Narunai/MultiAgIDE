from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal
from core.quota_service import QuotaInfo


class ClickableAccountLabel(QLabel):
    clicked = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)


class QuotaPillWidget(QFrame):
    """
    Minimal Flat Dark Quota Strip (No Icons)
    ความสูงคงที่ 30px สไตล์ Minimalist ตัวหนังสือคมชัด
    """
    user_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("QuotaPill")
        self.setFixedHeight(30)
        self.setCursor(Qt.PointingHandCursor)
        self.init_ui()

    def mousePressEvent(self, event):
        event.ignore()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 2, 6, 2)
        main_layout.setSpacing(1)

        # Row 1: G: 92%    5H: 92%    [ON/OFF]
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(6)

        self.lbl_g = QLabel("<b style='color: #38bdf8;'>G:</b> <b>--%</b>")
        self.lbl_g.setStyleSheet("font-size: 10px;")
        row1.addWidget(self.lbl_g)

        self.lbl_5h = QLabel("<b style='color: #a78bfa;'>5H:</b> <b>--%</b>")
        self.lbl_5h.setStyleSheet("font-size: 10px;")
        row1.addWidget(self.lbl_5h)

        row1.addStretch()

        self.status_tag = QLabel("OFF")
        self.status_tag.setStyleSheet("color: #52525b; font-size: 9px; font-weight: 700;")
        row1.addWidget(self.status_tag)

        main_layout.addLayout(row1)

        # Row 2: W: 6d 23h    5H: 4h 51m    user@email
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(6)

        self.lbl_w_reset = QLabel("W: --")
        self.lbl_w_reset.setStyleSheet("color: #71717a; font-size: 9px;")
        row2.addWidget(self.lbl_w_reset)

        self.lbl_5h_reset = QLabel("5H: --")
        self.lbl_5h_reset.setStyleSheet("color: #71717a; font-size: 9px;")
        row2.addWidget(self.lbl_5h_reset)

        row2.addStretch()

        self.lbl_account = ClickableAccountLabel("offline")
        self.lbl_account.setStyleSheet("""
            QLabel {
                color: #71717a;
                font-size: 9px;
            }
            QLabel:hover {
                color: #38bdf8;
                text-decoration: underline;
            }
        """)
        self.lbl_account.setToolTip("คลิกเพื่อสลับบัญชีผู้ใช้ (Swap User) กับสล็อตอื่น")
        self.lbl_account.clicked.connect(self.user_clicked.emit)
        row2.addWidget(self.lbl_account)

        main_layout.addLayout(row2)

    def update_quota(self, q: QuotaInfo, is_running: bool = False, is_last_used: bool = False, is_empty: bool = False, is_cooldown_finished: bool = False, is_generating: bool = False):
        email_short = q.email.split("@")[0] if ("@" in q.email and q.email != "offline") else q.email

        if is_running:
            self.lbl_g.setText(f"<b style='color: #38bdf8;'>G:</b> <b>{q.gemini_pct}%</b>")
            self.lbl_5h.setText(f"<b style='color: #a78bfa;'>5H:</b> <b>{q.rolling_5h_pct}%</b>")
            self.lbl_w_reset.setText(f"W: {q.weekly_str}")
            self.lbl_5h_reset.setText(f"5H: {q.reset_5h_str}")
            if is_generating:
                self.status_tag.setText("GENERATING")
                self.status_tag.setStyleSheet("color: #fbbf24; font-size: 8px; font-weight: 700;") # Amber/Yellow warning color
                status_text = "กำลังเจนคำตอบ (GENERATING...)"
            else:
                self.status_tag.setText("ACTIVE")
                self.status_tag.setStyleSheet("color: #4ade80; font-size: 8px; font-weight: 700;")
                status_text = "กำลังทำงาน (RUNNING)"

            self.lbl_account.setText(email_short)
            self.lbl_account.setStyleSheet("color: #a1a1aa; font-size: 9px;")
            self.setToolTip(
                f"บัญชี: {q.email}\n"
                f"สถานะ: {status_text}\n"
                f"Gemini Quota: {q.gemini_pct}% (รีเซ็ต: {q.weekly_str})\n"
                f"5-Hour Quota: {q.rolling_5h_pct}% (รีเซ็ต: {q.reset_5h_str})"
            )
        else:
            # STOPPED Mode: แสดงโควตาล่าสุดที่บันทึกไว้ เพื่อให้ผู้ใช้ตัดสินใจได้ถูกต้อง
            if is_cooldown_finished:
                # Cooldown เสร็จแล้ว ให้แสดงสีเขียวถึงแม้เปอร์เซ็นต์จะเป็นศูนย์
                self.lbl_g.setText(f"<b style='color: #4ade80;'>G:</b> <span style='color: #86efac; font-weight: 600;'>{q.gemini_pct}%</span>")
                self.lbl_5h.setText(f"<b style='color: #4ade80;'>5H:</b> <span style='color: #86efac; font-weight: 600;'>{q.rolling_5h_pct}%</span>")
            elif is_empty or q.gemini_pct <= 5:
                # โควตาหมดแล้ว -> สีส้มแดงเตือนภัย
                self.lbl_g.setText(f"<b style='color: #f87171;'>G:</b> <span style='color: #f87171; font-weight: 700;'>{q.gemini_pct}%</span>")
                self.lbl_5h.setText(f"<b style='color: #f87171;'>5H:</b> <span style='color: #f87171; font-weight: 700;'>{q.rolling_5h_pct}%</span>")
            elif q.gemini_pct >= 90:
                # โควตาเต็ม -> สีเขียวพร้อมใช้งาน
                self.lbl_g.setText(f"<b style='color: #4ade80;'>G:</b> <span style='color: #86efac; font-weight: 600;'>{q.gemini_pct}%</span>")
                self.lbl_5h.setText(f"<b style='color: #4ade80;'>5H:</b> <span style='color: #86efac; font-weight: 600;'>{q.rolling_5h_pct}%</span>")
            else:
                self.lbl_g.setText(f"<b style='color: #71717a;'>G:</b> <span style='color: #d4d4d8;'>{q.gemini_pct}%</span>")
                self.lbl_5h.setText(f"<b style='color: #71717a;'>5H:</b> <span style='color: #d4d4d8;'>{q.rolling_5h_pct}%</span>")

            self.lbl_w_reset.setText(f"W: {q.weekly_str}")
            self.lbl_5h_reset.setText(f"5H: {q.reset_5h_str}")

            # แท็กสถานะ: แยกความสำคัญชัดเจน
            if is_cooldown_finished:
                self.status_tag.setText("READY")
                self.status_tag.setStyleSheet("color: #22c55e; font-size: 8px; font-weight: 700;")
            elif is_last_used:
                self.status_tag.setText("LAST USED")
                self.status_tag.setStyleSheet("color: #38bdf8; font-size: 8px; font-weight: 700;")
            elif is_empty or (q.gemini_pct <= 5 and q.rolling_5h_pct <= 5):
                self.status_tag.setText("EMPTY")
                self.status_tag.setStyleSheet("color: #ef4444; font-size: 8px; font-weight: 700;")
            elif q.gemini_pct >= 90:
                self.status_tag.setText("READY")
                self.status_tag.setStyleSheet("color: #22c55e; font-size: 8px; font-weight: 700;")
            else:
                self.status_tag.setText("OFF")
                self.status_tag.setStyleSheet("color: #71717a; font-size: 9px; font-weight: 700;")

            self.lbl_account.setText(email_short)
            self.lbl_account.setStyleSheet("color: #71717a; font-size: 9px;")

            tip_lines = [
                f"บัญชี: {q.email}",
                f"สถานะ: ปิดอยู่ (STOPPED)",
                f"โควตาล่าสุด: Gemini {q.gemini_pct}% | 5H {q.rolling_5h_pct}%",
                f"เวลารีเซ็ต: 5H ({q.reset_5h_str}) | สัปดาห์ ({q.weekly_str})"
            ]
            if is_cooldown_finished:
                tip_lines.append("[READY] Cooldown เสร็จสิ้นแล้ว พร้อมใช้งาน (กดเปิดเพื่อรีเฟรชโควตา)")
            elif is_last_used:
                tip_lines.append("[LAST USED] บัญชีนี้ถูกเปิดใช้งานล่าสุด")
            if is_empty or q.gemini_pct <= 5:
                tip_lines.append("[EMPTY] โควตาหมดแล้ว! หลีกเลี่ยงการเปิดสล็อตนี้ชั่วคราว")
            elif q.gemini_pct >= 90 and not is_cooldown_finished:
                tip_lines.append("[READY] โควตาเต็มพร้อมใช้งาน")
            self.setToolTip("\n".join(tip_lines))
