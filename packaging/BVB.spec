# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec of the desktop builds: the game in a window of its own (src/ui/window.py).

Build from the project root:

    pyinstaller --noconfirm packaging/BVB.spec

The result:
- macOS: dist/BVB.app, an app opened with a double click;
- Windows: dist/BVB/BVB.exe (with _internal/), no console window;
- Linux: dist/BVB/BVB (with _internal/).

It opens a window (F11 for full screen); ``--terminal`` plays in the terminal
instead (packaging/desktop/launch.py). Configuration files and themes are
bundled; a file with the same name in the directory the game is started from
takes precedence (see src/core/paths.py).
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
sys.path.insert(0, ROOT)
from src import __version__  # noqa: E402

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

# The kind of build, read by the in-game updater (src/services/updater.py) to pick its download

import platform  # noqa: E402

KIND = {
    'darwin': 'macos-arm64' if platform.machine() == 'arm64' else 'macos-x86_64',
    'win32': 'windows-x86_64',
}.get(sys.platform, 'linux-x86_64')
BUILD_FILE = os.path.join(workpath, 'BUILD')
os.makedirs(workpath, exist_ok=True)
with open(BUILD_FILE, 'w', encoding='utf-8') as f:
    f.write(KIND)

a = Analysis(
    [os.path.join(SPECPATH, 'desktop', 'launch.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, name), '.') for name in DATA_FILES]
    + [(os.path.join(ROOT, 'media', 'fonts', name), os.path.join('media', 'fonts')) for name in FONTS]
    + [(os.path.join(ROOT, 'media', 'music'), os.path.join('media', 'music'))]
    + [(os.path.join(ROOT, 'media', 'icons', 'bvb_256.png'), os.path.join('media', 'icons'))]
    + [(BUILD_FILE, '.')],
    # The loop, services and the window are imported lazily by game.py
    hiddenimports=[
        'game',
        'src.engine.loop',
        'src.services.audio',
        'src.services.online',
        'src.services.updater',
        'src.services.music.arrangement',
        'src.services.music.boss',
        'src.services.music.effects',
        'src.services.music.screens',
        'src.services.music.sampler',
        'src.services.music.score',
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
    icon=os.path.join(ROOT, 'media', 'icons', 'bvb.ico'),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='BVB')

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='BVB.app',
        icon=os.path.join(ROOT, 'media', 'icons', 'bvb.icns'),
        bundle_identifier='io.github.onheiron.bvb',
        version=__version__,
        info_plist={
            'CFBundleName': 'BVB',
            'CFBundleDisplayName': 'BVB - Birds vs Bats',
            'CFBundleShortVersionString': __version__,
            'NSHighResolutionCapable': True,
            'LSApplicationCategoryType': 'public.app-category.arcade-games',
        },
    )
