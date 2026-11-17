"""Modern PySide6 Graphical Interface for Arch App Cloner."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app_cloner.apps import AppInfo, scan_installed_apps
from app_cloner.badge import create_badged_icon
from app_cloner.manager import CloneConfig, CloneManager
from app_cloner.utils import get_directory_size

DARK_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #0f172a;
    color: #f8fafc;
}

QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #e2e8f0;
}

QLabel {
    color: #e2e8f0;
}

QLineEdit {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
    font-size: 13px;
}

QLineEdit:focus {
    border: 1px solid #38bdf8;
    background-color: #1e293b;
}

QPushButton {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 16px;
    color: #f8fafc;
    font-weight: 500;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}

QPushButton:pressed {
    background-color: #0f172a;
}

QPushButton.primary {
    background-color: #2563eb;
    border: 1px solid #3b82f6;
    color: #ffffff;
    font-weight: 600;
}

QPushButton.primary:hover {
    background-color: #1d4ed8;
    border-color: #60a5fa;
}

QPushButton.danger {
    background-color: #991b1b;
    border: 1px solid #dc2626;
    color: #ffffff;
}

QPushButton.danger:hover {
    background-color: #b91c1c;
}

QPushButton.success {
    background-color: #166534;
    border: 1px solid #22c55e;
    color: #ffffff;
}

QPushButton.success:hover {
    background-color: #15803d;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background: #0f172a;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QCheckBox {
    spacing: 8px;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #475569;
    background-color: #1e293b;
}

QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #3b82f6;
}
"""


