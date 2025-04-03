# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['poe_tools.py'],
    pathex=[],
    binaries=[('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python310\\python310.dll', '.')],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'tkinter', 'PySide2', 'PyQt5.QtWebEngineWidgets', 
              'PyQt5.QtMultimedia', 'PyQt5.QtLocation', 'PyQt5.QtQuick', 'PyQt5.QtSensors'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='POE2PriceAid',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
)
