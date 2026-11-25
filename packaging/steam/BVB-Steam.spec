# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec of the Steam build: a folder with the BVB executable that
opens its own window (src/ui/window.py), full screen, with gamepad support.

Build it inside the Steam Linux Runtime (packaging/steam/build-linux.sh), from
the project root:

    pyinstaller --noconfirm packaging/steam/BVB-Steam.spec

The result is dist/BVB/ (BVB plus _internal/): upload that folder as the Linux
depot, with BVB as the launch executable.
"""

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, '..', '..'))

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
FONTS = ['DejaVuSansMono.ttf', 'DejaVuSansMono-Bold.ttf', 'LICENSE-DejaVu.txt']

# The kind of build, read by the in-game updater (src/services/updater.py; off when Steam installed it)
BUILD_FILE = os.path.join(workpath, 'BUILD')
os.makedirs(workpath, exist_ok=True)
with open(BUILD_FILE, 'w', encoding='utf-8') as f:
    f.write('steam-linux')

a = Analysis(
    [os.path.join(SPECPATH, 'launch.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, name), '.') for name in DATA_FILES]
    + [(os.path.join(ROOT, 'media', 'fonts', name), os.path.join('media', 'fonts')) for name in FONTS]
    + [(os.path.join(ROOT, 'media', 'music'), os.path.join('media', 'music'))]
    + [(os.path.join(ROOT, 'media', 'icons', 'bvb_256.png'), os.path.join('media', 'icons'))]
    + [(BUILD_FILE, '.')],
    # The loop, services and the window are imported lazily by game.py
    hiddenimports=[
        'src.services.music.arrangement',
        'src.services.music.boss',
        'src.services.music.effects',
        'src.services.music.screens',
        'src.services.music.sampler',
        'src.services.music.score',
        'game',
        'src.engine.loop',
        'src.services.audio',
        'src.services.online',
        'src.services.updater',
        'src.ui.window',
        'pygame._sdl2.controller',
    ],
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
    [],
    exclude_binaries=True,
    name='BVB',
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
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='BVB')
