#!/usr/bin/env python3
"""gwperintahin — Main Window & Application Entry Point"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pyautogui
from PIL import ImageGrab

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QLineEdit,
    QFileDialog, QMessageBox, QFrame, QDialog, QMenu,
    QStatusBar, QInputDialog, QAbstractItemView, QStyle,
)
from PyQt6.QtCore import Qt, QTimer, QMetaObject, Q_ARG, pyqtSignal
from PyQt6.QtGui import (
    QIcon, QColor,
)

from gui_constants import (
    APP_NAME, APP_VERSION, BASE_DIR, MACROS_DIR, TEMPLATES_DIR,
    LOGS_DIR, EXPORTS_DIR, ACTION_TYPES,
    logger, HAS_PYNPUT, HAS_EXECUTOR,
)
from gui_overlays import ColorPickerOverlay, RegionCaptureOverlay, RecordModeOverlay
from gui_dialogs import StepDialog, RecordReviewDialog, ScheduleDialog

# pynput imports for record mode (conditionally imported)
if HAS_PYNPUT:
    from pynput import mouse as pynput_mouse
    from pynput import keyboard as pynput_keyboard


# ═════════════════════════════════════════════════════════════════════════
#  Main Window
# ═════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    # Signal for thread-safe recording stop
    _recording_stop_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} \u2014 Windows Macro Agent Toolkit")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        # ── State ──
        self._showing_window = False
        self._current_macro = {
            "name": "Untitled Macro",
            "description": "",
            "version": "1.0",
            "created": time.strftime("%Y-%m-%d"),
            "steps": [],
        }
        self._current_macro_path = None
        self._modified = False
        self._step_widgets = []

        # ── Record mode state ──
        self._recording = False
        self._record_steps = []
        self._record_overlay = None
        self._record_mouse_listener = None
        self._record_keyboard_listener = None
        self._record_key_buffer = ""
        self._record_last_key_time = 0
        self._record_stop_hotkey = None

        # Thread-safe recording stop: background threads emit signal -> main thread handles it
        self._recording_stop_requested.connect(
            self._stop_recording, Qt.ConnectionType.QueuedConnection
        )

        # ── Build UI ──
        self._build_ui()
        self._setup_style()
        self._refresh_library()
        self._update_title()

        # Coord inspector timer
        self._coord_timer = QTimer(self)
        self._coord_timer.timeout.connect(self._update_coord_inspector)
        self._coord_timer.start(100)

    # ═════════════════════════════════════════════════════════════════════
    #  UI Construction
    # ═════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ── Left sidebar: Macro Library ──
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(8)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)

        lib_title = QLabel("\U0001f4da Macro Library")
        lib_title.setObjectName("sectionTitle")
        sidebar_layout.addWidget(lib_title)

        self._library_list = QListWidget()
        self._library_list.setObjectName("libraryList")
        self._library_list.itemClicked.connect(self._on_library_select)
        self._library_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._library_list.customContextMenuRequested.connect(self._library_context_menu)
        sidebar_layout.addWidget(self._library_list, 1)

        lib_btn_layout = QHBoxLayout()
        new_btn = QPushButton("\u2795 New")
        new_btn.clicked.connect(self._new_macro)
        import_btn = QPushButton("\U0001f4c2 Import")
        import_btn.clicked.connect(self._import_macro)
        lib_btn_layout.addWidget(new_btn)
        lib_btn_layout.addWidget(import_btn)
        sidebar_layout.addLayout(lib_btn_layout)

        # ── Center: Macro Editor ──
        editor = QFrame()
        editor.setObjectName("editorArea")
        editor_layout = QVBoxLayout(editor)
        editor_layout.setSpacing(8)
        editor_layout.setContentsMargins(16, 12, 16, 12)

        # Toolbar area
        toolbar = QHBoxLayout()

        det_btn = QPushButton("\U0001f3af Color Picker")
        det_btn.setToolTip("Pick a colour from any pixel on screen")
        det_btn.clicked.connect(self._detect_color)

        cap_btn = QPushButton("\U0001f4f7 Capture Region")
        cap_btn.setToolTip("Capture a screen region as template image")
        cap_btn.clicked.connect(self._capture_region)

        coord_btn = QPushButton("\U0001f4cd Coord Inspector")
        coord_btn.setToolTip("Show real-time mouse coordinates")
        coord_btn.setCheckable(True)
        coord_btn.toggled.connect(self._toggle_coord_inspector)
        self._coord_btn = coord_btn

        toolbar.addWidget(det_btn)
        toolbar.addWidget(cap_btn)
        toolbar.addWidget(coord_btn)

        # Separator
        sep = QLabel("|")
        sep.setStyleSheet("color: #3a3b3e; font-size: 18px; padding: 0 4px;")
        toolbar.addWidget(sep)

        # Record button
        self._record_btn = QPushButton("\U0001f534 Record")
        self._record_btn.setCheckable(True)
        self._record_btn.setToolTip("Start recording mouse clicks & keyboard actions")
        self._record_btn.setStyleSheet("""
            QPushButton {
                background: #4a1a1a;
                border-color: #8c3030;
                color: #ff6666;
                font-weight: 700;
                padding: 7px 18px;
            }
            QPushButton:hover {
                background: #5a2222;
                border-color: #cc4040;
            }
            QPushButton:checked {
                background: #cc3333;
                border-color: #ff4444;
                color: #fff;
            }
        """)
        self._record_btn.toggled.connect(self._on_record_toggle)
        toolbar.addWidget(self._record_btn)

        toolbar.addStretch()

        # Test Run / Save / Export / Schedule
        test_btn = QPushButton("\u25b6 Test Run")
        test_btn.setObjectName("testBtn")
        test_btn.clicked.connect(self._test_run)

        save_btn = QPushButton("\U0001f4be Save")
        save_btn.setObjectName("saveBtn")
        save_btn.clicked.connect(self._save_macro)

        export_btn = QPushButton("\U0001f4e4 Export BAT")
        export_btn.setObjectName("exportBtn")
        export_btn.clicked.connect(self._export_bat)

        toolbar.addWidget(test_btn)
        toolbar.addWidget(save_btn)
        toolbar.addWidget(export_btn)

        # Separator
        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #3a3b3e; font-size: 18px; padding: 0 4px;")
        toolbar.addWidget(sep2)

        sched_btn = QPushButton("\u23f0 Schedule")
        sched_btn.setToolTip("Schedule macro via Windows Task Scheduler")
        sched_btn.setStyleSheet("""
            QPushButton {
                background: #3a2a1a;
                border-color: #5a4030;
                color: #ffcc88;
                font-weight: 600;
                padding: 7px 16px;
            }
            QPushButton:hover {
                background: #5a3a2a;
                border-color: #8a6040;
            }
        """)
        sched_btn.clicked.connect(self._open_schedule)
        toolbar.addWidget(sched_btn)

        editor_layout.addLayout(toolbar)

        # Macro name & description
        name_layout = QHBoxLayout()
        name_label = QLabel("Macro Name:")
        name_label.setFixedWidth(100)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Enter macro name\u2026")
        self._name_edit.textChanged.connect(self._on_modified)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self._name_edit, 1)
        editor_layout.addLayout(name_layout)

        desc_layout = QHBoxLayout()
        desc_label = QLabel("Description:")
        desc_label.setFixedWidth(100)
        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("Brief description\u2026")
        self._desc_edit.textChanged.connect(self._on_modified)
        desc_layout.addWidget(desc_label)
        desc_layout.addWidget(self._desc_edit, 1)
        editor_layout.addLayout(desc_layout)

        # Steps header
        steps_header = QHBoxLayout()
        steps_title = QLabel("Steps:")
        steps_title.setObjectName("sectionTitle")
        add_step_btn = QPushButton("\u2795 Add Step")
        add_step_btn.clicked.connect(self._add_step)
        self._move_up_btn = QPushButton("\u2191")
        self._move_up_btn.setToolTip("Move selected step up")
        self._move_up_btn.setFixedWidth(32)
        self._move_up_btn.clicked.connect(self._move_step_up)
        self._move_down_btn = QPushButton("\u2193")
        self._move_down_btn.setToolTip("Move selected step down")
        self._move_down_btn.setFixedWidth(32)
        self._move_down_btn.clicked.connect(self._move_step_down)
        del_btn = QPushButton("\U0001f5d1\ufe0f Delete")
        del_btn.clicked.connect(self._delete_step)

        steps_header.addWidget(steps_title)
        steps_header.addStretch()
        steps_header.addWidget(add_step_btn)
        steps_header.addWidget(self._move_up_btn)
        steps_header.addWidget(self._move_down_btn)
        steps_header.addWidget(del_btn)
        editor_layout.addLayout(steps_header)

        # Steps list
        self._steps_list = QListWidget()
        self._steps_list.setObjectName("stepsList")
        self._steps_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._steps_list.model().rowsMoved.connect(self._on_steps_reordered)
        self._steps_list.itemClicked.connect(self._on_step_clicked)
        self._steps_list.itemDoubleClicked.connect(self._edit_step)
        editor_layout.addWidget(self._steps_list, 1)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(editor, 1)

        # ── Coord inspector panel ──
        self._coord_panel = QFrame()
        self._coord_panel.setObjectName("coordPanel")
        self._coord_panel.setFixedWidth(220)
        cp_layout = QVBoxLayout(self._coord_panel)
        cp_layout.setContentsMargins(12, 12, 12, 12)
        cp_layout.setSpacing(8)

        cp_title = QLabel("\U0001f4cd Koordinat Inspector")
        cp_title.setObjectName("sectionTitle")
        cp_layout.addWidget(cp_title)

        self._coord_display = QLabel("X: 0\nY: 0")
        self._coord_display.setObjectName("coordDisplay")
        self._coord_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cp_layout.addWidget(self._coord_display)

        self._coord_hex = QLabel("Hex: #000000")
        self._coord_hex.setObjectName("coordDisplay")
        self._coord_hex.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cp_layout.addWidget(self._coord_hex)

        cp_layout.addStretch()

        main_layout.addWidget(self._coord_panel)
        self._coord_panel.hide()

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    # ═════════════════════════════════════════════════════════════════════
    #  Styling
    # ═════════════════════════════════════════════════════════════════════

    def _setup_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background: #1a1b1e;
            }
            QWidget {
                font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
                font-size: 13px;
                color: #e0e0e0;
            }
            QFrame#sidebar {
                background: #141517;
                border-right: 1px solid #2a2b2e;
            }
            QFrame#editorArea {
                background: #1a1b1e;
            }
            QFrame#coordPanel {
                background: #141517;
                border-left: 1px solid #2a2b2e;
            }
            QLabel#sectionTitle {
                font-size: 13px;
                font-weight: 600;
                color: #9a9b9e;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding-bottom: 4px;
            }
            QLabel#coordDisplay {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 18px;
                color: #e0e0e0;
                background: #222326;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 16px;
            }
            QListWidget {
                background: #1e1f22;
                border: 1px solid #2a2b2e;
                border-radius: 8px;
                padding: 4px;
                font-size: 13px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 4px;
                margin: 2px 0;
                color: #d0d0d0;
                border: none;
            }
            QListWidget::item:selected {
                background: #2b2d30;
                color: #ffffff;
                border: none;
            }
            QListWidget::item:hover {
                background: #252629;
                color: #e8e8e8;
            }
            QListWidget::item:selected:hover {
                background: #303235;
                color: #ffffff;
            }
            QListWidget#stepsList {
                background: #1e1f22;
                selection-background-color: #2b2d30;
                selection-color: #ffffff;
            }
            QListWidget#stepsList::item {
                padding: 8px 10px;
                border-radius: 4px;
                margin: 2px 0;
                color: #d0d0d0;
            }
            QListWidget#stepsList::item:selected {
                background: #2d2f33;
                color: #ffffff;
                border: none;
            }
            QListWidget#stepsList::item:hover {
                background: #252629;
                color: #e8e8e8;
            }
            QListWidget#stepsList::item:selected:hover {
                background: #34363a;
                color: #ffffff;
            }
            QListWidget#libraryList {
                selection-background-color: #2d2f33;
                selection-color: #ffffff;
            }
            QListWidget#libraryList::item {
                padding: 10px 12px;
            }
            QListWidget#libraryList::item:selected {
                background: #2d2f33;
                color: #ffffff;
            }
            QListWidget#libraryList::item:hover {
                background: #252629;
                color: #e8e8e8;
            }
            QListWidget#libraryList::item:selected:hover {
                background: #34363a;
                color: #ffffff;
            }
            QPushButton {
                background: #2b2d30;
                color: #e0e0e0;
                border: 1px solid #3a3b3e;
                border-radius: 6px;
                padding: 7px 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #36383b;
                border-color: #4a4b4e;
            }
            QPushButton:pressed {
                background: #1e1f22;
            }
            QPushButton#testBtn {
                background: #1a6b3c;
                border-color: #218c4a;
                color: #fff;
                font-weight: 600;
            }
            QPushButton#testBtn:hover {
                background: #218c4a;
            }
            QPushButton#saveBtn {
                background: #1a4b8c;
                border-color: #2563a8;
                color: #fff;
                font-weight: 600;
            }
            QPushButton#saveBtn:hover {
                background: #2563a8;
            }
            QPushButton#exportBtn {
                background: #6b3a1a;
                border-color: #8c4a21;
                color: #fff;
                font-weight: 600;
            }
            QPushButton#exportBtn:hover {
                background: #8c4a21;
            }
            QLineEdit, QTextEdit {
                background: #1e1f22;
                border: 1px solid #2a2b2e;
                border-radius: 6px;
                padding: 6px 10px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #4a8cff;
            }
            QComboBox {
                background: #1e1f22;
                border: 1px solid #2a2b2e;
                border-radius: 6px;
                padding: 6px 10px;
                color: #e0e0e0;
                min-height: 20px;
            }
            QComboBox:focus {
                border-color: #4a8cff;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background: #1e1f22;
                border: 1px solid #333;
                selection-background-color: #2b2d30;
                color: #e0e0e0;
            }
            QSpinBox, QDoubleSpinBox {
                background: #1e1f22;
                border: 1px solid #2a2b2e;
                border-radius: 6px;
                padding: 4px 8px;
                color: #e0e0e0;
                min-height: 20px;
            }
            QScrollBar:vertical {
                background: #1a1b1e;
                width: 8px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #3a3b3e;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4a4b4e;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QGroupBox {
                font-weight: 600;
                border: 1px solid #2a2b2e;
                border-radius: 8px;
                margin-top: 12px;
                padding: 16px 12px 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #9a9b9e;
            }
            QDialog {
                background: #1a1b1e;
            }
            QStatusBar {
                background: #141517;
                color: #7a7b7e;
                border-top: 1px solid #2a2b2e;
                font-size: 12px;
            }
        """)

    # ═════════════════════════════════════════════════════════════════════
    #  Title
    # ═════════════════════════════════════════════════════════════════════

    def _update_title(self):
        name = self._current_macro.get("name", "Untitled")
        modified = " \u25cf" if self._modified else ""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} \u2014 {name}{modified}")

    # ═════════════════════════════════════════════════════════════════════
    #  Macro Library
    # ═════════════════════════════════════════════════════════════════════

    def _refresh_library(self):
        self._library_list.clear()
        macro_files = sorted(MACROS_DIR.glob("*.json"))
        for f in macro_files:
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                name = data.get("name", f.stem)
                steps = len(data.get("steps", []))
                item = QListWidgetItem(f"{name}  ({steps} steps)")
                item.setData(Qt.ItemDataRole.UserRole, str(f))
                self._library_list.addItem(item)
            except Exception:
                item = QListWidgetItem(f.stem + " (invalid)")
                item.setData(Qt.ItemDataRole.UserRole, str(f))
                item.setForeground(QColor("#ff6b6b"))
                self._library_list.addItem(item)

    def _on_library_select(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and Path(path).exists():
            self._load_macro(path)

    def _library_context_menu(self, pos):
        item = self._library_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.addAction("\U0001f5d1\ufe0f Delete", lambda: self._delete_macro(item))
        menu.addAction("\U0001f4c1 Show in Explorer", lambda: self._show_in_explorer(
            item.data(Qt.ItemDataRole.UserRole)))
        menu.exec(self._library_list.mapToGlobal(pos))

    def _delete_macro(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and Path(path).exists():
            reply = QMessageBox.question(self, "Delete Macro",
                f"Delete '{Path(path).stem}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                Path(path).unlink()
                self._refresh_library()
                self._status.showMessage("Deleted macro", 3000)

    def _show_in_explorer(self, path):
        resolved = str(Path(path).resolve())
        try:
            subprocess.Popen(['explorer', '/select,', resolved])
        except Exception:
            subprocess.Popen(['explorer', str(Path(path).parent.resolve())])

    # ═════════════════════════════════════════════════════════════════════
    #  New / Import / Load / Save
    # ═════════════════════════════════════════════════════════════════════

    def _new_macro(self):
        if self._modified:
            reply = QMessageBox.question(self, "Unsaved Changes",
                "Save current macro before creating a new one?",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Yes:
                self._save_macro()

        self._current_macro = {
            "name": "Untitled Macro",
            "description": "",
            "version": "1.0",
            "created": time.strftime("%Y-%m-%d"),
            "steps": [],
        }
        self._current_macro_path = None
        self._modified = False
        self._update_editor()
        self._update_title()
        self._status.showMessage("New macro created", 3000)

    def _import_macro(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Macro", "", "JSON Files (*.json)")
        if path:
            dest = MACROS_DIR / Path(path).name
            shutil.copy2(path, dest)
            self._refresh_library()
            self._load_macro(dest)
            self._status.showMessage(f"Imported: {Path(path).name}", 3000)

    def _load_macro(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._current_macro = data
            self._current_macro_path = Path(path)
            self._modified = False
            self._update_editor()
            self._update_title()
            self._status.showMessage(f"Loaded: {Path(path).name}", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load macro:\n{e}")

    def _save_macro(self):
        self._sync_editor_to_data()
        data = self._current_macro

        if self._current_macro_path:
            path = self._current_macro_path
        else:
            name = data.get("name", "untitled").replace(" ", "_").lower()
            path = MACROS_DIR / f"{name}.json"
            if path.exists():
                path = MACROS_DIR / f"{name}_{int(time.time())}.json"

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._current_macro_path = path
            self._modified = False
            self._update_title()
            self._refresh_library()
            self._status.showMessage(f"Saved: {path.name}", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save macro:\n{e}")

    # ═════════════════════════════════════════════════════════════════════
    #  Editor sync
    # ═════════════════════════════════════════════════════════════════════

    def _sync_editor_to_data(self):
        self._current_macro["name"] = self._name_edit.text().strip() or "Untitled"
        self._current_macro["description"] = self._desc_edit.text().strip()

    def _update_editor(self):
        self._name_edit.setText(self._current_macro.get("name", ""))
        self._desc_edit.setText(self._current_macro.get("description", ""))
        self._refresh_steps_list()

    def _on_modified(self):
        self._modified = True
        self._update_title()

    # ═════════════════════════════════════════════════════════════════════
    #  Steps list
    # ═════════════════════════════════════════════════════════════════════

    def _refresh_steps_list(self):
        self._steps_list.clear()
        self._step_widgets.clear()
        steps = self._current_macro.get("steps", [])
        for i, step in enumerate(steps):
            action = step.get("action", "unknown")
            icon = "\u2699\ufe0f"
            label = action
            for aid, alabel, aicon in ACTION_TYPES:
                if aid == action:
                    icon = aicon
                    label = alabel
                    break
            summary = self._step_summary(step)
            display = f"{i+1}. {icon} {label}  \u2014  {summary}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._steps_list.addItem(item)

    def _step_summary(self, step):
        action = step.get("action", "")
        if action in ("click_coord", "right_click_coord"):
            return f"({step.get('x', '?')}, {step.get('y', '?')})"
        elif action in ("click_image", "wait_for_image"):
            return f"{Path(step.get('target', '?')).name}"
        elif action in ("click_color", "wait_for_color"):
            return f"{step.get('color', '?')}"
        elif action == "type_text":
            text = step.get("text", "")
            return f'"{text[:30]}{"\u2026" if len(text) > 30 else ""}"'
        elif action == "press_key":
            return f"{step.get('key', '?')}"
        elif action == "wait_seconds":
            return f"{step.get('duration', 1)}s"
        elif action == "wait_for_window":
            return f'"{step.get("title", "?")}"'
        elif action == "focus_window":
            return f'"{step.get("title", "?")}"'
        elif action == "scroll":
            return f"{step.get('direction', 'down')} \u00d7{step.get('amount', 3)}"
        elif action == "screenshot":
            return Path(step.get("save_path", "auto")).name
        elif action == "loop":
            return f"{step.get('count', 1)}\u00d7"
        elif action == "if_else":
            cond = step.get("condition", {}).get("type", "?")
            return f"({cond})"
        elif action == "set_variable":
            return f"{step.get('name', '?')} = {step.get('value', 0)}"
        return ""

    def _add_step(self):
        dlg = StepDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            step_data = dlg.get_step_data()
            steps = self._current_macro.get("steps", [])
            step_data["id"] = len(steps) + 1
            steps.append(step_data)
            self._current_macro["steps"] = steps
            self._modified = True
            self._refresh_steps_list()
            self._update_title()
            self._status.showMessage(f"Added step: {step_data.get('action')}", 3000)

    def _edit_step(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None:
            return
        steps = self._current_macro.get("steps", [])
        if idx >= len(steps):
            return
        dlg = StepDialog(self, steps[idx])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            steps[idx] = dlg.get_step_data()
            steps[idx]["id"] = idx + 1
            self._current_macro["steps"] = steps
            self._modified = True
            self._refresh_steps_list()
            self._update_title()
            self._status.showMessage(f"Edited step {idx+1}", 3000)

    def _on_step_clicked(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is not None:
            self._steps_list.setCurrentRow(idx)

    def _delete_step(self):
        current = self._steps_list.currentItem()
        if not current:
            return
        idx = current.data(Qt.ItemDataRole.UserRole)
        if idx is None:
            return
        steps = self._current_macro.get("steps", [])
        if 0 <= idx < len(steps):
            steps.pop(idx)
            for i, s in enumerate(steps):
                s["id"] = i + 1
            self._current_macro["steps"] = steps
            self._modified = True
            self._refresh_steps_list()
            self._update_title()
            self._status.showMessage(f"Deleted step {idx+1}", 3000)

    def _move_step_up(self):
        current = self._steps_list.currentItem()
        if not current:
            return
        idx = current.data(Qt.ItemDataRole.UserRole)
        if idx and idx > 0:
            steps = self._current_macro["steps"]
            steps[idx], steps[idx-1] = steps[idx-1], steps[idx]
            for i, s in enumerate(steps):
                s["id"] = i + 1
            self._current_macro["steps"] = steps
            self._modified = True
            self._refresh_steps_list()
            self._steps_list.setCurrentRow(idx - 1)
            self._update_title()

    def _move_step_down(self):
        current = self._steps_list.currentItem()
        if not current:
            return
        idx = current.data(Qt.ItemDataRole.UserRole)
        steps = self._current_macro["steps"]
        if idx is not None and idx < len(steps) - 1:
            steps[idx], steps[idx+1] = steps[idx+1], steps[idx]
            for i, s in enumerate(steps):
                s["id"] = i + 1
            self._current_macro["steps"] = steps
            self._modified = True
            self._refresh_steps_list()
            self._steps_list.setCurrentRow(idx + 1)
            self._update_title()

    def _on_steps_reordered(self):
        """Sync the data array to match the new visual order after drag-drop."""
        new_steps = []
        for i in range(self._steps_list.count()):
            item = self._steps_list.item(i)
            old_idx = item.data(Qt.ItemDataRole.UserRole)
            if old_idx is not None and old_idx < len(self._current_macro.get("steps", [])):
                new_steps.append(self._current_macro["steps"][old_idx])

        if new_steps:
            for i, s in enumerate(new_steps):
                s["id"] = i + 1
            self._current_macro["steps"] = new_steps

        self._modified = True
        self._refresh_steps_list()
        self._update_title()

    # ═════════════════════════════════════════════════════════════════════
    #  Detection Tools
    # ═════════════════════════════════════════════════════════════════════

    def _show_window(self):
        """Show window and force a full repaint to prevent blank/white screen bug.

        Uses a reentrancy guard to prevent crashes when called from signal
        handlers during overlay destruction (e.g. ``destroyed`` signal while
        ``color_selected`` handler is still running with ``processEvents()``).
        """
        if self._showing_window:
            return
        self._showing_window = True
        try:
            self.show()
            self.raise_()
            self.activateWindow()
            QApplication.processEvents()

            # Force stylesheet re-application on ALL widgets recursively
            # (unpolish/polish on self alone isn't enough — child widgets also lose
            #  their dark theme after window is hidden and re-shown on Windows)
            style = self.style()
            for widget in [self] + self.findChildren(QWidget):
                try:
                    style.unpolish(widget)
                    style.polish(widget)
                    widget.update()
                except RuntimeError:
                    # Widget may have been deleted during reentrant event processing
                    pass

            self.repaint()
            QApplication.processEvents()
        finally:
            self._showing_window = False

    def _detect_color(self):
        self.hide()
        QTimer.singleShot(300, self._do_color_pick)

    def _do_color_pick(self):
        picker = ColorPickerOverlay()
        picker.color_selected.connect(lambda c: (
            self._status.showMessage(f"Picked colour: {c}", 5000),
        ))
        picker.destroyed.connect(lambda obj=None: QTimer.singleShot(0, self._show_window))
        picker.show()

    def _capture_region(self):
        self.hide()
        QTimer.singleShot(300, self._do_region_capture)

    def _do_region_capture(self):
        overlay = RegionCaptureOverlay()
        overlay.region_captured.connect(self._save_captured_region)
        overlay.destroyed.connect(lambda obj=None: QTimer.singleShot(0, self._show_window))
        overlay.show()

    def _save_captured_region(self, region):
        x, y, w, h = region
        try:
            screenshot = ImageGrab.grab(bbox=(x, y, x+w, y+h))
            name, ok = QInputDialog.getText(self, "Save Template",
                "Template name (without .png):",
                text=f"template_{int(time.time())}")
            if ok and name:
                path = TEMPLATES_DIR / f"{name}.png"
                screenshot.save(str(path))
                self._status.showMessage(f"Template saved: {path.name}", 5000)
                reply = QMessageBox.question(self, "Use Template",
                    f"Template saved as '{path.name}'.\n\n"
                    "Add a 'Wait for Image' or 'Click Image' step with this template?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    step = {
                        "id": len(self._current_macro.get("steps", [])) + 1,
                        "action": "click_image",
                        "target": f"templates/{name}.png",
                        "confidence": 0.85,
                    }
                    self._current_macro.setdefault("steps", []).append(step)
                    self._modified = True
                    self._refresh_steps_list()
                    self._update_title()
                    self._status.showMessage("Step added with captured template!", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not capture region:\n{e}")

    def _toggle_coord_inspector(self, checked):
        self._coord_panel.setVisible(checked)
        if checked:
            self._status.showMessage("Coord Inspector active \u2014 move mouse to see coordinates", 3000)

    def _update_coord_inspector(self):
        if not self._coord_panel.isVisible():
            return
        pos = pyautogui.position()
        self._coord_display.setText(f"X: {pos.x}\nY: {pos.y}")
        try:
            pixel = pyautogui.pixel(pos.x, pos.y)
            hex_color = "#{:02X}{:02X}{:02X}".format(*pixel)
            self._coord_hex.setText(f"Hex: {hex_color}")
            self._coord_hex.setStyleSheet(
                f"font-family: 'Consolas', monospace; font-size: 18px; "
                f"color: #e0e0e0; background: #222326; "
                f"border: 1px solid {hex_color}; "
                f"border-radius: 8px; padding: 16px;"
            )
        except Exception:
            self._coord_hex.setText("Hex: ---")

    # ═════════════════════════════════════════════════════════════════════
    #  Test Run
    # ═════════════════════════════════════════════════════════════════════

    def _test_run(self):
        self._sync_editor_to_data()
        data = self._current_macro

        if not data.get("steps"):
            QMessageBox.information(self, "Test Run",
                "No steps to execute. Add some steps first.")
            return

        if not HAS_EXECUTOR:
            QMessageBox.warning(self, "Cannot Test Run",
                "Macro executor module not available.\n\n"
                "Make sure 'executor.py' is in the same folder\n"
                "or rebuild the application.")
            return

        temp_path = MACROS_DIR / f"_test_run_{int(time.time())}.json"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            log_path = LOGS_DIR / f"test_run_{int(time.time())}.log"

            self._status.showMessage("\u25b6 Running macro test\u2026 (move mouse to top-left to abort)")

            try:
                from executor import MacroExecutor
                executor = MacroExecutor(str(temp_path), str(log_path))
                executor.run()
                self._status.showMessage("\u2705 Test run completed", 5000)

                msg = "Macro test run completed successfully!"
                if log_path.exists():
                    msg += f"\n\nLog saved to:\n{log_path}"
                QMessageBox.information(self, "Test Run Result", msg)

            except Exception as e:
                self._status.showMessage(f"\u274c Test run failed: {e}", 5000)
                QMessageBox.warning(self, "Test Run Error",
                    f"Error during execution:\n\n{e}\n\nCheck logs for details.")

            if temp_path.exists():
                temp_path.unlink()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not run test:\n{e}")

    # ═════════════════════════════════════════════════════════════════════
    #  Export .bat
    # ═════════════════════════════════════════════════════════════════════

    def _export_bat(self):
        self._sync_editor_to_data()
        data = self._current_macro

        if not data.get("steps"):
            QMessageBox.information(self, "Export",
                "No steps to export. Add some steps first.")
            return

        macro_name = data.get("name", "untitled").replace(" ", "_").lower()
        macro_filename = f"{macro_name}_{int(time.time())}.json"
        macro_path = MACROS_DIR / macro_filename

        try:
            with open(macro_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            bat_name = f"{macro_name}.bat"
            bat_path = EXPORTS_DIR / bat_name

            bat_content = f"""@echo off
:: ============================================================
:: Macro: {data.get('name', 'Untitled')}
:: Description: {data.get('description', '')}
:: Generated by: gwperintahin v{APP_VERSION}
:: Date: {time.strftime('%Y-%m-%d %H:%M')}
:: ============================================================

cd /d "%~dp0"

:: Run the macro
executor.exe --macro "macros\\{macro_filename}" --log "logs\\{macro_name}.log"

:: Uncomment the line below to keep the window open after execution
:: pause
"""

            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)

            self._status.showMessage(f"\u2705 Exported: {bat_name}", 5000)

            reply = QMessageBox.question(self, "Export Complete",
                f"Macro exported successfully!\n\n"
                f"\U0001f4c4 {bat_name}\n"
                f"\U0001f4cb {macro_filename}\n\n"
                f"To run: double-click the .bat file.\n\n"
                f"Open exports folder?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                os.startfile(str(EXPORTS_DIR.resolve()))

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not export:\n{e}")

    # ═════════════════════════════════════════════════════════════════════
    #  Schedule
    # ═════════════════════════════════════════════════════════════════════

    def _open_schedule(self):
        dlg = ScheduleDialog(self)
        dlg.exec()

    # ═════════════════════════════════════════════════════════════════════
    #  Record Mode
    # ═════════════════════════════════════════════════════════════════════

    def _on_record_toggle(self, checked):
        if checked:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        if not HAS_PYNPUT:
            QMessageBox.warning(self, "Cannot Record",
                "Recording mode requires the 'pynput' library.\n\n"
                "Install it with: pip install pynput")
            self._record_btn.setChecked(False)
            return

        self._recording = True
        self._record_steps = []
        self._record_key_buffer = ""
        self._record_last_key_time = 0

        self.hide()
        self._record_overlay = RecordModeOverlay()
        self._record_overlay.stop_requested.connect(self._stop_recording)
        self._record_overlay.show()

        self._status.showMessage("\U0001f534 Recording\u2026 Press F6 to stop", 0)

        self._record_mouse_listener = pynput_mouse.Listener(
            on_click=self._on_record_mouse_click
        )
        self._record_mouse_listener.start()

        self._record_keyboard_listener = pynput_keyboard.Listener(
            on_press=self._on_record_key_press
        )
        self._record_keyboard_listener.start()

        try:
            self._record_stop_hotkey = pynput_keyboard.GlobalHotKeys({
                '<f6>': lambda: self._recording_stop_requested.emit(),
                '<ctrl>+<f6>': lambda: self._recording_stop_requested.emit(),
            })
            self._record_stop_hotkey.start()
        except Exception:
            pass

        logger.info("Recording started")

    def _on_record_mouse_click(self, x, y, button, pressed):
        if not self._recording:
            return
        if not pressed:
            return

        self._flush_record_key_buffer()

        btn_name = "left"
        if button == pynput_mouse.Button.right:
            btn_name = "right"
        elif button == pynput_mouse.Button.middle:
            btn_name = "middle"

        step = {
            "action": "click_coord",
            "x": x,
            "y": y,
            "button": btn_name,
        }
        self._record_steps.append(step)

        QMetaObject.invokeMethod(
            self._record_overlay,
            "update_step_count",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(int, len(self._record_steps))
        )

    def _on_record_key_press(self, key):
        if not self._recording:
            return

        try:
            if hasattr(key, 'name') and key.name and key.name.lower() in ('f6',):
                self._recording_stop_requested.emit()
                return
        except Exception:
            pass
        try:
            if hasattr(key, 'char') and key.char == chr(6):
                return
        except Exception:
            pass
        try:
            if hasattr(key, 'vk') and key.vk == 117:
                self._recording_stop_requested.emit()
                return
        except Exception:
            pass

        now = time.time()

        try:
            if hasattr(key, 'char') and key.char is not None:
                if (now - self._record_last_key_time) > 0.5 and self._record_key_buffer:
                    self._flush_record_key_buffer()
                self._record_key_buffer += key.char
                self._record_last_key_time = now
                return
        except Exception:
            pass

        self._flush_record_key_buffer()

        key_name = self._map_special_key(key)
        if key_name:
            step = {"action": "press_key", "key": key_name}
            self._record_steps.append(step)

            QMetaObject.invokeMethod(
                self._record_overlay,
                "update_step_count",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(int, len(self._record_steps))
            )

    @staticmethod
    def _map_special_key(key):
        try:
            if hasattr(key, 'name'):
                name = key.name.lower()
                mapping = {
                    'enter': 'enter', 'tab': 'tab', 'space': 'space',
                    'backspace': 'backspace', 'delete': 'delete',
                    'escape': 'escape', 'up': 'up', 'down': 'down',
                    'left': 'left', 'right': 'right', 'home': 'home',
                    'end': 'end', 'page_up': 'pageup', 'page_down': 'pagedown',
                    'caps_lock': 'capslock',
                    'shift': None, 'shift_r': None,
                    'ctrl': None, 'ctrl_l': None, 'ctrl_r': None,
                    'alt': None, 'alt_l': None, 'alt_r': None, 'alt_gr': None,
                    'cmd': None, 'cmd_l': None, 'cmd_r': None,
                    'f1': 'f1', 'f2': 'f2', 'f3': 'f3', 'f4': 'f4',
                    'f5': 'f5', 'f7': 'f7', 'f8': 'f8', 'f9': 'f9',
                    'f10': 'f10', 'f11': 'f11', 'f12': 'f12',
                    'print_screen': 'printscreen', 'scroll_lock': 'scrolllock',
                    'pause': 'pause', 'insert': 'insert', 'menu': 'menu',
                    'num_lock': 'numlock',
                }
                return mapping.get(name)
        except Exception:
            pass
        return None

    def _flush_record_key_buffer(self):
        if self._record_key_buffer:
            step = {
                "action": "type_text",
                "text": self._record_key_buffer,
                "delay_between_keys": 0.02,
            }
            self._record_steps.append(step)
            self._record_key_buffer = ""

            if self._record_overlay:
                QMetaObject.invokeMethod(
                    self._record_overlay,
                    "update_step_count",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(int, len(self._record_steps))
                )

    def _stop_recording(self):
        if not self._recording:
            return

        self._recording = False

        # Flush any pending key buffer
        self._flush_record_key_buffer()

        # Stop listeners
        if self._record_mouse_listener:
            try:
                self._record_mouse_listener.stop()
            except Exception:
                pass
            self._record_mouse_listener = None

        if self._record_keyboard_listener:
            try:
                self._record_keyboard_listener.stop()
            except Exception:
                pass
            self._record_keyboard_listener = None

        if self._record_stop_hotkey:
            try:
                self._record_stop_hotkey.stop()
            except Exception:
                pass
            self._record_stop_hotkey = None

        # Close overlay
        if self._record_overlay:
            try:
                self._record_overlay.close()
            except Exception:
                pass
            self._record_overlay = None

        # Show main window again with whitescreen fix
        self._show_window()
        self._record_btn.setChecked(False)

        logger.info(f"Recording stopped \u2014 {len(self._record_steps)} steps captured")

        if not self._record_steps:
            self._status.showMessage("Recording cancelled \u2014 no steps captured", 3000)
            return

        self._insert_recorded_steps()

    def _insert_recorded_steps(self):
        dlg = RecordReviewDialog(self._record_steps, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            steps = dlg.get_steps()
            if steps:
                current_steps = self._current_macro.get("steps", [])
                offset = len(current_steps)
                for i, s in enumerate(steps):
                    s["id"] = offset + i + 1
                current_steps.extend(steps)
                self._current_macro["steps"] = current_steps
                self._modified = True
                self._refresh_steps_list()
                self._update_title()
                self._status.showMessage(
                    f"\u2705 Inserted {len(steps)} recorded steps into macro", 5000)

        self._record_steps = []


# ═════════════════════════════════════════════════════════════════════════
#  Application Entry Point
# ═════════════════════════════════════════════════════════════════════════

def main():
    """Application entry point."""
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # Set app icon
    icon_path = BASE_DIR / "gwperintahin.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    else:
        app.setWindowIcon(app.style().standardIcon(
            QStyle.StandardPixmap.SP_ComputerIcon))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
