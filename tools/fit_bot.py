#!/usr/bin/env python3
"""Fit a bot that plays like you, from your recorded games.

    python3 tools/fit_bot.py                      # every recording in ~/.bvb/recordings/
    python3 tools/fit_bot.py FILE.json.gz ...     # these recordings
    python3 tools/fit_bot.py --calibrate          # also tune it by playing it (a few minutes)

Then play with it:

    python3 tools/simulate.py --bot me
    python3 tools/watch.py --bot me               # (or the watch mode you use)

How it works:

1. Every recording is replayed with the code it was played with (its commit,
   checked out in a temporary git worktree) and measured
   (tools/measure_recording.py): keys per second, how high birds are bounced,
   UP presses that do nothing, swaps, gears, powers, the cards and pacts taken
   among those offered. Measurements are kept in ~/.bvb/measurements/.
   Recordings older than the commit field (no ``commit``) are measured with
   the current code unless ``--commit FILE=SHA`` says which code to use.
2. The measures become the bot's skill fields: key_interval from the time
   between two keys of the same hand, bounce_from from how high birds are
   bounced, max_gear from the gear most played, idle_up_rate from the UPs
   that did nothing, and the 'learned' card and pact choices from what was
   taken among what was offered.
3. With --calibrate it plays the bot on the seeds of the recordings and
   tunes reaction_frames, bounce_from, max_gear and idle_up_rate one at a
   time, keeping the values whose game looks most like yours (bounce height,
   keys, swaps, powers per minute, gears).

The profile goes to ~/.bvb/bot_profile.json, with the measures of your games and
of the bot's for comparison; the bot profile 'me' reads it. More recordings make
a better fit: run it again after a few games.
"""

import argparse
import concurrent.futures
import gzip
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))

BVB = Path.home() / '.bvb'
PROFILE_PATH = BVB / 'bot_profile.json'

# Fields tuned by --calibrate: (name, candidate steps around the current value)
TUNED = (
    ('reaction_frames', (-6, +6)),
    ('bounce_from', (-0.08, +0.08)),
    ('max_gear', (-1, +1)),
    ('idle_up_rate', (-0.4, +0.4)),
)
LIMITS = {'reaction_frames': (0, 40), 'bounce_from': (0.05, 0.8), 'max_gear': (2, 10), 'idle_up_rate': (0.0, 3.0)}


# --------------------------------------------------------------------------- measuring


def _git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def _head():
    try:
        return _git('rev-parse', 'HEAD')
    except (OSError, subprocess.CalledProcessError):
        return None


def measure_file(path, commit=None, refresh=False):
    """Measures of one recording (cached in ~/.bvb/measurements/)."""
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        header = json.load(f)
    commit = (commit or header.get('commit') or '').rstrip('+') or None
    if commit is None and header.get('version'):
        commit = f"v{header['version']}"  # a downloaded build (no git): the tag of its version
    cache = BVB / 'measurements' / f'{Path(path).name}.{commit or "current"}.json'
    if cache.exists() and not refresh:
        return json.loads(cache.read_text())
    root, worktree = ROOT, None
    if commit and commit != _head():
        worktree = Path(tempfile.mkdtemp(prefix='bvb-fit-')) / 'code'
        try:
            _git('worktree', 'add', '--detach', str(worktree), commit)
            root = worktree
        except (OSError, subprocess.CalledProcessError):
            print(f'  {Path(path).name}: commit {commit[:7]} not found, measured with the current code')
            worktree = None
    try:
        out = Path(tempfile.mkdtemp(prefix='bvb-fit-')) / 'measure.json'
        subprocess.run(
            [
                sys.executable,
                str(ROOT / 'tools' / 'measure_recording.py'),
                str(path),
                '--root',
                str(root),
                '--out',
                str(out),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(out.read_text())
    finally:
        if worktree is not None:
            subprocess.run(
                ['git', '-C', str(ROOT), 'worktree', 'remove', '--force', str(worktree)], capture_output=True
            )
    result['file'] = Path(path).name
    result['difficulty'] = header.get('difficulty', 1)
    result['profile'] = header.get('profile')
    result['settings'] = header.get('settings', {})
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result))
    return result


# --------------------------------------------------------------------------- what the measures say


def _percentile(values, share):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * share))] if values else None


