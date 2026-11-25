#!/usr/bin/env python3
"""Reset your progress, to play the meta-progression again from scratch.

    python3 tools/reset_progress.py              # asks first, then resets
    python3 tools/reset_progress.py --dry-run    # only says what it would do
    python3 tools/reset_progress.py --keep-birdpedia
    python3 tools/reset_progress.py --restore ~/.bvb/backups/20261125-101500

What is reset (in ~/.bvb/):
- profile.json: gold, upgrades bought, achievements, lifetime counters;
- saves/: the save slots and the autosave (they carry the old upgrades);
- discovery.json: the Birdpedia (what you have met), unless --keep-birdpedia.

What stays: settings and key bindings, recordings, the bot profile
(bot_profile.json) and its measurements.

Everything reset is first copied to ~/.bvb/backups/<date-time>/: --restore
puts it back.
"""

import argparse
import datetime
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def bvb_dir():
    from src.services.save_manager import SAVE_DIR_NAME

    return Path.home() / SAVE_DIR_NAME


def targets(base, keep_birdpedia):
    names = ['profile.json', 'saves']
    if not keep_birdpedia:
        names.append('discovery.json')
    return [base / name for name in names if (base / name).exists()]


def reset(base, keep_birdpedia=False, dry_run=False, stamp=None):
    """Move the progress files to a backup folder; returns (backup folder, what was moved)."""
    found = targets(base, keep_birdpedia)
    stamp = stamp or datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = base / 'backups' / stamp
    if dry_run or not found:
        return backup, found
    backup.mkdir(parents=True, exist_ok=True)
    for path in found:
        shutil.move(str(path), str(backup / path.name))
    return backup, found


def restore(base, backup):
    """Put a backup's files back (the current ones are moved aside first)."""
    backup = Path(backup).expanduser()
    if not backup.is_dir():
        raise SystemExit(f'No backup folder {backup}')
    replaced, _ = reset(base, stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-before-restore')
    for path in backup.iterdir():
        target = base / path.name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        (shutil.copytree if path.is_dir() else shutil.copy2)(path, target)
    return replaced


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--keep-birdpedia', action='store_true', help='keep what you have discovered')
    parser.add_argument('--dry-run', action='store_true', help='only say what would be reset')
    parser.add_argument('--yes', action='store_true', help='do not ask for confirmation')
    parser.add_argument('--restore', metavar='BACKUP', help='put a backup back')
    args = parser.parse_args()

    base = bvb_dir()
    if args.restore:
        aside = restore(base, args.restore)
        print(f'Restored {args.restore}. What was there before is in {aside}.')
        return

    found = targets(base, args.keep_birdpedia)
    if not found:
        print(f'Nothing to reset in {base}: no progress yet.')
        return
    print('This resets:')
    for path in found:
        print(f'  {path}')
    if args.dry_run:
        return
    answer = 'y' if args.yes else input('Reset your progress? A backup is kept. [y/N] ').strip().lower()
    if answer not in ('y', 'yes', 's', 'si'):
        print('Nothing changed.')
        return
    backup, _ = reset(base, args.keep_birdpedia)
    print(f'Done: you start again with no gold, no upgrades and no achievements.\nBackup: {backup}')
    print(f'To undo:  python3 tools/reset_progress.py --restore {backup}')


if __name__ == '__main__':
    main()
