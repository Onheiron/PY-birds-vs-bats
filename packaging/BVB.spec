# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: one self-contained BVB executable for the current OS.

Build from the project root:

    pyinstaller --noconfirm packaging/BVB.spec

The result is dist/BVB (dist/BVB.exe on Windows). Configuration files and
themes are bundled; a file with the same name in the directory the game is
started from takes precedence (see src/core/paths.py).
"""

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

DATA_FILES = [
    'config.yml',
    'config_easy.yml',
    'config_hard.yml',
    'config_hell.yml',
    'hardmode.yml',
    'config.sample.yml',
    'config.schema.json',
    'theme.yml',
    'theme_accessible.yml',
]

a = Analysis(
    [os.path.join(ROOT, 'game.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, name), '.') for name in DATA_FILES],
    # The loop and services are imported lazily by game.py
    hiddenimports=['src.engine.loop', 'src.services.audio', 'src.services.firebase_client'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'pytest'],
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
    name='BVB',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
