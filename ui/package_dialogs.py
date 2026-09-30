import os
import sys
import threading
import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QCheckBox, QProgressBar, QFileDialog, QScrollArea, QWidget, QFrame,
    QRadioButton, QButtonGroup, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, Signal, QObject

from core.package_manager import PackageManager
from .dark_title_bar import apply_dark_title_bar, create_minimal_app_icon


class WorkerSignals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(dict)
    error = Signal(str)


class ExportDialog(QDialog):
    """
    หน้าต่าง Export MultiAgIDE Package
    รวบรวมโปรเจกต์, บัญชี Google, Auth Token, Sessions, Extensions ออกมาเป็นไฟล์เดียวเพื่อย้ายเครื่อง
    """
    def __init__(self, package_mgr: PackageManager, parent=None):
        super().__init__(parent)
        self.pkg_mgr = package_mgr
        self.setWindowTitle("Export Package - MultiAgIDE Studio")
        self.setWindowIcon(create_minimal_app_icon())
        self.resize(500, 580)
        self.setMinimumWidth(460)

        self.slot_checkboxes = {}
        self.is_exporting = False

        self.init_ui()
        self.load_slots()
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
                padding: 10px;
            }
            QPushButton {
                background-color: #27272a;
                color: #e4e4e7;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3f3f46;
                color: #ffffff;
            }
            QPushButton.PrimaryBtn {
                background-color: #0284c7;
                color: #ffffff;
            }
            QPushButton.PrimaryBtn:hover {
                background-color: #0369a1;
            }
            QPushButton.SuccessBtn {
                background-color: #15803d;
                color: #ffffff;
            }
            QPushButton.SuccessBtn:hover {
                background-color: #166534;
            }
            QLineEdit {
                background-color: #09090b;
                border: 1px solid #27272a;
                border-radius: 4px;
                color: #fafafa;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #38bdf8;
            }
            QCheckBox {
                color: #d4d4d8;
                font-size: 11px;
                spacing: 6px;
            }
            QProgressBar {
                background-color: #09090b;
                border: 1px solid #27272a;
                border-radius: 4px;
                text-align: center;
                color: #e4e4e7;
                font-size: 10px;
                height: 14px;
            }
            QProgressBar::chunk {
                background-color: #0284c7;
                border-radius: 3px;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header
        header = QLabel("EXPORT PACKAGE")
        header.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: 800; letter-spacing: 0.5px;")
        layout.addWidget(header)

        desc = QLabel(
            "Bundle slot profiles, Google auth tokens, sessions, extensions, and workspaces\n"
            "into a single portable archive for migrating to another computer."
        )
        desc.setStyleSheet("color: #71717a; font-size: 10px; line-height: 14px;")
        layout.addWidget(desc)

        # 1. Slot Selection Card
        slots_card = QFrame()
        slots_card.setProperty("class", "Card")
        sc_layout = QVBoxLayout(slots_card)
        sc_layout.setContentsMargins(10, 8, 10, 8)
        sc_layout.setSpacing(6)

        sc_head = QHBoxLayout()
        sc_title = QLabel("Select Slots to Export:")
        sc_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #a1a1aa;")
        sc_head.addWidget(sc_title)
        sc_head.addStretch()

        btn_all = QPushButton("Select All")
        btn_all.setFixedHeight(20)
        btn_all.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        btn_all.clicked.connect(self.select_all_slots)
        sc_head.addWidget(btn_all)

        btn_none = QPushButton("Clear")
        btn_none.setFixedHeight(20)
        btn_none.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        btn_none.clicked.connect(self.clear_all_slots)
        sc_head.addWidget(btn_none)
        sc_layout.addLayout(sc_head)

        # Scroll Area for slots
        self.slots_scroll = QScrollArea()
        self.slots_scroll.setWidgetResizable(True)
        self.slots_scroll.setFixedHeight(140)
        self.slots_widget = QWidget()
        self.slots_layout = QVBoxLayout(self.slots_widget)
        self.slots_layout.setContentsMargins(4, 4, 4, 4)
        self.slots_layout.setSpacing(4)
        self.slots_scroll.setWidget(self.slots_widget)
        sc_layout.addWidget(self.slots_scroll)

        layout.addWidget(slots_card)

        # 2. Options Card
        opt_card = QFrame()
        opt_card.setProperty("class", "Card")
        opt_layout = QVBoxLayout(opt_card)
        opt_layout.setContentsMargins(10, 8, 10, 8)
        opt_layout.setSpacing(6)

        self.cb_workspaces = QCheckBox("Include Projects & Workspaces (All project code & files)")
        self.cb_workspaces.setChecked(True)
        opt_layout.addWidget(self.cb_workspaces)

        self.cb_caches = QCheckBox("Exclude volatile GPU/Browser Caches (Recommended: Faster & Cross-PC Safe)")
        self.cb_caches.setChecked(True)
        self.cb_caches.setToolTip("GPU and shader caches will be cleanly rebuilt by Chromium on the new machine.")
        opt_layout.addWidget(self.cb_caches)

        self.cb_auth = QCheckBox("Preserve Google Auth, Sessions & Login State (100% Isolated Tokens)")
        self.cb_auth.setChecked(True)
        self.cb_auth.setEnabled(False)  # Always included
        opt_layout.addWidget(self.cb_auth)

        layout.addWidget(opt_card)

        # 3. Output Destination
        dest_card = QFrame()
        dest_card.setProperty("class", "Card")
        dest_layout = QVBoxLayout(dest_card)
        dest_layout.setContentsMargins(10, 8, 10, 8)
        dest_layout.setSpacing(4)

        dest_title = QLabel("Save Destination:")
        dest_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #a1a1aa;")
        dest_layout.addWidget(dest_title)

        dest_row = QHBoxLayout()
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        default_filename = f"MultiAgIDE_Package_{now_str}.zip"
        default_path = os.path.join(os.path.expanduser("~"), "Desktop", default_filename)

        self.dest_edit = QLineEdit(default_path)
        dest_row.addWidget(self.dest_edit, 1)

        btn_browse_folder = QPushButton("Folder...")
        btn_browse_folder.setFixedHeight(26)
        btn_browse_folder.setToolTip("เลือกโฟลเดอร์ปลายทางที่จะบันทึกไฟล์")
        btn_browse_folder.clicked.connect(self.browse_folder)
        dest_row.addWidget(btn_browse_folder)

        btn_browse_file = QPushButton("File...")
        btn_browse_file.setFixedHeight(26)
        btn_browse_file.setToolTip("เลือกตำแหน่งและระบุชื่อไฟล์ .zip")
        btn_browse_file.clicked.connect(self.browse_output)
        dest_row.addWidget(btn_browse_file)
        dest_layout.addLayout(dest_row)

        layout.addWidget(dest_card)

        # 4. Progress Bar & Status
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.hide()
        layout.addWidget(self.prog_bar)

        self.status_lbl = QLabel("Ready to export.")
        self.status_lbl.setStyleSheet("color: #71717a; font-size: 10px;")
        layout.addWidget(self.status_lbl)

        # 5. Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        self.btn_open_folder = QPushButton("Open Folder")
        self.btn_open_folder.hide()
        self.btn_open_folder.clicked.connect(self.open_output_folder)
        btn_box.addWidget(self.btn_open_folder)

        btn_box.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_export = QPushButton("Start Export")
        self.btn_export.setProperty("class", "PrimaryBtn")
        self.btn_export.setFixedHeight(28)
        self.btn_export.clicked.connect(self.start_export)
        btn_box.addWidget(self.btn_export)

        layout.addLayout(btn_box)

    def load_slots(self):
        slots = self.pkg_mgr.get_exportable_slots()
        self.slot_checkboxes.clear()

        # Clear layout
        while self.slots_layout.count():
            item = self.slots_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for s in slots:
            sid = s["id"]
            name = s["name"]
            email = s["email"]
            projs = s["projects"]
            proj_str = f" [{len(projs)} project{'s' if len(projs) > 1 else ''}: {', '.join(projs)}]" if projs else ""

            cb = QCheckBox(f"Slot #{sid:2d}: {name} ({email}){proj_str}")
            cb.setChecked(True)
            self.slot_checkboxes[sid] = cb
            self.slots_layout.addWidget(cb)

        self.slots_layout.addStretch()

    def select_all_slots(self):
        for cb in self.slot_checkboxes.values():
            cb.setChecked(True)

    def clear_all_slots(self):
        for cb in self.slot_checkboxes.values():
            cb.setChecked(False)

    def browse_output(self):
        f, _ = QFileDialog.getSaveFileName(
            self,
            "Save MultiAgIDE Package",
            self.dest_edit.text(),
            "Zip Archive (*.zip);;MultiAgIDE Package (*.magpkg);;All Files (*.*)"
        )
        if f:
            self.dest_edit.setText(f)

    def browse_folder(self):
        curr = self.dest_edit.text().strip()
        start_dir = os.path.dirname(curr) if curr else os.path.join(os.path.expanduser("~"), "Desktop")
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder", start_dir)
        if folder:
            now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"MultiAgIDE_Package_{now_str}.zip"
            self.dest_edit.setText(os.path.join(folder, filename))

    def start_export(self):
        if self.is_exporting:
            return

        selected_sids = [sid for sid, cb in self.slot_checkboxes.items() if cb.isChecked()]
        if not selected_sids:
            QMessageBox.warning(self, "No Slots Selected", "Please select at least one slot to export.")
            return

        out_path = self.dest_edit.text().strip()
        if not out_path:
            QMessageBox.warning(self, "Invalid Path", "Please specify a destination file path.")
            return

        self.is_exporting = True
        self.btn_export.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.prog_bar.show()
        self.prog_bar.setValue(0)
        self.status_lbl.setText("Packaging profiles, auth tokens, and projects...")

        self.signals = WorkerSignals()
        self.signals.progress.connect(self.on_export_progress)
        self.signals.finished.connect(self.on_export_finished)
        self.signals.error.connect(self.on_export_error)

        inc_ws = self.cb_workspaces.isChecked()
        exc_cache = self.cb_caches.isChecked()

        def run_thread():
            try:
                res = self.pkg_mgr.export_package(
                    out_path,
                    slot_ids=selected_sids,
                    include_workspaces=inc_ws,
                    exclude_transient_caches=exc_cache,
                    progress_callback=lambda cur, tot, name: self.signals.progress.emit(cur, tot, name)
                )
                self.signals.finished.emit(res)
            except Exception as e:
                self.signals.error.emit(str(e))

        threading.Thread(target=run_thread, daemon=True).start()

    def on_export_progress(self, current: int, total: int, filename: str):
        pct = int((current / max(1, total)) * 100)
        self.prog_bar.setValue(pct)
        # Display short filename
        short_name = os.path.basename(filename)
        self.status_lbl.setText(f"Exporting ({pct}%): {short_name}")

    def on_export_finished(self, result: dict):
        self.is_exporting = False
        self.btn_export.hide()
        self.btn_cancel.setText("Done")
        self.btn_cancel.setEnabled(True)
        self.btn_open_folder.show()
        self.prog_bar.setValue(100)

        size_mb = result["archive_size_bytes"] / (1024 * 1024)
        slots_count = len(result["slots_exported"])
        self.status_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: 700;")
        self.status_lbl.setText(
            f"Export Complete! Package size: {size_mb:.1f} MB ({result['files_count']} files, {slots_count} slots)"
        )

        QMessageBox.information(
            self,
            "Export Successful",
            f"Successfully packaged {slots_count} slots into:\n\n{result['output_path']}\n\n"
            f"Size: {size_mb:.1f} MB\n"
            "This package can now be copied to any computer and imported with full auth and projects intact!"
        )

    def on_export_error(self, err_msg: str):
        self.is_exporting = False
        self.btn_export.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.status_lbl.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 700;")
        self.status_lbl.setText(f"Export Error: {err_msg}")
        QMessageBox.critical(self, "Export Failed", f"An error occurred during export:\n\n{err_msg}")

    def open_output_folder(self):
        p = self.dest_edit.text().strip()
        folder = os.path.dirname(p)
        if os.path.exists(folder):
            os.startfile(folder)


class ImportDialog(QDialog):
    """
    หน้าต่าง Import MultiAgIDE Package
    นำเข้าและกู้คืนโปรเจกต์, บัญชี Google, Auth Token, Sessions เข้าเครื่องใหม่โดยอัตโนมัติ
    """
    import_completed = Signal(dict)

    def __init__(self, package_mgr: PackageManager, parent=None):
        super().__init__(parent)
        self.pkg_mgr = package_mgr
        self.setWindowTitle("Import Package - MultiAgIDE Studio")
        self.setWindowIcon(create_minimal_app_icon())
        self.resize(500, 560)
        self.setMinimumWidth(460)

        self.inspected_data = None
        self.is_importing = False

        self.init_ui()
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
                padding: 10px;
            }
            QPushButton {
                background-color: #27272a;
                color: #e4e4e7;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3f3f46;
                color: #ffffff;
            }
            QPushButton.PrimaryBtn {
                background-color: #0284c7;
                color: #ffffff;
            }
            QPushButton.PrimaryBtn:hover {
                background-color: #0369a1;
            }
            QLineEdit {
                background-color: #09090b;
                border: 1px solid #27272a;
                border-radius: 4px;
                color: #fafafa;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #38bdf8;
            }
            QRadioButton {
                color: #d4d4d8;
                font-size: 11px;
                spacing: 6px;
            }
            QProgressBar {
                background-color: #09090b;
                border: 1px solid #27272a;
                border-radius: 4px;
                text-align: center;
                color: #e4e4e7;
                font-size: 10px;
                height: 14px;
            }
            QProgressBar::chunk {
                background-color: #0284c7;
                border-radius: 3px;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header
        header = QLabel("IMPORT PACKAGE")
        header.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: 800; letter-spacing: 0.5px;")
        layout.addWidget(header)

        desc = QLabel(
            "Restore slot profiles, Google auth sessions, and projects into this machine.\n"
            "Path remapping and local Antigravity IDE detection will execute automatically."
        )
        desc.setStyleSheet("color: #71717a; font-size: 10px; line-height: 14px;")
        layout.addWidget(desc)

        # 1. Select Package File
        file_card = QFrame()
        file_card.setProperty("class", "Card")
        fc_layout = QVBoxLayout(file_card)
        fc_layout.setContentsMargins(10, 8, 10, 8)
        fc_layout.setSpacing(4)

        fc_title = QLabel("Select Package File or Folder:")
        fc_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #a1a1aa;")
        fc_layout.addWidget(fc_title)

        fc_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Path to package archive (.zip / .magpkg) or folder...")
        self.file_edit.textChanged.connect(self.on_file_path_changed)
        fc_row.addWidget(self.file_edit, 1)

        btn_browse_folder = QPushButton("Folder...")
        btn_browse_folder.setFixedHeight(26)
        btn_browse_folder.setToolTip("เลือกโฟลเดอร์แพ็กเกจ/โปรเจกต์ที่ต้องการนำเข้า")
        btn_browse_folder.clicked.connect(self.browse_folder)
        fc_row.addWidget(btn_browse_folder)

        btn_browse_file = QPushButton("File (.zip)...")
        btn_browse_file.setFixedHeight(26)
        btn_browse_file.setToolTip("เลือกไฟล์แพ็กเกจ .zip หรือ .magpkg")
        btn_browse_file.clicked.connect(self.browse_package)
        fc_row.addWidget(btn_browse_file)
        fc_layout.addLayout(fc_row)

        layout.addWidget(file_card)

        # 2. Package Inspection Card
        self.info_card = QFrame()
        self.info_card.setProperty("class", "Card")
        ic_layout = QVBoxLayout(self.info_card)
        ic_layout.setContentsMargins(10, 8, 10, 8)
        ic_layout.setSpacing(4)

        ic_title = QLabel("Package Information:")
        ic_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #a1a1aa;")
        ic_layout.addWidget(ic_title)

        self.info_source = QLabel("Source: None selected")
        self.info_source.setStyleSheet("color: #71717a; font-size: 10px;")
        ic_layout.addWidget(self.info_source)

        self.info_created = QLabel("Created: --")
        self.info_created.setStyleSheet("color: #71717a; font-size: 10px;")
        ic_layout.addWidget(self.info_created)

        self.info_slots_scroll = QScrollArea()
        self.info_slots_scroll.setWidgetResizable(True)
        self.info_slots_scroll.setFixedHeight(110)
        self.info_slots_widget = QWidget()
        self.info_slots_layout = QVBoxLayout(self.info_slots_widget)
        self.info_slots_layout.setContentsMargins(2, 2, 2, 2)
        self.info_slots_layout.setSpacing(2)
        self.info_slots_scroll.setWidget(self.info_slots_widget)
        ic_layout.addWidget(self.info_slots_scroll)

        layout.addWidget(self.info_card)

        # 3. Import Mode Card
        mode_card = QFrame()
        mode_card.setProperty("class", "Card")
        mc_layout = QVBoxLayout(mode_card)
        mc_layout.setContentsMargins(10, 8, 10, 8)
        mc_layout.setSpacing(6)

        mc_title = QLabel("Import Mode:")
        mc_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #a1a1aa;")
        mc_layout.addWidget(mc_title)

        self.rb_merge = QRadioButton("Merge & Update (Keep existing slots, import/update slots from package)")
        self.rb_merge.setChecked(True)
        mc_layout.addWidget(self.rb_merge)

        self.rb_replace = QRadioButton("Full Restore (Replace current slots and configurations with package contents)")
        mc_layout.addWidget(self.rb_replace)

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.rb_merge)
        self.btn_group.addButton(self.rb_replace)

        remap_notice = QLabel("Auto-Path Remapping: Active (Remaps old paths in storage.json, state.vscdb, and config.json)")
        remap_notice.setStyleSheet("color: #38bdf8; font-size: 9px; font-weight: 600; padding-top: 2px;")
        mc_layout.addWidget(remap_notice)

        layout.addWidget(mode_card)

        # 4. Progress Bar & Status
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.hide()
        layout.addWidget(self.prog_bar)

        self.status_lbl = QLabel("Select a package file to begin.")
        self.status_lbl.setStyleSheet("color: #71717a; font-size: 10px;")
        layout.addWidget(self.status_lbl)

        # 5. Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)
        btn_box.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_import = QPushButton("Start Import")
        self.btn_import.setProperty("class", "PrimaryBtn")
        self.btn_import.setFixedHeight(28)
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self.start_import)
        btn_box.addWidget(self.btn_import)

        layout.addLayout(btn_box)

    def browse_package(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Select MultiAgIDE Package",
            os.path.join(os.path.expanduser("~"), "Desktop"),
            "Packages (*.zip *.magpkg);;All Files (*.*)"
        )
        if f:
            self.file_edit.setText(f)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select MultiAgIDE Package Folder",
            os.path.join(os.path.expanduser("~"), "Desktop")
        )
        if folder:
            self.file_edit.setText(folder)

    def on_file_path_changed(self, path: str):
        path = path.strip()
        if os.path.exists(path):
            try:
                self.inspected_data = self.pkg_mgr.inspect_package(path)
                self.display_inspection(self.inspected_data)
                self.btn_import.setEnabled(True)
                self.status_lbl.setText("Package validated. Ready to import.")
                self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 10px;")
            except Exception as e:
                self.btn_import.setEnabled(False)
                self.status_lbl.setText(f"Invalid package: {e}")
                self.status_lbl.setStyleSheet("color: #ef4444; font-size: 10px;")
        else:
            self.btn_import.setEnabled(False)

    def display_inspection(self, data: dict):
        manifest = data.get("manifest", {})
        src = manifest.get("source_base_dir", "Unknown")
        created = manifest.get("created_at_iso", "Unknown")[:19].replace("T", " ")
        size_mb = data.get("archive_size_bytes", 0) / (1024 * 1024)

        self.info_source.setText(f"Source Machine: {src}")
        self.info_created.setText(f"Exported At: {created} | Archive Size: {size_mb:.1f} MB")

        # Clear slots widget
        while self.info_slots_layout.count():
            item = self.info_slots_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        slots = manifest.get("slots", [])
        for s in slots:
            sid = s.get("id")
            name = s.get("name", f"Slot {sid}")
            email = s.get("email", "offline")
            projs = s.get("projects", [])
            proj_str = f" - Projects: {', '.join(projs)}" if projs else ""

            lbl = QLabel(f"Slot #{sid}: {name} ({email}){proj_str}")
            lbl.setStyleSheet("color: #d4d4d8; font-size: 10px;")
            self.info_slots_layout.addWidget(lbl)

        self.info_slots_layout.addStretch()

    def start_import(self):
        if self.is_importing or not self.inspected_data:
            return

        pkg_path = self.file_edit.text().strip()
        mode = "merge" if self.rb_merge.isChecked() else "replace"

        reply = QMessageBox.question(
            self,
            "Confirm Import",
            f"Are you sure you want to import this package in '{mode.upper()}' mode?\n\n"
            "This will extract slot profiles, Google auth sessions, and projects, "
            "and automatically remap all paths to this machine.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.is_importing = True
        self.btn_import.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.prog_bar.show()
        self.prog_bar.setValue(0)
        self.status_lbl.setText("Extracting package and remapping paths...")

        self.signals = WorkerSignals()
        self.signals.progress.connect(self.on_import_progress)
        self.signals.finished.connect(self.on_import_finished)
        self.signals.error.connect(self.on_import_error)

        def run_thread():
            try:
                res = self.pkg_mgr.import_package(
                    pkg_path,
                    mode=mode,
                    progress_callback=lambda cur, tot, name: self.signals.progress.emit(cur, tot, name)
                )
                self.signals.finished.emit(res)
            except Exception as e:
                self.signals.error.emit(str(e))

        threading.Thread(target=run_thread, daemon=True).start()

    def on_import_progress(self, current: int, total: int, filename: str):
        pct = int((current / max(1, total)) * 100)
        self.prog_bar.setValue(pct)
        short_name = os.path.basename(filename)
        self.status_lbl.setText(f"Importing ({pct}%): {short_name}")

    def on_import_finished(self, result: dict):
        self.is_importing = False
        self.prog_bar.setValue(100)
        self.btn_import.hide()
        self.btn_cancel.setText("Done")
        self.btn_cancel.setEnabled(True)

        count = result.get("slots_count", 0)
        remapped = result.get("remapped_files", 0)

        self.status_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: 700;")
        self.status_lbl.setText(f"Import Complete! {count} slots restored, {remapped} configuration files remapped.")

        self.import_completed.emit(result)

        QMessageBox.information(
            self,
            "Import Successful",
            f"Successfully imported {count} slots!\n\n"
            f"Auto-remapped {remapped} configuration and state files.\n"
            "All Google accounts, auth sessions, and projects are now active and ready to use."
        )
        self.accept()

    def on_import_error(self, err_msg: str):
        self.is_importing = False
        self.btn_import.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.status_lbl.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 700;")
        self.status_lbl.setText(f"Import Error: {err_msg}")
        QMessageBox.critical(self, "Import Failed", f"An error occurred during import:\n\n{err_msg}")
