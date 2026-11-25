"""The in-game updater of the downloaded builds (desktop and Steam Linux).

At the title the game asks GitHub, in the background, for the latest release.
When there is a newer version the title menu shows UPDATE: it downloads the
build of this kind (``BUILD``, written into the bundle by the PyInstaller spec:
linux-x86_64, macos-arm64, windows-x86_64 or steam-linux), checks it against the
release's SHA256SUMS.txt, unpacks it next to the installed one and swaps the
two; RESTART then starts the new version. Saves and settings live in ~/.bvb
and are not touched.

It does nothing when the game runs from the sources or from pip (pip install -U
birds-vs-bats updates those), when Steam itself installed it (Steam updates
it), or with BVB_NO_UPDATE set.

The swap: on Linux and macOS the installed folder (or BVB.app) is renamed
aside and the new one takes its place, which works while the game runs; the old
one is removed at the next start. On Windows files in use cannot be replaced: a
small script waits for the game to close, copies the new files over and starts
it again.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path

from src import __version__

REPOSITORY = 'Onheiron/PY-birds-vs-bats'
LATEST = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
OLD_SUFFIX = '.old-bvb'
TIMEOUT = 10

# What the title menu shows: None (nothing to do), or a dict with 'version' and 'state':
# 'available', 'downloading' (with 'progress' 0..1), 'ready', 'failed' (with 'error')
status = {'version': None, 'state': None, 'progress': 0.0, 'error': None}
_lock = threading.Lock()
_checked = False


def build():
    """The kind of build running (the BUILD file in the bundle), or None outside one."""
    if not getattr(sys, 'frozen', False):
        return None
    path = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)) / 'BUILD'
    try:
        return path.read_text(encoding='utf-8').strip() or None
    except OSError:
        return None


def installed_by_steam():
    """Is this the copy Steam installed (in a steamapps library)? Steam updates that one. A build
    added to Steam as a non-Steam game lives anywhere else, and updates itself."""
    try:
        return 'steamapps' in (part.lower() for part in install_root().parts)
    except OSError:
        return False


def enabled():
    if os.environ.get('BVB_NO_UPDATE'):
        return False
    return build() is not None and not installed_by_steam()


def version_tuple(text):
    parts = []
    for piece in str(text).lstrip('vV').split('.'):
        digits = ''.join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def newer(latest, current=__version__):
    return version_tuple(latest) > version_tuple(current)


def asset_name(version, kind):
    return f'BVB-{version}-{kind}.' + ('zip' if kind.startswith('windows') else 'tar.gz')


def install_root():
    """The folder the update replaces: BVB.app on macOS, else the folder of the executable."""
    exe = Path(sys.executable).resolve()
    if sys.platform == 'darwin' and exe.parent.name == 'MacOS' and exe.parents[2].suffix == '.app':
        return exe.parents[2]
    return exe.parent


def _get(url, accept='application/octet-stream'):
    request = urllib.request.Request(url, headers={'User-Agent': 'BVB-updater', 'Accept': accept})
    from src.services import net

    return net.urlopen(request, timeout=TIMEOUT)


# --------------------------------------------------------------------------- checking


def check_in_background():
    """Ask for the latest release once per start (title screen); quiet when offline."""
    global _checked
    if _checked or not enabled():
        return
    _checked = True
    cleanup_old()
    threading.Thread(target=_check, daemon=True).start()


def _check():
    try:
        with _get(LATEST, 'application/vnd.github+json') as response:
            release = json.load(response)
    except Exception as error:
        reason = getattr(error, 'reason', error)
        with _lock:  # shown, dimmed, on the title: an update that never shows has a reason
            status.update(state='check_failed', error=f'{type(error).__name__}: {reason}'[:50])
        return
    version = str(release.get('tag_name', '')).lstrip('vV')
    if not version or not newer(version):
        return
    assets = {a.get('name'): a.get('browser_download_url') for a in release.get('assets', [])}
    name = asset_name(version, build())
    if name not in assets or 'SHA256SUMS.txt' not in assets:
        return
    from src.ui import news

    with _lock:
        status.update(version=version, state='available', progress=0.0, error=None)
        status['notes'] = (
            news.sections(release.get('body') or '').get(version)
            or [line.strip()[2:] for line in (release.get('body') or '').splitlines() if line.strip().startswith('- ')][
                :6
            ]
        )
        status['_urls'] = (assets[name], assets['SHA256SUMS.txt'], name)


# --------------------------------------------------------------------------- updating


def start():
    """UPDATE was chosen: download and install in the background."""
    with _lock:
        if status['state'] not in ('available', 'failed'):
            return
        status.update(state='downloading', progress=0.0, error=None)
        urls = status['_urls']
    threading.Thread(target=_update, args=urls, daemon=True).start()


def _update(url, sums_url, name):
    try:
        with tempfile.TemporaryDirectory(prefix='bvb-update-') as work:
            archive = Path(work) / name
            _download(url, archive)
            with _get(sums_url) as response:
                sums = response.read().decode('utf-8', 'replace')
            verify(archive, sums)
            new_root = unpack(archive, Path(work) / 'new')
            stage = stage_next_to(new_root, install_root())
        with _lock:
            status.update(state='ready', progress=1.0, _staged=str(stage))
    except Exception as error:
        with _lock:
            status.update(state='failed', error=str(error)[:60])


def _download(url, target):
    with _get(url) as response, open(target, 'wb') as out:
        total = int(response.headers.get('Content-Length') or 0)
        done = 0
        while chunk := response.read(256 * 1024):
            out.write(chunk)
            done += len(chunk)
            if total:
                with _lock:
                    status['progress'] = done / total


def verify(archive, sums):
    """The archive's SHA256 must be the one the release lists."""
    digest = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip('*') == Path(archive).name:
            if parts[0].lower() != digest:
                raise ValueError('the download is damaged (checksum)')
            return
    raise ValueError('the release does not list this download')


