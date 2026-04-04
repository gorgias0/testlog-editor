# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

from icons import APP_ICON_SVG, ico_bytes_from_svg

EXCLUDED_QT_MODULES = [
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtXml",
]

EXCLUDED_MODULES = [
    "tkinter",
    "unittest",
    "pydoc",
    "doctest",
    "ftplib",
    "imaplib",
    "mailbox",
    "multiprocessing",
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    *EXCLUDED_QT_MODULES,
]

hiddenimports = collect_submodules("markdown_it") + collect_submodules("mdit_py_plugins")

icon_dir = Path("build") / "icons"
icon_dir.mkdir(parents=True, exist_ok=True)
windows_icon_path = icon_dir / "testlog-editor.ico"
windows_icon_path.write_bytes(ico_bytes_from_svg(APP_ICON_SVG))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_MODULES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TestLog Editor",
    icon=str(windows_icon_path),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="TestLog Editor",
)
