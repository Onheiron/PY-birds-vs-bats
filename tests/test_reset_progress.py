"""tools/reset_progress.py: progress goes to a backup, and can come back."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('reset_progress', ROOT / 'tools' / 'reset_progress.py')
reset_progress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset_progress)


def make_progress(base):
    (base / 'saves').mkdir(parents=True)
    (base / 'saves' / 'slot_1.json').write_text('{}')
    (base / 'profile.json').write_text(json.dumps({'gold': 999}))
    (base / 'discovery.json').write_text('{}')
    (base / 'settings.json').write_text('{}')
    (base / 'recordings').mkdir()


def test_reset_moves_progress_to_a_backup_and_keeps_the_rest(tmp_path):
    make_progress(tmp_path)
    backup, moved = reset_progress.reset(tmp_path, stamp='t1')
    assert {p.name for p in moved} == {'profile.json', 'saves', 'discovery.json'}
    assert not (tmp_path / 'profile.json').exists() and not (tmp_path / 'saves').exists()
    assert (tmp_path / 'settings.json').exists() and (tmp_path / 'recordings').exists()
    assert json.loads((backup / 'profile.json').read_text())['gold'] == 999


def test_keep_birdpedia_and_dry_run(tmp_path):
    make_progress(tmp_path)
    _backup, moved = reset_progress.reset(tmp_path, keep_birdpedia=True, dry_run=True)
    assert 'discovery.json' not in {p.name for p in moved}
    assert (tmp_path / 'profile.json').exists()  # dry run: nothing moved


def test_restore_puts_the_backup_back(tmp_path):
    make_progress(tmp_path)
    backup, _ = reset_progress.reset(tmp_path, stamp='t1')
    (tmp_path / 'profile.json').write_text(json.dumps({'gold': 0}))  # a new start
    reset_progress.restore(tmp_path, backup)
    assert json.loads((tmp_path / 'profile.json').read_text())['gold'] == 999
    assert (tmp_path / 'saves' / 'slot_1.json').exists()
