#!/usr/bin/env python3
"""Verify the games players sent and keep the leaderboards (run by .github/workflows/online.yml).

    python3 tools/verify_runs.py verify          # every pending submission
    python3 tools/verify_runs.py wipe --yes       # delete every document (a fresh start)

Needs firebase-admin and the service account of the Firebase project in the
environment variable FIREBASE_SERVICE_ACCOUNT (its JSON): the GitHub secret.
It never runs in the game.

A submission (src/services/online.py) is a recording of a whole game. It is
replayed with the code of the version it was played with (the git tag
v<version>, checked out in a worktree): only when the replay ends with the
level and score the player sent does the game enter the leaderboards
``boards/<period>-<difficulty>`` (period all, month-YYYY-MM, week-YYYY-Www),
each keeping a player's best run, the best BOARD_SIZE in all. The submission
is then marked verified or rejected (with the reason) and its parts deleted.
"""

import argparse
import datetime
import gzip
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARD_SIZE = 100
MIN_VERSION = (2, 3, 0)  # the first version that sends games
DIFFICULTIES = ('peaceful', 'adventure', 'survival', 'legendary')


def version_tuple(text):
    return tuple(int(''.join(c for c in p if c.isdigit()) or 0) for p in str(text).split('.'))


def client():
    import firebase_admin
    from firebase_admin import credentials, firestore

    info = json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT'])
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(info))
    return firestore.client()


def boards_of(created, difficulty):
    when = created.astimezone(datetime.timezone.utc)
    year, week, _day = when.isocalendar()
    name = DIFFICULTIES[max(0, min(3, int(difficulty)))]
    return [f'all-{name}', f'month-{when.year}-{when.month:02d}-{name}', f'week-{year}-W{week:02d}-{name}']


def worktree(version, cache={}):  # noqa: B006 (a cache on purpose)
    """A checkout of the tag v<version> (made once per run)."""
    if version not in cache:
        path = Path(tempfile.mkdtemp(prefix=f'bvb-{version}-'))
        subprocess.run(['git', '-C', str(ROOT), 'worktree', 'add', '--detach', str(path), f'v{version}'], check=True)
        cache[version] = path
    return cache[version]


def replay(version, raw):
    """(level, score) the game reaches when its recording is replayed with its version's code."""
    tree = worktree(version)
    with tempfile.NamedTemporaryFile(suffix='.json.gz', delete=False) as f:
        f.write(raw)
        path = f.name
    script = (
        'import json, os, sys, tempfile\n'
        "os.environ['HOME'] = os.environ['USERPROFILE'] = tempfile.mkdtemp()\n"
        "os.environ['BVB_OFFLINE'] = '1'\n"
        "os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')\n"
        'sys.path.insert(0, os.getcwd())\n'
        'from src.core import state\n'
        'from src.engine import recorder\n'
        'from src.sim import runner\n'
        f'data = recorder.load({path!r})\n'
        # The configuration is the version's own, never the one the recording carries
        "data['config'] = None\n"
        'runner.replay(data)\n'
        "print(json.dumps({'level': state.game.level, 'score': int(state.game.score)}))\n"
    )
    done = subprocess.run(
        [sys.executable, '-c', script], cwd=tree, capture_output=True, text=True, timeout=600, check=False
    )
    os.unlink(path)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip().splitlines()[-1] if done.stderr.strip() else 'replay failed')
    result = json.loads(done.stdout.strip().splitlines()[-1])
    return result['level'], result['score']


def check(doc, raw):
    """None when the submission is a true game, else why not."""
    version = doc.get('version', '')
    if version_tuple(version) < MIN_VERSION:
        return f'version {version} does not send games'
    try:
        data = json.loads(gzip.decompress(raw))
    except (OSError, ValueError):
        return 'unreadable recording'
    if data.get('version') != version or int(data.get('difficulty', -1)) != int(doc.get('difficulty', -2)):
        return 'the recording does not match the submission'
    try:
        level, score = replay(version, raw)
    except Exception as error:
        return f'replay failed: {error}'[:200]
    if (level, score) != (int(doc.get('level', -1)), int(doc.get('score', -1))):
        return f'replay ends at level {level} with {score}, not {doc.get("level")} / {doc.get("score")}'
    return None


def add_to_board(db, board, entry):
    ref = db.collection('boards').document(board)
    snap = ref.get()
    entries = (snap.to_dict() or {}).get('entries', []) if snap.exists else []
    best = {e['uid']: e for e in entries}
    old = best.get(entry['uid'])
    if old is None or entry['score'] > old['score']:
        best[entry['uid']] = entry
    ranked = sorted(best.values(), key=lambda e: (-e['score'], e['date']))[:BOARD_SIZE]
    ref.set({'entries': ranked, 'updated': datetime.datetime.now(datetime.timezone.utc)})


def verify(db):
    from google.cloud.firestore_v1.base_query import FieldFilter

    pending = list(db.collection('submissions').where(filter=FieldFilter('status', '==', 'pending')).stream())
    print(f'{len(pending)} submission(s) to verify')
    for snap in pending:
        doc = snap.to_dict()
        parts = [db.collection('parts').document(f'{snap.id}-{n}').get() for n in range(int(doc.get('parts', 0)))]
        if not all(p.exists for p in parts):
            age = datetime.datetime.now(datetime.timezone.utc) - snap.create_time
            if age > datetime.timedelta(hours=1):
                snap.reference.update({'status': 'rejected', 'reason': 'incomplete upload'})
            continue
        raw = b''.join(p.to_dict()['data'] for p in parts)
        reason = check(doc, raw)
        if reason:
            snap.reference.update({'status': 'rejected', 'reason': reason})
            print(f'{snap.id}: rejected, {reason}')
        else:
            player = db.collection('players').document(doc['uid']).get()
            name = (player.to_dict() or {}).get('name') if player.exists else None
            entry = {
                'uid': doc['uid'],
                'name': (name or doc.get('name') or 'Anonymous')[:20],
                'score': int(doc['score']),
                'level': int(doc['level']),
                'version': doc['version'],
                'date': snap.create_time.strftime('%Y-%m-%d'),
            }
            for board in boards_of(snap.create_time, doc['difficulty']):
                add_to_board(db, board, entry)
            snap.reference.update({'status': 'verified'})
            print(f'{snap.id}: verified, {entry["score"]} at level {entry["level"]}')
        for p in parts:
            p.reference.delete()


def wipe(db):
    """Delete every document of every collection, subcollections included (a fresh start)."""
    for collection in db.collections():
        print(f'deleting {collection.id}...', flush=True)
        db.recursive_delete(collection)  # in batches (BulkWriter): no long reads
    print('done')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=('verify', 'wipe'))
    parser.add_argument('--yes', action='store_true', help='needed by wipe')
    args = parser.parse_args()
    db = client()
    if args.action == 'wipe':
        if not args.yes:
            raise SystemExit('wipe deletes everything: add --yes')
        wipe(db)
    else:
        verify(db)


if __name__ == '__main__':
    main()
