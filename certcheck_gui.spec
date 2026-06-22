# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — builds the standalone GUI: dist\certcheck-gui.exe
# Windowed (no console). Build with:  pyinstaller certcheck_gui.spec  (or .\build.ps1)

a = Analysis(
    ['certcheck_gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['openpyxl'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='certcheck-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
