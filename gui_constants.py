#!/usr/bin/env python3
"""gwperintahin — Shared Constants & Data Definitions"""

import json
import logging
import subprocess
import sys
from pathlib import Path

# ═════════════════════════════════════════════════════════════════════════
#  Constants
# ═════════════════════════════════════════════════════════════════════════

APP_NAME = "gwperintahin"
APP_VERSION = "1.0.0"
BASE_DIR = Path(__file__).parent.resolve()
MACROS_DIR = BASE_DIR / "macros"
TEMPLATES_DIR = BASE_DIR / "templates"
LOGS_DIR = BASE_DIR / "logs"
EXPORTS_DIR = BASE_DIR / "exports"

# Ensure folders exist
for d in (MACROS_DIR, TEMPLATES_DIR, LOGS_DIR, EXPORTS_DIR):
    d.mkdir(exist_ok=True)

# ── Logging ──────────────────────────────────────────────────────────────
logger = logging.getLogger("gwperintahin")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    )
    _ch = logging.StreamHandler()
    _ch.setFormatter(_fmt)
    logger.addHandler(_ch)

# ── pynput availability ───────────────────────────────────────────────
try:
    import pynput  # noqa: F401
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

# ── executor availability ──────────────────────────────────────────────
try:
    from executor import MacroExecutor  # noqa: F401
    HAS_EXECUTOR = True
except ImportError:
    HAS_EXECUTOR = False


# ═════════════════════════════════════════════════════════════════════════
#  Action Type Definitions
# ═════════════════════════════════════════════════════════════════════════

ACTION_TYPES = [
    ("wait_for_image",   "Wait for Image",       "\U0001f5bc\ufe0f"),
    ("wait_for_color",   "Wait for Color",       "\U0001f3a8"),
    ("click_image",      "Click Image",          "\U0001f446"),
    ("click_color",      "Click Color",          "\U0001f3af"),
    ("click_coord",      "Click Coordinate",     "\U0001f4cd"),
    ("right_click_coord","Right Click Coord",    "\U0001f5b1\ufe0f"),
    ("double_click",     "Double Click",         "\U0001f504"),
    ("type_text",        "Type Text",            "\u2328\ufe0f"),
    ("press_key",        "Press Key",            "\U0001f511"),
    ("scroll",           "Scroll",               "\U0001f4dc"),
    ("wait_seconds",     "Wait (Seconds)",       "\u23f1\ufe0f"),
    ("wait_for_window",  "Wait for Window",      "\U0001fa9f"),
    ("focus_window",     "Focus Window",         "\U0001f3af"),
    ("screenshot",       "Screenshot",           "\U0001f4f7"),
    ("loop",             "Loop",                 "\U0001f501"),
    ("if_else",          "If/Else Condition",    "\u2753"),
    ("set_variable",     "Set Variable",         "\U0001f4ca"),
    ("exit",             "Exit Macro",           "\U0001f6aa"),
]

ACTION_DEFAULTS = {
    "wait_for_image":   {"target": "", "confidence": 0.85, "timeout": 30, "region": None, "on_found": "next", "on_timeout": "exit"},
    "wait_for_color":   {"color": "#000000", "region": None, "tolerance": 20, "timeout": 10, "on_found": "next", "on_timeout": "exit"},
    "click_image":      {"target": "", "confidence": 0.80, "fallback": "click_color", "fallback_color": "", "fallback_coord": None},
    "click_color":      {"color": "#000000", "region": None, "tolerance": 20, "fallback_coord": None},
    "click_coord":      {"x": 0, "y": 0, "button": "left"},
    "right_click_coord":{"x": 0, "y": 0},
    "double_click":     {"x": None, "y": None, "target": None, "confidence": 0.8},
    "type_text":        {"text": "", "delay_between_keys": 0.02},
    "press_key":        {"key": ""},
    "scroll":           {"direction": "down", "amount": 3, "x": None, "y": None},
    "wait_seconds":     {"duration": 1.0},
    "wait_for_window":  {"title": "", "timeout": 30},
    "focus_window":     {"title": ""},
    "screenshot":       {"save_path": "", "region": None},
    "loop":             {"steps": [], "count": 1},
    "if_else":          {"condition": {}, "then_steps": [], "else_steps": []},
    "set_variable":     {"name": "", "value": 0},
    "exit":             {},
}

