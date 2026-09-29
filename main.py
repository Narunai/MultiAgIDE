import sys
import os
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from ui.dashboard_window import DashboardWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MultiAgIDE Studio")
    app.setOrganizationName("MultiAgIDE")

    window = DashboardWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
