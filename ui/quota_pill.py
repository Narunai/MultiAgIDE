from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from core.quota_service import QuotaInfo


class QuotaPillWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("QuotaPill")
        self.setStyleSheet("""
            QFrame#QuotaPill {
                background-color: #121820;
                border: 1px solid #1f2937;
                border-radius: 10px;
                padding: 4px 8px;
            }
            QLabel {
                font-family: 'Segoe UI', Consolas, monospace;
            }
        """)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(2)

        # Row 1: G: 99%   5H: 97%   ●
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.lbl_g = QLabel("<b style='color: #38bdf8;'>G:</b> <b>--%</b>")
        self.lbl_g.setStyleSheet("color: #ffffff; font-size: 11px;")
        row1.addWidget(self.lbl_g)

        self.lbl_5h = QLabel("<b style='color: #818cf8;'>5H:</b> <b>--%</b>")
        self.lbl_5h.setStyleSheet("color: #ffffff; font-size: 11px;")
        row1.addWidget(self.lbl_5h)

        row1.addStretch()

        self.dot = QLabel("●")
        self.dot.setStyleSheet("color: #64748b; font-size: 11px;")
        row1.addWidget(self.dot)

        main_layout.addLayout(row1)

        # Row 2: W: 6d 23h   5H: 4h 51m
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.lbl_w_reset = QLabel("W: --")
        self.lbl_w_reset.setStyleSheet("color: #94a3b8; font-size: 10px;")
        row2.addWidget(self.lbl_w_reset)

        self.lbl_5h_reset = QLabel("5H: --")
        self.lbl_5h_reset.setStyleSheet("color: #94a3b8; font-size: 10px;")
        row2.addWidget(self.lbl_5h_reset)

        row2.addStretch()

        self.lbl_account = QLabel("")
        self.lbl_account.setStyleSheet("color: #64748b; font-size: 9px;")
        row2.addWidget(self.lbl_account)

        main_layout.addLayout(row2)

    def update_quota(self, q: QuotaInfo):
        if q.connected:
            self.lbl_g.setText(f"<b style='color: #38bdf8;'>G:</b> <b>{q.gemini_pct}%</b>")
            self.lbl_5h.setText(f"<b style='color: #818cf8;'>5H:</b> <b>{q.rolling_5h_pct}%</b>")
            self.lbl_w_reset.setText(f"W: {q.weekly_str}")
            self.lbl_5h_reset.setText(f"5H: {q.reset_5h_str}")
            self.dot.setStyleSheet("color: #10b981; font-size: 12px;")  # Green active
            email_short = q.email.split("@")[0] if "@" in q.email else q.email
            self.lbl_account.setText(email_short)
            self.setToolTip(f"บัญชี: {q.email}\nแพ็กเกจ: {q.plan}\nGemini Quota: {q.gemini_pct}%\nรีเซ็ต 5 ชม.: {q.reset_5h_str}")
        else:
            self.lbl_g.setText("<b style='color: #64748b;'>G:</b> <span style='color: #94a3b8;'>--%</span>")
            self.lbl_5h.setText("<b style='color: #64748b;'>5H:</b> <span style='color: #94a3b8;'>--%</span>")
            self.lbl_w_reset.setText("W: --")
            self.lbl_5h_reset.setText("5H: --")
            self.dot.setStyleSheet("color: #475569; font-size: 12px;")  # Gray offline
            self.lbl_account.setText("offline")
            self.setToolTip("ยังไม่ได้เปิด Antigravity IDE ในสล็อตนี้")
