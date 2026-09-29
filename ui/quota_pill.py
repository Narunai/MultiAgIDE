from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from core.quota_service import QuotaInfo


class QuotaPillWidget(QFrame):
    """
    Minimal Flat Dark Quota Strip (No Icons)
    ความสูงคงที่ 30px สไตล์ Minimalist ตัวหนังสือคมชัด
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("QuotaPill")
        self.setFixedHeight(30)
        self.init_ui()

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

        self.lbl_account = QLabel("offline")
        self.lbl_account.setStyleSheet("color: #52525b; font-size: 9px;")
        row2.addWidget(self.lbl_account)

        main_layout.addLayout(row2)

    def update_quota(self, q: QuotaInfo):
        if q.connected:
            self.lbl_g.setText(f"<b style='color: #38bdf8;'>G:</b> <b>{q.gemini_pct}%</b>")
            self.lbl_5h.setText(f"<b style='color: #a78bfa;'>5H:</b> <b>{q.rolling_5h_pct}%</b>")
            self.lbl_w_reset.setText(f"W: {q.weekly_str}")
            self.lbl_5h_reset.setText(f"5H: {q.reset_5h_str}")
            self.status_tag.setText("ACTIVE")
            self.status_tag.setStyleSheet("color: #4ade80; font-size: 9px; font-weight: 700;")
            email_short = q.email.split("@")[0] if "@" in q.email else q.email
            self.lbl_account.setText(email_short)
            self.lbl_account.setStyleSheet("color: #a1a1aa; font-size: 9px;")
            self.setToolTip(f"อีเมล: {q.email}\nแพ็กเกจ: {q.plan}\nGemini Quota: {q.gemini_pct}%\nรีเซ็ต 5 ชม.: {q.reset_5h_str}")
        else:
            self.lbl_g.setText("<b style='color: #52525b;'>G:</b> <span style='color: #71717a;'>--%</span>")
            self.lbl_5h.setText("<b style='color: #52525b;'>5H:</b> <span style='color: #71717a;'>--%</span>")
            self.lbl_w_reset.setText("W: --")
            self.lbl_5h_reset.setText("5H: --")
            self.status_tag.setText("OFF")
            self.status_tag.setStyleSheet("color: #52525b; font-size: 9px; font-weight: 700;")
            self.lbl_account.setText("offline")
            self.lbl_account.setStyleSheet("color: #52525b; font-size: 9px;")
            self.setToolTip("ยังไม่ได้เปิด Antigravity IDE ในสล็อตนี้")
