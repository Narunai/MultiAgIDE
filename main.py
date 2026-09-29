import sys
import os
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from ui.dashboard_window import DashboardWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MultiAgIDE Studio")
    app.setOrganizationName("MultiAgIDE")

    # Global Dark Palette - ป้องกันไม่ให้เกิดสีขาวหลุดรอดในทุก Widget & DWM Thumbnail
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0b0f17"))
    palette.setColor(QPalette.WindowText, QColor("#f1f5f9"))
    palette.setColor(QPalette.Base, QColor("#0f172a"))
    palette.setColor(QPalette.AlternateBase, QColor("#1e293b"))
    palette.setColor(QPalette.ToolTipBase, QColor("#1e293b"))
    palette.setColor(QPalette.ToolTipText, QColor("#f1f5f9"))
    palette.setColor(QPalette.Text, QColor("#f1f5f9"))
    palette.setColor(QPalette.Button, QColor("#1e293b"))
    palette.setColor(QPalette.ButtonText, QColor("#f1f5f9"))
    palette.setColor(QPalette.Highlight, QColor("#2563eb"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    window = DashboardWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