class CreateCloneDialog(QDialog):
    """Dialog for customizing and creating an app clone."""

    def __init__(self, app_info: AppInfo, parent=None):
        super().__init__(parent)
        self.app_info = app_info
        self.selected_color = "#3b82f6"
        self.setWindowTitle(f"Clone Application: {app_info.name}")
        self.setMinimumWidth(520)
        self.setStyleSheet(DARK_STYLESHEET)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header preview
        top_row = QHBoxLayout()
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(72, 72)
        top_row.addWidget(self.preview_label)

        app_info_layout = QVBoxLayout()
        title_lbl = QLabel(f"<b>{self.app_info.name}</b>")
        title_lbl.setStyleSheet("font-size: 16px; color: #f8fafc;")
        desc_lbl = QLabel(f"Base command: <code>{self.app_info.clean_exec}</code>")
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        desc_lbl.setWordWrap(True)
        app_info_layout.addWidget(title_lbl)
        app_info_layout.addWidget(desc_lbl)
        top_row.addLayout(app_info_layout)
        top_row.addStretch()
        layout.addLayout(top_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #334155;")
        layout.addWidget(sep)

        # Clone Name Input
        name_box = QVBoxLayout()
        name_lbl = QLabel("Clone Display Name:")
        name_lbl.setStyleSheet("font-weight: 600;")
        self.name_input = QLineEdit()
        self.name_input.setText(f"{self.app_info.name} (Secondary)")
        self.name_input.textChanged.connect(self._update_preview)
        name_box.addWidget(name_lbl)
        name_box.addWidget(self.name_input)
        layout.addLayout(name_box)

        # Badge customization
        badge_box = QVBoxLayout()
        badge_lbl = QLabel("Badge Text (1-3 letters or emoji):")
        badge_lbl.setStyleSheet("font-weight: 600;")
        self.badge_input = QLineEdit()
        self.badge_input.setText("2")
        self.badge_input.setMaxLength(4)
        self.badge_input.textChanged.connect(self._update_preview)
        badge_box.addWidget(badge_lbl)
        badge_box.addWidget(self.badge_input)
        layout.addLayout(badge_box)

        # Badge color presets
        color_box = QVBoxLayout()
        color_lbl = QLabel("Badge Color:")
        color_lbl.setStyleSheet("font-weight: 600;")
        color_box.addWidget(color_lbl)

        color_row = QHBoxLayout()
        presets = [
            ("#3b82f6", "Blue"),
            ("#10b981", "Green"),
            ("#f59e0b", "Amber"),
            ("#ef4444", "Red"),
            ("#8b5cf6", "Purple"),
            ("#ec4899", "Pink"),
            ("#06b6d4", "Cyan"),
        ]
        for hex_code, _ in presets:
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setStyleSheet(f"background-color: {hex_code}; border-radius: 16px; border: 2px solid #1e293b;")
            btn.clicked.connect(lambda _, c=hex_code: self._set_color(c))
            color_row.addWidget(btn)

        custom_btn = QPushButton("Custom...")
        custom_btn.clicked.connect(self._pick_custom_color)
        color_row.addWidget(custom_btn)
        color_row.addStretch()
        color_box.addLayout(color_row)
        layout.addLayout(color_box)

        # Storage & Permissions
        opts_box = QVBoxLayout()
        opts_lbl = QLabel("Storage & Sharing Options:")
        opts_lbl.setStyleSheet("font-weight: 600;")
        opts_box.addWidget(opts_lbl)

        self.cb_downloads = QCheckBox("Share host ~/Downloads folder (allow saving & reading downloads)")
        self.cb_downloads.setChecked(True)
        self.cb_documents = QCheckBox("Share host ~/Documents folder")
        self.cb_offline = QCheckBox("Offline Mode (block network access)")

        opts_box.addWidget(self.cb_downloads)
        opts_box.addWidget(self.cb_documents)
        opts_box.addWidget(self.cb_offline)
        layout.addLayout(opts_box)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        self.create_btn = QPushButton("Create Clone")
        self.create_btn.setProperty("class", "primary")
        self.create_btn.clicked.connect(self.accept)
        btn_box.addWidget(self.create_btn)

        layout.addLayout(btn_box)

        self._update_preview()

    def _set_color(self, hex_code: str):
        self.selected_color = hex_code
        self._update_preview()

    def _pick_custom_color(self):
        dlg = QColorDialog(QColor(self.selected_color), self)
        if dlg.exec():
            self.selected_color = dlg.selectedColor().name()
            self._update_preview()

    def _update_preview(self):
        text = self.badge_input.text().strip()
        if not text:
            # fallback to first letter of clone name
            text = self.name_input.text().strip()[:1].upper() or "2"

        # Render preview offscreen
        tmp_preview = Path("/tmp/app_cloner_dlg_preview.png")
        try:
            create_badged_icon(
                src_icon_path=self.app_info.icon_path,
                dest_path=tmp_preview,
                badge_color=self.selected_color,
                badge_text=text,
                size=128,
                app_name=self.app_info.name,
            )
            pix = QPixmap(str(tmp_preview)).scaled(
                64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(pix)
            tmp_preview.unlink(missing_ok=True)
        except Exception:
            pass


class CloneCardWidget(QFrame):
    """Card representing an active or stopped clone with action buttons."""

    launched = Signal(str)
    stopped = Signal(str)
    reset = Signal(str)
    deleted = Signal(str)
    opened = Signal(str)

    def __init__(self, config: CloneConfig, status: Dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.status = status
        self.setStyleSheet("""
            CloneCardWidget {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 12px;
            }
            CloneCardWidget:hover {
                border: 1px solid #475569;
                background-color: #1f2d42;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(16)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(56, 56)
        if self.config.icon_path and Path(self.config.icon_path).exists():
            pix = QPixmap(self.config.icon_path).scaled(
                56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            icon_lbl.setPixmap(pix)
        layout.addWidget(icon_lbl)

        # Info column
        info_col = QVBoxLayout()
        info_col.setSpacing(4)

        title_row = QHBoxLayout()
        name_lbl = QLabel(f"<b>{self.config.clone_name}</b>")
        name_lbl.setStyleSheet("font-size: 15px; color: #f8fafc;")
        title_row.addWidget(name_lbl)

        # Status Chip
        is_running = self.status.get("is_running", False)
        pid = self.status.get("pid")
        status_lbl = QLabel(f"● Running ({pid})" if is_running else "○ Stopped")
        if is_running:
            status_lbl.setStyleSheet("background-color: #064e3b; color: #34d399; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600;")
        else:
            status_lbl.setStyleSheet("background-color: #334155; color: #94a3b8; padding: 2px 8px; border-radius: 10px; font-size: 11px;")
        title_row.addWidget(status_lbl)
        title_row.addStretch()
        info_col.addLayout(title_row)

        sub_lbl = QLabel(f"Base: {self.config.app_name}  •  Disk: {self.status.get('disk_size', '0 B')}  •  ID: {self.config.id}")
        sub_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        info_col.addWidget(sub_lbl)

        layout.addLayout(info_col, stretch=1)

        # Action Buttons
        btn_col = QHBoxLayout()
        btn_col.setSpacing(8)

        if is_running:
            stop_btn = QPushButton("Stop")
            stop_btn.setProperty("class", "danger")
            stop_btn.clicked.connect(lambda: self.stopped.emit(self.config.id))
            btn_col.addWidget(stop_btn)
        else:
            launch_btn = QPushButton("Launch")
            launch_btn.setProperty("class", "primary")
            launch_btn.clicked.connect(lambda: self.launched.emit(self.config.id))
            btn_col.addWidget(launch_btn)

        open_btn = QPushButton("Folder")
        open_btn.setToolTip("Open data directory")
        open_btn.clicked.connect(lambda: self.opened.emit(self.config.id))
        btn_col.addWidget(open_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.setToolTip("Clear data & cookies")
        reset_btn.clicked.connect(lambda: self.reset.emit(self.config.id))
        btn_col.addWidget(reset_btn)

        del_btn = QPushButton("Delete")
        del_btn.setToolTip("Delete this clone")
        del_btn.clicked.connect(lambda: self.deleted.emit(self.config.id))
        btn_col.addWidget(del_btn)

        layout.addLayout(btn_col)


class MainWindow(QMainWindow):
    """Main window for Arch App Cloner."""

    def __init__(self):
        super().__init__()
        self.mgr = CloneManager()
        self.all_installed_apps: List[AppInfo] = []
        self.setWindowTitle("Arch App Cloner")
        self.resize(880, 640)
        self.setStyleSheet(DARK_STYLESHEET)
        self._init_ui()
        self._refresh_clones()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header Bar
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        app_title = QLabel("<b>Arch App Cloner</b>")
        app_title.setStyleSheet("font-size: 20px; color: #f8fafc;")
        app_sub = QLabel("Run isolated parallel instances with dedicated data and credentials")
        app_sub.setStyleSheet("color: #94a3b8; font-size: 13px;")
        title_box.addWidget(app_title)
        title_box.addWidget(app_sub)
        header.addLayout(title_box)
        header.addStretch()

        # Nav Buttons
        self.btn_my_clones = QPushButton("My Clones")
        self.btn_my_clones.setProperty("class", "primary")
        self.btn_my_clones.clicked.connect(lambda: self._switch_tab(0))
        header.addWidget(self.btn_my_clones)

        self.btn_new_clone = QPushButton("➕ Clone New App")
        self.btn_new_clone.clicked.connect(lambda: self._switch_tab(1))
        header.addWidget(self.btn_new_clone)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.clicked.connect(self._refresh_clones)
        header.addWidget(refresh_btn)

        main_layout.addLayout(header)

        # Stacked pages
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        # Page 0: My Clones
        self.page_clones = QWidget()
        clones_page_layout = QVBoxLayout(self.page_clones)
        clones_page_layout.setContentsMargins(0, 8, 0, 0)

        self.scroll_clones = QScrollArea()
        self.scroll_clones.setWidgetResizable(True)
        self.clones_container = QWidget()
        self.clones_layout = QVBoxLayout(self.clones_container)
        self.clones_layout.setSpacing(10)
        self.clones_layout.setContentsMargins(0, 0, 0, 0)
        self.clones_layout.addStretch()
        self.scroll_clones.setWidget(self.clones_container)
        clones_page_layout.addWidget(self.scroll_clones)

        self.stack.addWidget(self.page_clones)

        # Page 1: Clone New App
        self.page_discover = QWidget()
        discover_layout = QVBoxLayout(self.page_discover)
        discover_layout.setContentsMargins(0, 8, 0, 0)
        discover_layout.setSpacing(12)

        # Search bar
        self.app_search_input = QLineEdit()
        self.app_search_input.setPlaceholderText("Search installed applications to clone (e.g. Brave, Telegram, Discord, VS Code)...")
        self.app_search_input.textChanged.connect(self._filter_installed_apps)
        discover_layout.addWidget(self.app_search_input)

        # App list
        self.scroll_apps = QScrollArea()
        self.scroll_apps.setWidgetResizable(True)
        self.apps_container = QWidget()
        self.apps_layout = QVBoxLayout(self.apps_container)
        self.apps_layout.setSpacing(8)
        self.apps_layout.setContentsMargins(0, 0, 0, 0)
        self.apps_layout.addStretch()
        self.scroll_apps.setWidget(self.apps_container)
        discover_layout.addWidget(self.scroll_apps)

        self.stack.addWidget(self.page_discover)

        # Periodic status refresh
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_clone_statuses_only)
        self.timer.start(4000)

    def _switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.btn_my_clones.setProperty("class", "primary")
            self.btn_new_clone.setProperty("class", "")
            self._refresh_clones()
        else:
            self.btn_my_clones.setProperty("class", "")
            self.btn_new_clone.setProperty("class", "primary")
            if not self.all_installed_apps:
                self._load_installed_apps()
        self.btn_my_clones.style().unpolish(self.btn_my_clones)
        self.btn_my_clones.style().polish(self.btn_my_clones)
        self.btn_new_clone.style().unpolish(self.btn_new_clone)
        self.btn_new_clone.style().polish(self.btn_new_clone)

    def _refresh_clones(self):
        # Clear existing card widgets
        while self.clones_layout.count() > 1:
            item = self.clones_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        clones = self.mgr.list_clones()
        if not clones:
            empty_lbl = QLabel(
                "<center><br><br><b style='font-size: 16px; color: #94a3b8;'>No Clones Created Yet</b><br><br>"
                "<span style='color: #64748b;'>Click <b>Clone New App</b> above to create your first isolated app instance!</span></center>"
            )
            self.clones_layout.insertWidget(0, empty_lbl)
            return

        for cfg, status in clones:
            card = CloneCardWidget(cfg, status, self)
            card.launched.connect(self._on_launch_clone)
            card.stopped.connect(self._on_stop_clone)
            card.reset.connect(self._on_reset_clone)
            card.deleted.connect(self._on_delete_clone)
            card.opened.connect(self._on_open_folder)
            self.clones_layout.insertWidget(self.clones_layout.count() - 1, card)

    def _refresh_clone_statuses_only(self):
        # Only update if on page 0 to avoid visual jumping
        if self.stack.currentIndex() == 0:
            self._refresh_clones()

    def _load_installed_apps(self):
        self.all_installed_apps = scan_installed_apps()
        self._filter_installed_apps(self.app_search_input.text())

    def _filter_installed_apps(self, query: str):
        query = query.strip().lower()

        # Clear existing app rows
        while self.apps_layout.count() > 1:
            item = self.apps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        matches = [
            a for a in self.all_installed_apps
            if not query or query in a.name.lower() or query in a.desktop_id.lower() or query in a.clean_exec.lower()
        ]

        for app in matches[:50]:
            row = QFrame()
            row.setStyleSheet("""
                QFrame {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 8px;
                }
                QFrame:hover {
                    background-color: #273549;
                    border-color: #475569;
                }
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 8, 10, 8)
            row_layout.setSpacing(12)

            icon_lbl = QLabel()
            icon_lbl.setFixedSize(40, 40)
            if app.icon_path and Path(app.icon_path).exists():
                pix = QPixmap(app.icon_path).scaled(
                    40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                icon_lbl.setPixmap(pix)
            row_layout.addWidget(icon_lbl)

            info_box = QVBoxLayout()
            info_box.setSpacing(2)
            title = QLabel(f"<b>{app.name}</b>")
            title.setStyleSheet("font-size: 14px; color: #f8fafc;")
            cmd_lbl = QLabel(f"<code>{app.clean_exec}</code>")
            cmd_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
            info_box.addWidget(title)
            info_box.addWidget(cmd_lbl)
            row_layout.addLayout(info_box, stretch=1)

            clone_btn = QPushButton("Clone")
            clone_btn.setProperty("class", "primary")
            clone_btn.clicked.connect(lambda _, a=app: self._open_clone_dialog(a))
            row_layout.addWidget(clone_btn)

            self.apps_layout.insertWidget(self.apps_layout.count() - 1, row)

    def _open_clone_dialog(self, app_info: AppInfo):
        dlg = CreateCloneDialog(app_info, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            clone_name = dlg.name_input.text().strip() or f"{app_info.name} (Clone)"
            badge_text = dlg.badge_input.text().strip()
            badge_color = dlg.selected_color
            share_dl = dlg.cb_downloads.isChecked()
            share_docs = dlg.cb_documents.isChecked()
            offline = dlg.cb_offline.isChecked()

            try:
                cfg = self.mgr.create_clone(
                    app_info=app_info,
                    clone_name=clone_name,
                    badge_color=badge_color,
                    badge_text=badge_text,
                    share_downloads=share_dl,
                    share_documents=share_docs,
                    offline_mode=offline,
                )
                QMessageBox.information(
                    self,
                    "Clone Created",
                    f"Successfully created '{cfg.clone_name}'!\nA desktop shortcut has been created in your app launcher.",
                )
                self._switch_tab(0)
            except Exception as e:
                QMessageBox.critical(self, "Creation Error", f"Failed to create clone: {e}")

    def _on_launch_clone(self, clone_id: str):
        ok, msg, pid = self.mgr.launch(clone_id, detach=True)
        if not ok:
            QMessageBox.critical(self, "Launch Error", msg)
        self._refresh_clones()

    def _on_stop_clone(self, clone_id: str):
        ok, msg = self.mgr.stop(clone_id)
        if not ok:
            QMessageBox.warning(self, "Stop Warning", msg)
        self._refresh_clones()

    def _on_reset_clone(self, clone_id: str):
        cfg = self.mgr.get_clone(clone_id)
        name = cfg.clone_name if cfg else clone_id
        res = QMessageBox.warning(
            self,
            "Confirm Reset",
            f"Are you sure you want to reset all data and credentials for '{name}'?\nThis will clear its cookies, cache, and logins.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            self.mgr.reset_data(clone_id)
            self._refresh_clones()

    def _on_delete_clone(self, clone_id: str):
        cfg = self.mgr.get_clone(clone_id)
        name = cfg.clone_name if cfg else clone_id
        res = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete '{name}' and remove its launcher?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            self.mgr.delete_clone(clone_id)
            self._refresh_clones()

    def _on_open_folder(self, clone_id: str):
        clone_home = self.mgr._clone_path(clone_id) / "data" / "home"
        subprocess.run(["xdg-open", str(clone_home)], check=False)


def launch_gui() -> int:
    """Entry point to launch the PySide6 App Cloner GUI."""
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    app.setApplicationName("Arch App Cloner")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(launch_gui())
