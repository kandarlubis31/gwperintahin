#!/usr/bin/env python3
"""gwperintahin — Dialog Classes (Step Editor, Record Review, Schedule Manager)"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QLineEdit,
    QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QFileDialog,
    QMessageBox, QGroupBox, QFormLayout, QScrollArea,
    QFrame, QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

import pyautogui

from gui_constants import (
    BASE_DIR, MACROS_DIR,
    ACTION_TYPES, ACTION_DEFAULTS, ACTION_PARAM_DEFS,
    _scheduled_task_name, create_scheduled_task,
    delete_scheduled_task, run_scheduled_task_now, query_task_exists,
    load_scheduled_tasks, save_scheduled_tasks,
)
from gui_overlays import ColorPickerOverlay, RegionCaptureOverlay


# ═════════════════════════════════════════════════════════════════════════
#  Add / Edit Step Dialog
# ═════════════════════════════════════════════════════════════════════════

class StepDialog(QDialog):
    """Dialog for adding or editing a macro step."""

    def __init__(self, parent=None, step_data=None):
        super().__init__(parent)
        self.setWindowTitle("Add Step" if step_data is None else "Edit Step")
        self.setMinimumWidth(520)
        self.setModal(True)

        self._step_data = step_data or {}
        self._widgets = {}
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(12)
        self._build_ui()

    def _build_ui(self):
        # Action selector
        form = QFormLayout()
        self._action_combo = QComboBox()
        for action_id, label, icon in ACTION_TYPES:
            self._action_combo.addItem(f"{icon} {label}", action_id)

        current_action = self._step_data.get("action", "click_coord")
        idx = self._action_combo.findData(current_action)
        if idx >= 0:
            self._action_combo.setCurrentIndex(idx)

        form.addRow("Action:", self._action_combo)
        self._layout.addLayout(form)

        # Config area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._config_widget = QWidget()
        self._config_layout = QFormLayout(self._config_widget)
        self._config_layout.setSpacing(8)
        self._config_layout.setContentsMargins(0, 4, 0, 4)
        self._scroll.setWidget(self._config_widget)
        self._layout.addWidget(self._scroll, 1)

        # Buttons
        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        self._btn_box.accepted.connect(self._accept)
        self._btn_box.rejected.connect(self.reject)
        self._layout.addWidget(self._btn_box)

        self._action_combo.currentIndexChanged.connect(self._rebuild_config)
        self._rebuild_config()

    def _rebuild_config(self):
        # Clear existing widgets
        while self._config_layout.count():
            item = self._config_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._widgets.clear()

        action_id = self._action_combo.currentData()
        param_defs = ACTION_PARAM_DEFS.get(action_id, [])
        defaults = ACTION_DEFAULTS.get(action_id, {})

        for pdef in param_defs:
            key, ptype, label = pdef[:3]
            existing_val = self._step_data.get(key, defaults.get(key))
            widget = None

            if ptype == "text":
                widget = QLineEdit()
                if existing_val:
                    widget.setText(str(existing_val))
                widget.setPlaceholderText(f"Enter {label.lower()}\u2026")

            elif ptype == "text_area":
                widget = QTextEdit()
                widget.setMaximumHeight(100)
                if existing_val:
                    widget.setPlainText(str(existing_val))
                widget.setPlaceholderText(f"Enter {label.lower()}\u2026")

            elif ptype == "int":
                widget = QSpinBox()
                minv, maxv = pdef[3], pdef[4]
                widget.setRange(minv, maxv)
                if existing_val is not None:
                    widget.setValue(int(existing_val))

            elif ptype == "float":
                widget = QDoubleSpinBox()
                minv, maxv, step = pdef[3], pdef[4], pdef[5]
                widget.setRange(minv, maxv)
                widget.setSingleStep(step)
                if existing_val is not None:
                    widget.setValue(float(existing_val))

            elif ptype == "combo":
                widget = QComboBox()
                choices = pdef[3]
                widget.addItems(choices)
                if existing_val in choices:
                    widget.setCurrentText(existing_val)

            elif ptype == "combo_edit":
                widget = QComboBox()
                widget.setEditable(True)
                choices = pdef[3]
                widget.addItems(choices)
                if existing_val:
                    widget.setCurrentText(existing_val)

            elif ptype == "file":
                w = QWidget()
                hl = QHBoxLayout(w)
                hl.setContentsMargins(0, 0, 0, 0)
                line = QLineEdit()
                if existing_val:
                    line.setText(str(existing_val))
                line.setPlaceholderText(f"Select {label.lower()}\u2026")
                btn = QPushButton("Browse\u2026")
                filters = pdef[3] if len(pdef) > 3 else "All Files (*)"
                btn.clicked.connect(lambda _, le=line, filt=filters:
                    self._browse_file(le, filt))
                hl.addWidget(line, 1)
                hl.addWidget(btn)
                widget = w
                self._widgets[key] = (widget, line)

            elif ptype == "color":
                w = QWidget()
                hl = QHBoxLayout(w)
                hl.setContentsMargins(0, 0, 0, 0)
                line = QLineEdit()
                if existing_val:
                    line.setText(str(existing_val))
                line.setPlaceholderText("#RRGGBB")
                line.setFixedWidth(100)
                preview = QLabel("\u2b24")
                preview.setStyleSheet("font-size: 22px; color: " +
                    (existing_val or "#000000") + ";")
                line.textChanged.connect(
                    lambda t, lbl=preview: lbl.setStyleSheet(
                        f"font-size: 22px; color: {t};"
                    ) if t.startswith("#") and len(t) == 7 else None
                )
                pick_btn = QPushButton("\U0001f3a8 Pick")
                pick_btn.clicked.connect(lambda: self._open_color_picker(line, preview))
                hl.addWidget(line)
                hl.addWidget(preview)
                hl.addWidget(pick_btn)
                hl.addStretch()
                widget = w
                self._widgets[key] = (widget, line)

            elif ptype == "coord":
                w = QWidget()
                hl = QHBoxLayout(w)
                hl.setContentsMargins(0, 0, 0, 0)
                line = QLineEdit()
                if existing_val and isinstance(existing_val, (list, tuple)):
                    line.setText(f"{existing_val[0]}, {existing_val[1]}")
                line.setPlaceholderText("x, y")
                pick_btn = QPushButton("\U0001f4cd Pick")
                pick_btn.clicked.connect(lambda: self._open_coord_picker(line))
                hl.addWidget(line, 1)
                hl.addWidget(pick_btn)
                widget = w
                self._widgets[key] = (widget, line)

            elif ptype == "region":
                w = QWidget()
                hl = QHBoxLayout(w)
                hl.setContentsMargins(0, 0, 0, 0)
                line = QLineEdit()
                if existing_val and isinstance(existing_val, (list, tuple)):
                    line.setText(f"{existing_val[0]}, {existing_val[1]}, {existing_val[2]}, {existing_val[3]}")
                line.setPlaceholderText("x, y, w, h (optional)")
                pick_btn = QPushButton("\U0001f4d0 Select")
                pick_btn.clicked.connect(lambda: self._open_region_selector(line))
                hl.addWidget(line, 1)
                hl.addWidget(pick_btn)
                widget = w
                self._widgets[key] = (widget, line)

            if widget:
                self._config_layout.addRow(label + ":", widget)

    def _browse_file(self, line_edit, filters):
        from gui_constants import BASE_DIR
        path, _ = QFileDialog.getOpenFileName(self, "Select File", "", filters)
        if path:
            try:
                rel = Path(path).relative_to(BASE_DIR)
                line_edit.setText(str(rel))
            except ValueError:
                line_edit.setText(path)

    def _open_color_picker(self, line_edit, preview_label):
        self.hide()
        picker = ColorPickerOverlay()
        picker.color_selected.connect(lambda c: (
            line_edit.setText(c),
            preview_label.setStyleSheet(f"font-size: 22px; color: {c};"),
        ))
        picker.destroyed.connect(lambda obj=None: QTimer.singleShot(0, self.show))
        picker.show()

    def _open_coord_picker(self, line_edit):
        self.hide()
        QTimer.singleShot(300, lambda: self._do_coord_pick(line_edit))

    def _do_coord_pick(self, line_edit):
        pos = pyautogui.position()
        line_edit.setText(f"{pos.x}, {pos.y}")
        self.show()

    def _open_region_selector(self, line_edit):
        self.hide()
        QTimer.singleShot(300, lambda: self._do_region_select(line_edit))

    def _do_region_select(self, line_edit):
        overlay = RegionCaptureOverlay()
        overlay.region_captured.connect(lambda r: (
            line_edit.setText(f"{r[0]}, {r[1]}, {r[2]}, {r[3]}"),
        ))
        overlay.destroyed.connect(lambda obj=None: QTimer.singleShot(0, self.show))
        overlay.show()

    def _accept(self):
        action_id = self._action_combo.currentData()
        result = {"action": action_id}
        param_defs = ACTION_PARAM_DEFS.get(action_id, [])
        defaults = ACTION_DEFAULTS.get(action_id, {})

        for pdef in param_defs:
            key, ptype = pdef[:2]
            val = None

            if key in self._widgets:
                w = self._widgets[key]
                if isinstance(w, tuple):
                    line = w[1]
                    text = line.text().strip()

                    if ptype == "file":
                        val = text if text else None
                    elif ptype == "color":
                        val = text if text and text.startswith("#") else None
                    elif ptype == "coord":
                        parts = [p.strip() for p in text.split(",")]
                        if len(parts) >= 2:
                            try:
                                val = [int(parts[0]), int(parts[1])]
                            except ValueError:
                                val = None
                    elif ptype == "region":
                        parts = [p.strip() for p in text.split(",")]
                        if len(parts) >= 4:
                            try:
                                val = [int(parts[0]), int(parts[1]),
                                       int(parts[2]), int(parts[3])]
                            except ValueError:
                                val = None
                else:
                    if ptype == "text":
                        val = w.text().strip() or None
                    elif ptype == "text_area":
                        val = w.toPlainText().strip() or None
                    elif ptype == "int":
                        val = w.value()
                    elif ptype == "float":
                        val = w.value()
                    elif ptype in ("combo", "combo_edit"):
                        val = w.currentText().strip()

                if val is not None:
                    result[key] = val

        for k, dv in defaults.items():
            if k not in result:
                result[k] = dv

        self._step_data = result
        self.accept()

    def get_step_data(self):
        return self._step_data


# ═════════════════════════════════════════════════════════════════════════
#  Record Review Dialog
# ═════════════════════════════════════════════════════════════════════════

class RecordReviewDialog(QDialog):
    """
    Dialog showing recorded steps after recording stops.
    User can review, delete unwanted steps, and insert into macro.
    """

    def __init__(self, steps: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("\U0001f534 Recording Complete \u2014 Review Steps")
        self.setMinimumSize(600, 400)
        self.setModal(True)

        self._steps = steps
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(12)
        self._build_ui()

    def _build_ui(self):
        header = QLabel(f"<b>Recorded {len(self._steps)} actions</b> \u2014 Review and edit before inserting:")
        header.setStyleSheet("font-size: 14px; padding: 4px 0;")
        self._layout.addWidget(header)

        # Steps list
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                font-size: 13px;
                selection-background-color: #2d2f33;
                selection-color: #ffffff;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
                color: #d0d0d0;
            }
            QListWidget::item:selected {
                background: #2d2f33;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background: #252629;
                color: #e8e8e8;
            }
            QListWidget::item:selected:hover {
                background: #34363a;
                color: #ffffff;
            }
        """)

        for i, step in enumerate(self._steps):
            action = step.get("action", "unknown")
            summary = self._step_summary(step)
            display = f"{i+1}. {action}  \u2014  {summary}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._list.addItem(item)

        self._layout.addWidget(self._list, 1)

        # Buttons
        btn_layout = QHBoxLayout()

        delete_btn = QPushButton("\U0001f5d1\ufe0f Delete Selected")
        delete_btn.clicked.connect(self._delete_selected)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(clear_btn)

        cancel_btn = QPushButton("Discard & Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        insert_btn = QPushButton("\u2705 Insert into Macro")
        insert_btn.setObjectName("testBtn")
        insert_btn.clicked.connect(self._insert)
        btn_layout.addWidget(insert_btn)

        self._layout.addLayout(btn_layout)

    def _step_summary(self, step):
        action = step.get("action", "")
        if action == "click_coord":
            return f"({step.get('x', '?')}, {step.get('y', '?')}) \u2014 {step.get('button', 'left')}"
        elif action == "type_text":
            text = step.get("text", "")
            return f'"{text[:40]}{"\u2026" if len(text) > 40 else ""}"'
        elif action == "press_key":
            return f"{step.get('key', '?')}"
        elif action == "wait_seconds":
            return f"{step.get('duration', 0.3)}s"
        return str(step)

    def _delete_selected(self):
        current = self._list.currentItem()
        if current:
            idx = current.data(Qt.ItemDataRole.UserRole)
            if idx is not None and 0 <= idx < len(self._steps):
                self._steps.pop(idx)
                self._refresh_list()

    def _clear_all(self):
        reply = QMessageBox.question(self, "Clear All",
            "Remove all recorded steps?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._steps.clear()
            self._refresh_list()

    def _refresh_list(self):
        self._list.clear()
        for i, step in enumerate(self._steps):
            action = step.get("action", "unknown")
            summary = self._step_summary(step)
            display = f"{i+1}. {action}  \u2014  {summary}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._list.addItem(item)

    def _insert(self):
        self.accept()

    def get_steps(self):
        return self._steps


# ═════════════════════════════════════════════════════════════════════════
#  Schedule Dialog
# ═════════════════════════════════════════════════════════════════════════

class ScheduleDialog(QDialog):
    """
    Dialog for managing Windows Scheduled Tasks for macros.
    Users can create, view, run, and delete scheduled tasks.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("\u23f0 Schedule Macro \u2014 Windows Task Scheduler")
        self.setMinimumSize(700, 520)
        self.setModal(True)

        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(12)
        self._build_ui()

    def _build_ui(self):
        # ── Existing tasks ──
        existing_group = QGroupBox("Scheduled Tasks")
        existing_layout = QVBoxLayout(existing_group)
        existing_layout.setSpacing(6)

        self._task_list = QListWidget()
        self._task_list.setStyleSheet("""
            QListWidget {
                selection-background-color: #2d2f33;
                selection-color: #ffffff;
                outline: none;
            }
            QListWidget::item {
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background: #2d2f33;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background: #252629;
                color: #e8e8e8;
            }
            QListWidget::item:selected:hover {
                background: #34363a;
                color: #ffffff;
            }
        """)
        self._task_list.itemSelectionChanged.connect(self._on_selection_changed)
        existing_layout.addWidget(self._task_list, 1)

        task_btn_layout = QHBoxLayout()
        self._run_now_btn = QPushButton("\u25b6 Run Now")
        self._run_now_btn.setObjectName("testBtn")
        self._run_now_btn.setEnabled(False)
        self._run_now_btn.clicked.connect(self._run_selected)

        self._delete_btn = QPushButton("\U0001f5d1\ufe0f Delete")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._delete_selected)

        self._refresh_btn = QPushButton("\U0001f504 Refresh")
        self._refresh_btn.clicked.connect(self._refresh_tasks)

        task_btn_layout.addWidget(self._run_now_btn)
        task_btn_layout.addWidget(self._delete_btn)
        task_btn_layout.addStretch()
        task_btn_layout.addWidget(self._refresh_btn)
        existing_layout.addLayout(task_btn_layout)

        self._layout.addWidget(existing_group, 1)

        # ── Create new schedule ──
        create_group = QGroupBox("Create New Schedule")
        create_layout = QVBoxLayout(create_group)
        create_layout.setSpacing(8)

        # Macro file
        macro_row = QHBoxLayout()
        macro_row.addWidget(QLabel("Macro (.json):"))
        self._macro_path_edit = QLineEdit()
        self._macro_path_edit.setPlaceholderText("Select a saved macro JSON\u2026")
        macro_row.addWidget(self._macro_path_edit, 1)
        browse_btn = QPushButton("Browse\u2026")
        browse_btn.clicked.connect(self._browse_macro)
        macro_row.addWidget(browse_btn)
        create_layout.addLayout(macro_row)

        # Schedule type
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Schedule:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems([
            "Once", "Daily", "Weekly", "Monthly",
            "On Logon", "On Startup", "On Idle"
        ])
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        type_row.addWidget(self._type_combo)
        type_row.addStretch()
        create_layout.addLayout(type_row)

        # Time
        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Time (HH:MM):"))
        self._time_edit = QLineEdit()
        self._time_edit.setPlaceholderText("14:30")
        self._time_edit.setFixedWidth(120)
        time_row.addWidget(self._time_edit)

        date_label = QLabel("Date (YYYY-MM-DD):")
        time_row.addWidget(date_label)
        self._date_edit = QLineEdit()
        self._date_edit.setPlaceholderText("2025-12-31")
        self._date_edit.setFixedWidth(140)
        time_row.addWidget(self._date_edit)
        time_row.addStretch()
        self._date_edit.setVisible(True)
        self._date_label = date_label
        create_layout.addLayout(time_row)

        # Days / interval
        days_row = QHBoxLayout()
        self._days_label = QLabel("Days interval / Day(s):")
        self._days_edit = QLineEdit()
        self._days_edit.setPlaceholderText("e.g. 1 (daily), MON,WED (weekly), 15 (monthly)")
        self._days_edit.setFixedWidth(300)
        days_row.addWidget(self._days_label)
        days_row.addWidget(self._days_edit)
        days_row.addStretch()
        self._days_row_widget = QWidget()
        self._days_row_widget.setLayout(days_row)
        create_layout.addWidget(self._days_row_widget)

        # Executor path
        exec_row = QHBoxLayout()
        exec_row.addWidget(QLabel("Executor exe path:"))
        self._exec_path_edit = QLineEdit()
        self._exec_path_edit.setPlaceholderText("Leave empty = auto-detect")
        exec_row.addWidget(self._exec_path_edit, 1)
        exec_browse_btn = QPushButton("Browse\u2026")
        exec_browse_btn.clicked.connect(self._browse_executor)
        exec_row.addWidget(exec_browse_btn)
        create_layout.addLayout(exec_row)

        # Create button
        create_btn_layout = QHBoxLayout()
        create_btn_layout.addStretch()
        self._create_btn = QPushButton("\u2705 Create Schedule")
        self._create_btn.setObjectName("saveBtn")
        self._create_btn.clicked.connect(self._create_schedule)
        create_btn_layout.addWidget(self._create_btn)
        create_layout.addLayout(create_btn_layout)

        self._layout.addWidget(create_group)

        # Dialog buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        self._layout.addWidget(btn_box)

        # Initial state
        self._on_type_changed("Once")
        self._refresh_tasks()

    def _on_type_changed(self, stype: str):
        needs_time = stype in ("Once", "Daily", "Weekly", "Monthly")
        needs_date = stype == "Once"
        needs_days = stype in ("Daily", "Weekly", "Monthly", "On Idle")

        self._time_edit.setEnabled(needs_time)
        self._date_edit.setVisible(needs_date)
        if self._date_label:
            self._date_label.setVisible(needs_date)
        self._days_row_widget.setVisible(needs_days)

        if stype == "Daily":
            self._days_edit.setPlaceholderText("Every N days (e.g. 1 = every day)")
        elif stype == "Weekly":
            self._days_edit.setPlaceholderText("Day(s): MON,TUE,WED,THU,FRI,SAT,SUN")
        elif stype == "Monthly":
            self._days_edit.setPlaceholderText("Day of month (e.g. 1 or 15)")
        elif stype == "On Idle":
            self._days_edit.setPlaceholderText("Idle minutes (e.g. 10)")

    def _browse_macro(self):
        from gui_constants import MACROS_DIR
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Macro", str(MACROS_DIR), "JSON Files (*.json)")
        if path:
            self._macro_path_edit.setText(path)

    def _browse_executor(self):
        from gui_constants import BASE_DIR
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Executor", str(BASE_DIR), "Executable (*.exe)")
        if path:
            self._exec_path_edit.setText(path)

    def _refresh_tasks(self):
        self._task_list.clear()
        tracked = load_scheduled_tasks()

        if not tracked:
            item = QListWidgetItem("\u2601\ufe0f  No scheduled tasks. Create one below.")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.setForeground(QColor("#888"))
            self._task_list.addItem(item)
            self._run_now_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            return

        for t in tracked:
            task_name = t.get("task_name", "")
            exists = query_task_exists(task_name)

            icon = "\u2705" if exists else "\u274c"
            stype = t.get("schedule_type", "?").capitalize()
            time_str = t.get("time", "")
            macro = Path(t.get("macro_path", "")).stem
            status = "Active" if exists else "Missing from scheduler"

            display = f"{icon}  {t.get('task_name', '?')}  \u2014  {stype}  {time_str}  \u2014  {macro}  ({status})"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, t)
            item.setForeground(QColor("#ddd" if exists else "#ff6b6b"))
            self._task_list.addItem(item)

        self._on_selection_changed()

    def _on_selection_changed(self):
        has_selection = self._task_list.currentItem() is not None
        has_data = has_selection and self._task_list.currentItem().data(Qt.ItemDataRole.UserRole) is not None
        self._run_now_btn.setEnabled(has_data)
        self._delete_btn.setEnabled(has_data)

    def _run_selected(self):
        item = self._task_list.currentItem()
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        task_name = data.get("task_name", "")
        success, msg = run_scheduled_task_now(task_name)
        if success:
            QMessageBox.information(self, "Task Started",
                f"Task '{task_name}' has been triggered!")
        else:
            QMessageBox.warning(self, "Error",
                f"Could not run task:\n\n{msg}")

    def _delete_selected(self):
        item = self._task_list.currentItem()
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        task_name = data.get("task_name", "")
        reply = QMessageBox.question(self, "Delete Task",
            f"Delete scheduled task '{task_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            success, msg = delete_scheduled_task(task_name)
            if success:
                tracked = load_scheduled_tasks()
                tracked = [t for t in tracked if t.get("task_name") != task_name]
                save_scheduled_tasks(tracked)
                self._status(f"Deleted: {task_name}")
                self._refresh_tasks()
            else:
                QMessageBox.warning(self, "Error", f"Could not delete:\n\n{msg}")

    def _status(self, msg: str):
        parent = self.parent()
        if parent and hasattr(parent, '_status'):
            parent._status.showMessage(msg, 3000)

    def _create_schedule(self):
        macro_path = self._macro_path_edit.text().strip()
        if not macro_path:
            QMessageBox.warning(self, "Missing", "Select a macro .json file first.")
            return
        if not Path(macro_path).exists():
            QMessageBox.warning(self, "Not Found", f"Macro file not found:\n{macro_path}")
            return

        stype = self._type_combo.currentText().lower().replace(" ", "")
        time_str = self._time_edit.text().strip()
        date_str = self._date_edit.text().strip()
        days_str = self._days_edit.text().strip()
        exec_path = self._exec_path_edit.text().strip()

        # Auto-detect executor path
        if not exec_path:
            if getattr(sys, 'frozen', False):
                guessed = Path(sys.executable).parent / "executor.exe"
            else:
                from gui_constants import BASE_DIR
                guessed = BASE_DIR / "executor.exe"
            if guessed.exists():
                exec_path = str(guessed)

        needs_time = stype in ("once", "daily", "weekly", "monthly")
        if needs_time and not time_str:
            QMessageBox.warning(self, "Missing Time",
                "Please enter a time (HH:MM format, e.g. 14:30).")
            return

        if stype == "once" and not date_str:
            QMessageBox.warning(self, "Missing Date",
                "Please enter a date (YYYY-MM-DD format, e.g. 2025-12-31).")
            return

        macro_name = Path(macro_path).stem
        task_name = _scheduled_task_name(macro_name)

        tracked = load_scheduled_tasks()
        existing_names = [t.get("task_name") for t in tracked]
        if task_name in existing_names:
            reply = QMessageBox.question(self, "Task Exists",
                f"A task for '{macro_name}' already exists.\n\nOverwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
            delete_scheduled_task(task_name)
            tracked = [t for t in tracked if t.get("task_name") != task_name]

        success, msg = create_scheduled_task(
            task_name, macro_path, stype, time_str, date_str, days_str, exec_path
        )

        if success:
            from datetime import datetime
            tracked.append({
                "task_name": task_name,
                "macro_path": macro_path,
                "schedule_type": stype,
                "time": time_str,
                "date": date_str,
                "days": days_str,
                "created": datetime.now().isoformat(),
            })
            save_scheduled_tasks(tracked)

            QMessageBox.information(self, "Task Created",
                f"\u2705 Scheduled task created successfully!\n\n"
                f"Name: {task_name}\n"
                f"Schedule: {self._type_combo.currentText()}\n"
                f"Macro: {macro_name}\n\n"
                f"You can view/manage it in Windows Task Scheduler.")
            self._refresh_tasks()
            self._macro_path_edit.clear()
            self._time_edit.clear()
            self._date_edit.clear()
            self._days_edit.clear()
        else:
            QMessageBox.warning(self, "Error",
                f"Could not create task. Error:\n\n{msg}")
