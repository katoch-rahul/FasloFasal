# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

# Version info
VERSION = "2.1.0"

# Playwright Python package
datas, binaries, hiddenimports = [], [], []
tmp = collect_all('playwright')
datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

# Playwright Chromium browser binaries.
# The cache can hold several revisions across upgrades; bundle ONLY the one the
# installed Playwright actually launches (keeps the build correct and lean).
needed_dirs = None
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as _pw:
        _exe = Path(_pw.chromium.executable_path)
    for _part in _exe.parts:
        if _part.startswith('chromium-'):
            _rev = _part.split('-', 1)[1]
            needed_dirs = {f'chromium-{_rev}', f'chromium_headless_shell-{_rev}'}
            break
except Exception:
    needed_dirs = None  # fall back to bundling every revision found

playwright_cache = Path.home() / 'AppData' / 'Local' / 'ms-playwright'
if playwright_cache.exists():
    _browser_dirs = (list(playwright_cache.glob('chromium-*'))
                     + list(playwright_cache.glob('chromium_headless_shell-*')))
    for d in _browser_dirs:
        if needed_dirs is None or d.name in needed_dirs:
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