ACTION_PARAM_DEFS = {
    "wait_for_image": [
        ("target", "file", "Template Image (.png)", "*.png"),
        ("confidence", "float", "Confidence", 0.0, 1.0, 0.05),
        ("timeout", "int", "Timeout (sec)", 1, 300),
        ("on_timeout", "combo", "On Timeout", ["exit", "skip", "fallback_coord"]),
    ],
    "wait_for_color": [
        ("color", "color", "Color"),
        ("tolerance", "int", "Tolerance", 0, 255),
        ("timeout", "int", "Timeout (sec)", 1, 300),
        ("region", "region", "Region (x,y,w,h)"),
        ("on_timeout", "combo", "On Timeout", ["exit", "skip"]),
    ],
    "click_image": [
        ("target", "file", "Template Image (.png)", "*.png"),
        ("confidence", "float", "Confidence", 0.0, 1.0, 0.05),
        ("fallback", "combo", "Fallback", ["none", "click_color", "click_coord"]),
        ("fallback_color", "color", "Fallback Color"),
        ("fallback_coord", "coord", "Fallback Coordinate"),
    ],
    "click_color": [
        ("color", "color", "Color"),
        ("tolerance", "int", "Tolerance", 0, 255),
        ("region", "region", "Region (x,y,w,h)"),
        ("fallback_coord", "coord", "Fallback Coordinate"),
    ],
    "click_coord": [
        ("x", "int", "X", 0, 99999),
        ("y", "int", "Y", 0, 99999),
        ("button", "combo", "Button", ["left", "middle", "right"]),
    ],
    "right_click_coord": [
        ("x", "int", "X", 0, 99999),
        ("y", "int", "Y", 0, 99999),
    ],
    "double_click": [
        ("target", "file", "Template Image (.png)", "*.png"),
        ("confidence", "float", "Confidence", 0.0, 1.0, 0.05),
        ("x", "int", "X (if no image)", 0, 99999),
        ("y", "int", "Y (if no image)", 0, 99999),
    ],
    "type_text": [
        ("text", "text_area", "Text to Type"),
        ("delay_between_keys", "float", "Key Delay (sec)", 0.0, 1.0, 0.01),
    ],
    "press_key": [
        ("key", "combo_edit", "Key / Shortcut",
         ["enter", "tab", "escape", "space", "backspace", "delete",
          "ctrl+c", "ctrl+v", "ctrl+a", "ctrl+x", "ctrl+z",
          "ctrl+s", "alt+tab", "alt+f4", "win+d", "win+r",
          "up", "down", "left", "right", "home", "end",
          "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12"]),
    ],
    "scroll": [
        ("direction", "combo", "Direction", ["down", "up"]),
        ("amount", "int", "Amount (clicks)", 1, 100),
        ("x", "int", "X Position (optional)", 0, 99999),
        ("y", "int", "Y Position (optional)", 0, 99999),
    ],
    "wait_seconds": [
        ("duration", "float", "Duration (sec)", 0.1, 999.0, 0.1),
    ],
    "wait_for_window": [
        ("title", "text", "Window Title"),
        ("timeout", "int", "Timeout (sec)", 1, 300),
    ],
    "focus_window": [
        ("title", "text", "Window Title"),
    ],
    "screenshot": [
        ("save_path", "text", "Save Path (leave empty = auto)"),
        ("region", "region", "Region (x,y,w,h)"),
    ],
    "loop": [
        ("count", "int", "Loop Count", 1, 9999),
    ],
    "if_else": [
        ("condition_type", "combo", "Condition Type",
         ["image_exists", "color_exists", "window_exists", "variable"]),
    ],
    "set_variable": [
        ("name", "text", "Variable Name"),
        ("value", "int", "Value", -99999, 99999),
    ],
    "exit": [],
}


# ═════════════════════════════════════════════════════════════════════════
#  Scheduling — Windows Task Scheduler Integration
# ═════════════════════════════════════════════════════════════════════════

SCHED_TASK_PREFIX = "gwperintahin-"

