#!/usr/bin/env python3
"""
gwperintahin — Windows Macro Agent Toolkit
GUI Builder for creating, editing, testing, and exporting Windows macro automation.

This is the application entry point. The actual implementation is split into modules:
  - gui_constants.py   → Constants, action definitions, scheduler helpers
  - gui_overlays.py    → Screen overlay widgets (color picker, region capture, recording)
  - gui_dialogs.py     → Dialog classes (step editor, record review, schedule)
  - gui_main.py        → MainWindow class and application entry point
  - executor.py        → Macro execution engine (standalone)

Usage:
    python gwperintahin.py
"""

from gui_main import main

if __name__ == "__main__":
    main()
