"""The in-game updater: versions, the download's checksum, unpacking and swapping the build."""

import hashlib
import io
import tarfile
import zipfile

import pytest

from src.services import updater


def test_versions_and_assets():
    assert updater.newer('2.3.0', '2.2.9') and updater.newer('v2.10.0', '2.9.1')
    assert not updater.newer('2.2.3', '2.2.3') and not updater.newer('2.2.0', '2.2.3')
    assert updater.asset_name('2.3.0', 'macos-arm64') == 'BVB-2.3.0-macos-arm64.tar.gz'
    assert updater.asset_name('2.3.0', 'windows-x86_64') == 'BVB-2.3.0-windows-x86_64.zip'


def test_off_outside_a_build(monkeypatch):
    assert updater.build() is None and not updater.enabled()  # from the sources
    monkeypatch.setattr(updater, 'build', lambda: 'steam-linux')
    monkeypatch.setattr(updater, 'installed_by_steam', lambda: False)
    assert updater.enabled()
    monkeypatch.setenv('BVB_NO_UPDATE', '1')
    assert not updater.enabled()


def _tar(path, files):
    with tarfile.open(path, 'w:gz') as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            t.addfile(info, io.BytesIO(data))


def test_verify_unpack_and_swap(tmp_path):
    archive = tmp_path / 'BVB-9.0.0-linux-x86_64.tar.gz'
    _tar(archive, {'BVB-9.0.0-linux-x86_64/BVB': b'new', 'BVB-9.0.0-linux-x86_64/_internal/x': b'1'})
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    updater.verify(archive, f'{digest}  {archive.name}\n')
    with pytest.raises(ValueError):
        updater.verify(archive, f'{"0" * 64}  {archive.name}\n')
    with pytest.raises(ValueError):
        updater.verify(archive, 'nothing here')

    new_root = updater.unpack(archive, tmp_path / 'new')
    assert (new_root / 'BVB').read_bytes() == b'new'

    root = tmp_path / 'games' / 'BVB'
    (root / '_internal').mkdir(parents=True)
    (root / 'BVB').write_bytes(b'old')
    stage = updater.stage_next_to(new_root, root)
    old = updater.swap(root, stage)
    assert (root / 'BVB').read_bytes() == b'new' and (old / 'BVB').read_bytes() == b'old'


def test_a_macos_app_and_a_windows_zip(tmp_path):
    archive = tmp_path / 'mac.tar.gz'
    _tar(archive, {'BVB-9-macos-arm64/BVB.app/Contents/MacOS/BVB': b'x', 'BVB-9-macos-arm64/README.md': b''})
    assert updater.unpack(archive, tmp_path / 'm').name == 'BVB.app'
    zipped = tmp_path / 'win.zip'
    with zipfile.ZipFile(zipped, 'w') as z:
        z.writestr('BVB-9-windows-x86_64/BVB.exe', b'x')
    assert updater.unpack(zipped, tmp_path / 'w').name == 'BVB-9-windows-x86_64'


def test_an_archive_cannot_write_outside(tmp_path):
    archive = tmp_path / 'evil.tar.gz'
    _tar(archive, {'../outside': b'x'})
    with pytest.raises(ValueError):
        updater.unpack(archive, tmp_path / 'in')


def test_windows_script_and_menu_lines(monkeypatch):
    script = updater.windows_script('C:\\g\\BVB.new-bvb', 'C:\\g\\BVB', 'C:\\g\\BVB\\BVB.exe', 1234)
    assert 'PID eq 1234' in script and 'robocopy' in script and 'BVB.exe' in script
    monkeypatch.setattr(updater, 'status', dict(updater.status))
    assert updater.menu_label() is None
    updater.status.update(version='9.0.0', state='available')
    assert updater.menu_label() == ('UPDATE TO 9.0.0', '')
    updater.status.update(state='downloading', progress=0.42)
    assert updater.menu_label() == ('UPDATING', '42%')
    updater.status.update(state='ready')
    assert updater.menu_label()[0] == 'RESTART (9.0.0)'


def test_the_title_shows_the_version_and_the_update(monkeypatch):
    from src import __version__
    from src.ui.layers import title

    monkeypatch.setattr(updater, 'status', {'version': None, 'state': None, 'progress': 0.0, 'error': None})
    assert title.version_line()[0] == f'v{__version__}'
    updater.status.update(version='9.0.0', state='downloading', progress=0.5)
    assert title.version_line()[0] == f'v{__version__}  ·  downloading 9.0.0: 50%'


def test_a_steam_install_does_not_update_itself_a_shortcut_does(monkeypatch, tmp_path):
    from pathlib import Path

    monkeypatch.setattr(updater, 'build', lambda: 'steam-linux')
    monkeypatch.setattr(updater, 'install_root', lambda: Path('/home/deck/.local/share/Steam/steamapps/common/BVB'))
    assert not updater.enabled()
    monkeypatch.setattr(updater, 'install_root', lambda: Path('/home/deck/Games/BVB'))
    monkeypatch.setenv('SteamAppId', '123')  # a non-Steam shortcut may carry ids: it still updates itself
    assert updater.enabled()


def test_a_failed_check_is_shown(monkeypatch):
    from src.ui.layers import title

    monkeypatch.setattr(updater, 'status', {'version': None, 'state': None, 'progress': 0.0, 'error': None})

    def broken(*_args, **_kwargs):
        raise OSError('certificate verify failed')

    monkeypatch.setattr(updater, '_get', broken)
    updater._check()
    assert updater.status['state'] == 'check_failed'
    assert 'no update check' in title.version_line()[0]