# Use real app directory for persistent data (important for PyInstaller)
if getattr(sys, 'frozen', False):
    SCHED_APP_DIR = Path(sys.executable).parent.resolve()
else:
    SCHED_APP_DIR = BASE_DIR
SCHED_TRACKING_FILE = SCHED_APP_DIR / "scheduled_tasks.json"

# Ensure tracking file exists
if not SCHED_TRACKING_FILE.exists():
    with open(SCHED_TRACKING_FILE, "w") as f:
        json.dump([], f)


def _scheduled_task_name(macro_name: str) -> str:
    """Generate a unique Task Scheduler name from a macro name."""
    safe = macro_name.strip().replace(" ", "_").replace("/", "_").replace("\\", "_")
    return f"{SCHED_TASK_PREFIX}{safe}"


def _schtasks(*args: str) -> subprocess.CompletedProcess:
    """Run schtasks.exe and return the result."""
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return subprocess.run(
        ["schtasks"] + list(args),
        capture_output=True, text=True,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
    )


def load_scheduled_tasks() -> list[dict]:
    """Load scheduled task tracking records from JSON file."""
    try:
        with open(SCHED_TRACKING_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_scheduled_tasks(tasks: list[dict]):
    """Save scheduled task tracking records to JSON file."""
    with open(SCHED_TRACKING_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def create_scheduled_task(
    task_name: str,
    macro_path: str,
    schedule_type: str,
    time_str: str = "",
    date_str: str = "",
    days: str = "",
    exec_path: str = ""
) -> tuple[bool, str]:
    """Create a Windows Scheduled Task using schtasks.exe.
    Returns (success: bool, message: str).
    """
    if not exec_path:
        exec_path = str(BASE_DIR / "executor.exe")

    tr = f'"{exec_path}" --macro "{macro_path}" --log "{LOGS_DIR / Path(macro_path).stem}.log"'

    args = ["/create", "/tn", task_name, "/tr", tr, "/f"]

    if schedule_type == "once":
        args.extend(["/sc", "once"])
        if time_str:
            args.extend(["/st", time_str])
        if date_str:
            args.extend(["/sd", date_str])
    elif schedule_type == "daily":
        args.extend(["/sc", "daily"])
        if time_str:
            args.extend(["/st", time_str])
        if days:
            try:
                args.extend(["/mo", str(int(days))])
            except ValueError:
                pass
    elif schedule_type == "weekly":
        args.extend(["/sc", "weekly"])
        if time_str:
            args.extend(["/st", time_str])
        if days:
            args.extend(["/d", days.upper()])
    elif schedule_type == "monthly":
        args.extend(["/sc", "monthly"])
        if time_str:
            args.extend(["/st", time_str])
        if days:
            try:
                args.extend(["/mo", str(int(days))])
            except ValueError:
                pass
    elif schedule_type == "onlogon":
        args.extend(["/sc", "onlogon"])
    elif schedule_type == "onstartup":
        args.extend(["/sc", "onstartup"])
    elif schedule_type == "onidle":
        args.extend(["/sc", "onidle", "/mo", days or "10"])
    else:
        return False, f"Unknown schedule type: {schedule_type}"

    if schedule_type in ("once", "daily", "weekly", "monthly"):
        args.extend(["/rl", "HIGHEST"])

    result = _schtasks(*args)
    if result.returncode == 0:
        return True, result.stdout.strip() or "Task created successfully"
    else:
        err = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        return False, err


def delete_scheduled_task(task_name: str) -> tuple[bool, str]:
    """Delete a Windows Scheduled Task."""
    result = _schtasks("/delete", "/tn", task_name, "/f")
    if result.returncode == 0:
        return True, "Task deleted"
    else:
        return False, result.stderr.strip() or "Failed to delete task"


def run_scheduled_task_now(task_name: str) -> tuple[bool, str]:
    """Run a scheduled task immediately."""
    result = _schtasks("/run", "/tn", task_name)
    if result.returncode == 0:
        return True, "Task started"
    else:
        return False, result.stderr.strip() or "Failed to run task"


def query_task_exists(task_name: str) -> bool:
    """Check if a task exists in the Task Scheduler."""
    result = _schtasks("/query", "/tn", task_name, "/fo", "LIST")
    return result.returncode == 0
