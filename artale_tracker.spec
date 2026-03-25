# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Artale EXP Tracker."""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PIL',
        'PIL.Image',
        'numpy',
        # macOS frameworks via pyobjc
        'objc',
        'Quartz',
        'Vision',
        'AppKit',
        'Foundation',
        'CoreFoundation',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'pytest',
        'pytesseract',  # no longer needed, using Vision
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Artale EXP Tracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Artale EXP Tracker',
)

app = BUNDLE(
    coll,
    name='Artale EXP Tracker.app',
    icon=None,  # TODO: add app icon later
    bundle_identifier='com.artale.exptracker',
    info_plist={
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleName': 'Artale EXP Tracker',
        'NSAppleEventsUsageDescription': 'Required for screen capture',
        'NSScreenCaptureUsageDescription': 'Required to read game status bar',
    },
)