def style(m):
    """The numbers that describe how a game was played (player's or bot's)."""
    seconds = max(1e-9, m['minutes'] * 60)
    keys = [k for k in m['keys'] if not k[2]]
    moves = [t for t, k, _c in keys if k in ('LEFT', 'RIGHT')]
    ups = [t for t, k, _c in keys if k == 'UP']

    def gap(times):
        gaps = [b - a for a, b in zip(times, times[1:], strict=False) if b - a < 1.0]
        return _percentile(gaps, 0.10)

    rows = [b[1] / m['floor'] for b in m['bounces']]
    gears = m['gear_seconds']
    total = sum(gears.values()) or 1
    ups_total = sum(m['ups'].values()) or 1
    return {
        'minutes': m['minutes'],
        'level': m['level'],
        'keys/s': len(keys) / seconds,
        'moves/s': len(moves) / seconds,
        'UP/s': len(ups) / seconds,
        'key gap (frames)': (gap(moves) or 0.2) * 60,
        'UP gap (frames)': (gap(ups) or 0.2) * 60,
        'bounce height': statistics.median(rows) if rows else 0.5,
        'idle UP share': m['ups']['nothing'] / ups_total,
        'idle UP/s': m['ups']['nothing'] / seconds,
        'swaps/min': len(m['swaps']) / max(1e-9, m['minutes']),
        'gear (mean)': sum(int(g) * s for g, s in gears.items()) / total,
        'gear (mode)': int(max(gears, key=gears.get)) if gears else 5,
        'powers/min': sum(m['powers'].values()) / max(1e-9, m['minutes']),
        'birds lost/min': len(m['deaths']) / max(1e-9, m['minutes']),
    }


def combine(styles, weights):
    """Average of several games' numbers, weighted by their minutes."""
    total = sum(weights) or 1
    return {k: sum(s[k] * w for s, w in zip(styles, weights, strict=True)) / total for k in styles[0]}


def preferences(measures):
    """How much the player likes each card and pact: (taken + 1) / (offered + 2)."""
    offered, taken = Counter(), Counter()
    for m in measures:
        for offer in m['offers']:
            ids = [c[0] for c in offer['cards']]
            for cid in ids:
                offered[cid] += 1
            if offer['kind'] == 'pact' and offer['taken'] is None and not offer['skipped']:
                taken['refuse'] += 1  # closed without a pact: refused
                offered['refuse'] += 1
            elif offer['taken'] in ids:
                taken[offer['taken']] += 1
    return {cid: round((taken[cid] + 1) / (offered[cid] + 2), 3) for cid in offered}


def lane_prefs(measures):
    """How far from the middle lane the player keeps each kind of bird (mean, in lanes)."""
    distances = {}
    for m in measures:
        for sample in m.get('layouts', []):
            lanes = sample[1:]
            middle = (len(lanes) - 1) / 2
            for lane, k in enumerate(lanes):
                if k is not None:
                    distances.setdefault(k, []).append(abs(lane - middle))
    return {k: round(statistics.mean(v), 2) for k, v in distances.items() if len(v) >= 10}


def fit(measures):
    """Skill fields from the measures."""
    weights = [m['minutes'] for m in measures]
    player = combine([style(m) for m in measures], weights)
    return {
        'key_interval': max(3, round((player['key gap (frames)'] + player['UP gap (frames)']) / 2)),
        'two_hands': True,
        'sweep': True,
        'reaction_frames': 15,
        'miss_rate': 0.03,
        'safety_frames': 12,
        'memory': 2.0,
        'bounce_from': round(min(0.8, max(0.05, player['bounce height'])), 2),
        'max_gear': int(player['gear (mode)']),
        'formation': 'player',  # the player's rules (strategy.player_formation_score)
        'lane_prefs': lane_prefs(measures),
        'formation_every': 60,
        'idle_up_rate': round(player['idle UP/s'], 2),
        'card_policy': 'learned',
        'pact_policy': 'learned',
        'card_prefs': preferences(measures),
        'rarity_pull': 0.3,
    }, player


# --------------------------------------------------------------------------- playing the bot


def _play_bot(args):
    """One bot game on a recording's seed, measured like a recording (runs in a worker)."""
    fields, seed, difficulty, profile, minutes = args
    import measure_recording

    from src.sim import runner
    from src.sim.bot import Skill

    fields = dict(fields)
    fields['card_prefs'] = tuple(fields['card_prefs'].items())
    fields['lane_prefs'] = tuple(fields.get('lane_prefs', {}).items())
    config = runner.RunConfig(
        seed=seed,
        difficulty=difficulty,
        skill=Skill(**fields),
        profile=profile,
        max_minutes=minutes,
    )
    return measure_recording.measure({'seed': seed}, play=lambda: runner.run(config))