def _safe_members(names, into):
    root = Path(into).resolve()
    for name in names:
        if not (root / name).resolve().is_relative_to(root):
            raise ValueError(f'unsafe path in the archive: {name}')


def unpack(archive, into):
    """Unpack the archive; returns the folder in it that holds the game (BVB.app, or the
    folder of the BVB executable)."""
    into = Path(into)
    into.mkdir(parents=True, exist_ok=True)
    if str(archive).endswith('.zip'):
        with zipfile.ZipFile(archive) as z:
            _safe_members(z.namelist(), into)
            z.extractall(into)
    else:
        with tarfile.open(archive) as t:
            _safe_members(t.getnames(), into)
            t.extractall(into, filter='tar')  # members checked above too
    for path in sorted(into.rglob('*'), key=lambda p: len(p.parts)):
        if path.name == 'BVB.app' and path.is_dir():
            return path
        if path.name in ('BVB', 'BVB.exe') and path.is_file():
            return path.parent
    raise ValueError('no game in the download')


def stage_next_to(new_root, root):
    """Copy the new build next to the installed one (same disk: the swap is a rename)."""
    stage = root.with_name(root.name + '.new-bvb')
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(new_root, stage, symlinks=True)
    return stage


def swap(root, stage):
    """Put the staged build in place of the installed one (Linux, macOS)."""
    old = root.with_name(root.name + OLD_SUFFIX)
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
    os.replace(root, old)
    os.replace(stage, root)
    return old


def cleanup_old():
    """Remove what the last update left aside."""
    if build() is None:
        return
    root = install_root()
    for leftover in (root.with_name(root.name + OLD_SUFFIX), root.with_name(root.name + '.new-bvb')):
        if leftover.exists():
            shutil.rmtree(leftover, ignore_errors=True)


def windows_script(stage, root, exe, pid):
    """The batch file that finishes an update on Windows once the game has closed."""
    return (
        '@echo off\r\n'
        f':wait\r\ntasklist /FI "PID eq {pid}" | find "{pid}" >nul && (timeout /t 1 /nobreak >nul & goto wait)\r\n'
        f'robocopy "{stage}" "{root}" /MIR /NFL /NDL /NJH /NJS >nul\r\n'
        f'rmdir /S /Q "{stage}"\r\n'
        f'start "" "{exe}"\r\n'
        '(goto) 2>nul & del "%~f0"\r\n'
    )


def restart():
    """Start the new version and leave (RESTART in the title menu)."""
    from src.ui import terminal

    stage = Path(status['_staged'])
    root = install_root()
    args = sys.argv[1:]
    if sys.platform.startswith('win'):
        script = Path(tempfile.gettempdir()) / 'bvb-update.bat'
        script.write_text(windows_script(stage, root, root / 'BVB.exe', os.getpid()), encoding='utf-8')
        subprocess.Popen(['cmd', '/c', str(script)], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        terminal.cleanup()
        os._exit(0)
    swap(root, stage)
    terminal.cleanup()
    if sys.platform == 'darwin' and root.suffix == '.app':
        subprocess.Popen(['open', '-n', str(root), '--args', *args])
        os._exit(0)
    os.execv(str(root / 'BVB'), [str(root / 'BVB'), *args])


def menu_label():
    """The title menu's line for the update, or None."""
    with _lock:
        state, version = status['state'], status['version']
        progress, error = status['progress'], status['error']
    if state == 'available':
        return f'UPDATE TO {version}', ''
    if state == 'downloading':
        return 'UPDATING', f'{int(progress * 100)}%'
    if state == 'ready':
        return f'RESTART ({version})', ''
    if state == 'failed':
        return 'UPDATE FAILED: RETRY', error or ''
    return None


def choose():
    """ENTER on the update line."""
    if status['state'] == 'ready':
        restart()
    else:
        start()
