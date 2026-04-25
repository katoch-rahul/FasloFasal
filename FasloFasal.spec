# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

# Playwright Python package
datas, binaries, hiddenimports = [], [], []
tmp = collect_all('playwright')
datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

# Playwright Chromium browser binaries (dynamic version detection)
playwright_cache = Path.home() / 'AppData' / 'Local' / 'ms-playwright'
if playwright_cache.exists():
    for d in playwright_cache.glob('chromium-*'):
        datas.append((str(d), f'playwright/driver/package/.local-browsers/{d.name}'))
    for d in playwright_cache.glob('chromium_headless_shell-*'):
        datas.append((str(d), f'playwright/driver/package/.local-browsers/{d.name}'))

# App assets and helper modules
datas += [
    ('assets', 'assets'),
    ('config.py', '.'),
    ('approve_claims.py', '.'),
]

hiddenimports += [
    'PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'shiboken6',
]

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FasloFasal',
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
    icon='assets/faslofasal.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FasloFasal',
)