def play_bot(fields, measures, jobs):
    tasks = [
        (fields, m['seed'], m['difficulty'], m.get('profile'), min(40.0, max(5.0, m['minutes'] * 1.5)))
        for m in measures
    ]
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(_play_bot, tasks))
    return combine([style(r) for r in results], [r['minutes'] for r in results])


# What a bot game must look like: (field, weight); distance on a log scale
MATCH = (
    ('bounce height', 2.0),
    ('keys/s', 1.0),
    ('UP/s', 1.0),
    ('swaps/min', 1.0),
    ('powers/min', 1.0),
    ('gear (mean)', 1.5),
    ('idle UP share', 0.5),
)


def distance(bot, player):
    return sum(w * abs(math.log((bot[k] + 0.05) / (player[k] + 0.05))) for k, w in MATCH)


def calibrate(fields, player, measures, jobs, rounds):
    best = dict(fields)
    best_style = play_bot(best, measures, jobs)
    best_score = distance(best_style, player)
    print(f'  start: distance {best_score:.2f}')
    for _round in range(rounds):
        improved = False
        for name, steps in TUNED:
            for step in steps:
                low, high = LIMITS[name]
                value = min(high, max(low, best[name] + step))
                if isinstance(best[name], int):
                    value = int(round(value))
                if value == best[name]:
                    continue
                trial = dict(best, **{name: round(value, 3) if isinstance(value, float) else value})
                trial_style = play_bot(trial, measures, jobs)
                score = distance(trial_style, player)
                print(f'  {name} = {trial[name]}: distance {score:.2f}')
                if score < best_score:
                    best, best_style, best_score, improved = trial, trial_style, score, True
        if not improved:
            break
    return best, best_style


# --------------------------------------------------------------------------- report


def table(player, bot):
    rows = ['| | you | bot |', '|---|--:|--:|']
    for key in player:
        rows.append(f'| {key} | {player[key]:.2f} | {bot[key]:.2f} |' if bot else f'| {key} | {player[key]:.2f} | |')
    return '\n'.join(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('files', nargs='*', help='recordings (default: all in ~/.bvb/recordings/)')
    parser.add_argument(
        '--commit', action='append', default=[], metavar='FILE=SHA', help='code a recording was played with'
    )
    parser.add_argument('--calibrate', action='store_true', help='tune the bot by playing it on your seeds')
    parser.add_argument('--rounds', type=int, default=2, help='calibration rounds (default 2)')
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--refresh', action='store_true', help='measure the recordings again')
    parser.add_argument('--out', default=str(PROFILE_PATH), help=f'profile file (default {PROFILE_PATH})')
    args = parser.parse_args()

    files = [Path(f) for f in args.files] or sorted((BVB / 'recordings').glob('*.json.gz'))
    if not files:
        raise SystemExit('No recordings: play a few games first (python3 game.py).')
    commits = dict(item.split('=', 1) for item in args.commit)
    if shutil.which('git') is None:
        print('git not found: every recording is measured with the current code')

    print(f'Measuring {len(files)} recording(s)...')
    measures = []
    for path in files:
        m = measure_file(path, commits.get(path.name) or commits.get(str(path)), args.refresh)
        note = '' if m.get('matches') else ' (replay differs from the game: measures are approximate)'
        print(f'  {path.name}: {m["minutes"]:.1f} min, level {m["level"]}{note}')
        measures.append(m)

    fields, player = fit(measures)
    bot = None
    if args.calibrate:
        print('Calibrating (playing the bot on your seeds)...')
        fields, bot = calibrate(fields, player, measures, args.jobs, args.rounds)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {'skill': fields, 'fitted_from': [m['file'] for m in measures], 'you': player, 'bot': bot},
            indent=2,
        )
    )
    print()
    print(table(player, bot))
    print()
    shown = {k: v for k, v in fields.items() if k not in ('card_prefs', 'lane_prefs')}
    print('Skill:', ', '.join(f'{k}={v}' for k, v in shown.items()))
    liked = sorted(fields['card_prefs'].items(), key=lambda kv: -kv[1])
    print('Cards you like most:', ', '.join(f'{k} {v:.2f}' for k, v in liked[:6]))
    print('...and least:', ', '.join(f'{k} {v:.2f}' for k, v in liked[-6:]))
    order = sorted(fields.get('lane_prefs', {}).items(), key=lambda kv: kv[1])
    print('Formation (lanes from the middle):', ', '.join(f'{k} {v:.1f}' for k, v in order))
    print(f'\nSaved {out}: play it with  python3 tools/simulate.py --bot me')


if __name__ == '__main__':
    main()
