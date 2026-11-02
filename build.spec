# -*- mode: python ; coding: utf-8 -*-
"""
gwperintahin — PyInstaller Build Spec

Build commands:
    pyinstaller build.spec            # Build both executables
    pyinstaller build.spec --gui      # Build only GUI
    pyinstaller build.spec --executor # Build only executor
"""

import sys
import os
from pathlib import Path

# ── Project root ───────────────────────────────────────────────
# Use cwd-based resolution for PyInstaller compatibility
ROOT = Path(os.getcwd()).resolve()

# ── Block cipher (optional, for obfuscation) ───────────────────
block_cipher = None

# ── Common hidden imports ──────────────────────────────────────
# These are needed because PyInstaller may miss them
HIDDEN_IMPORTS = [
    "numpy",
    "pyautogui",
    "pygetwindow",
    "PIL",
    "PIL.ImageGrab",
    "PIL.ImageQt",
    "pkg_resources",
]

# ── Builder: gwperintahin.exe (GUI) ────────────────────────────
gui_a = Analysis(
    ['gwperintahin.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "macros"), "macros"),
        (str(ROOT / "templates"), "templates"),
        (str(ROOT / "logs"), "logs"),
        (str(ROOT / "exports"), "exports"),
        (str(ROOT / "README.txt"), "."),
        (str(ROOT / "gui_constants.py"), "."),
        (str(ROOT / "gui_overlays.py"), "."),
        (str(ROOT / "gui_dialogs.py"), "."),
        (str(ROOT / "gui_main.py"), "."),
        (str(ROOT / "gwperintahin.ico"), "."),
    ],
    hiddenimports=HIDDEN_IMPORTS + ["PyQt6.QtSvg"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "cv2", "tkinter", "matplotlib", "scipy", "pandas",
        "IPython", "jupyter", "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(gui_a.pure, gui_a.zipped_data, cipher=block_cipher)

gui_exe = EXE(
    pyz,
    gui_a.scripts,
    gui_a.binaries,
    gui_a.zipfiles,
    gui_a.datas,
    [],
    name='gwperintahin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window for GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='gwperintahin.ico',
)

# ── Builder: executor.exe (Runtime Engine) ─────────────────────
exec_a = Analysis(
    ['executor.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "macros"), "macros"),
        (str(ROOT / "templates"), "templates"),
        (str(ROOT / "logs"), "logs"),
        (str(ROOT / "exports"), "exports"),
        (str(ROOT / "gwperintahin.ico"), "."),
    ],
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "cv2", "tkinter", "PyQt6", "matplotlib", "scipy",
        "pandas", "IPython", "jupyter", "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

exec_pyz = PYZ(exec_a.pure, exec_a.zipped_data, cipher=block_cipher)

exec_exe = EXE(
    exec_pyz,
    exec_a.scripts,
    exec_a.binaries,
    exec_a.zipfiles,
    exec_a.datas,
    [],
    name='executor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,           # Console window for executor output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='gwperintahin.ico',
)

# ── COLLECT (only for onefile=False) ────────────────────────────
# If you want a single .exe instead of a folder, change to:
#     EXE(pyz, ...)
# Currently configured as one-file builds.
