#!/usr/bin/env python3
"""Measure how a recorded game was played (used by tools/fit_bot.py).

    python3 tools/measure_recording.py RECORDING.json.gz [--root CODE_DIR] [--out FILE.json]

Replays the recording with the game code in ``--root`` (default: this
checkout) and writes what the player did, as JSON:

- keys: game second, key, and whether a card choice was on screen;
- bounces: row, how long the bird had been falling, how many birds were
  falling, the gear;
- falls: how long every fall lasted before it was bounced or lost;
- swaps (gear and falling birds at each), powers fired by bird kind;
- seconds spent in each gear;
- card choices: what was offered, what was taken, rerolls and skips;
- birds lost (cause, world), level reached and minutes played.

A replay only matches the recorded game with the code it was recorded with:
fit_bot.py runs this script inside a checkout of the recording's commit. It
only uses parts of the game that every version has, so old code runs it too.
"""

import argparse
import gzip
import json
import os
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('recording')
    parser.add_argument('--root', default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument('--out')
    args = parser.parse_args()

    root = Path(args.root).resolve()
    sys.path.insert(0, str(root))
    os.chdir(root)
    os.environ['HOME'] = os.environ['USERPROFILE'] = tempfile.mkdtemp(prefix='bvb-measure-')
    with gzip.open(args.recording, 'rt', encoding='utf-8') as f:
        data = json.load(f)
    result = measure(data)
    text = json.dumps(result)
    if args.out:
        Path(args.out).write_text(text)
    else:
        print(text)


def measure(data, play=None):
    """What the player of recording ``data`` did; ``play``: another way to play the
    game while measuring (fit_bot.py plays the bot with it), returning RunStats."""
    import time as time_module

    from src.core import constants, state
    from src.engine import actions, events, input_handler, loop
    from src.entities.bird_types import get_bird_type_by_color
    from src.sim import runner

    out = {
        'seed': data.get('seed'),
        'commit': data.get('commit'),
        'keys': [],
        'bounces': [],
        'falls': [],
        'swaps': [],
        'ups': {'bounce': 0, 'power': 0, 'nothing': 0},
        'powers': {},
        'gear_seconds': {},
        'offers': [],
        'deaths': [],
        'levels': [],
        'layouts': [],  # every 2 s: the kind of bird in each lane (None: empty)
    }
    clock = {'start': None, 'last': None}
    fall_start = {}  # bird -> game second its fall began
    offer = {'current': None}

    def now():
        if clock['start'] is None:
            clock['start'] = state.game.start_time
        return time_module.time() - clock['start']

    def falling():
        return sum(1 for i in range(len(state.birds.colors)) if not state.birds.lost[i] and state.birds.vy[i] == 1)

    counts = {'power': 0}

    def lane_kind(lane):
        for i in range(len(state.birds.colors)):
            if not state.birds.lost[i] and state.birds.random_lanes[i] == lane:
                return kind(i)
        return None

    def kind(i):
        k = get_bird_type_by_color(state.birds.colors[i])
        return str(getattr(k, 'name', k))

    original_input = input_handler.process_input
    original_bounce = actions._bounce_bird_up
    original_step = loop.Session.step

    def process_input(key):
        t = now()
        in_choice = state.choice.active is not None
        out['keys'].append([round(t, 3), key, in_choice])
        if in_choice and offer['current'] is not None:
            if key == 'R':
                offer['current']['rerolls'] += 1
            elif key == 'S':
                offer['current']['skipped'] = True
        elif key == 'SPACE' and state.player.selected_lane is not None:
            a, b = state.player.selected_lane, state.player.lane
            out['swaps'].append([round(t, 3), state.game.speed, falling(), a, b, lane_kind(a), lane_kind(b)])
        if key != 'UP' or in_choice:
            return original_input(key)
        seen = (len(out['bounces']), counts['power'])
        result = original_input(key)
        if len(out['bounces']) > seen[0]:
            out['ups']['bounce'] += 1
        elif counts['power'] > seen[1]:
            out['ups']['power'] += 1
        else:
            out['ups']['nothing'] += 1
        return result

    def bounce(i):
        t = now()
        if state.birds.vy[i] == 1:
            out['bounces'].append(
                [
                    round(t, 3),
                    state.birds.y[i],
                    round(t - fall_start.get(i, t), 3),
                    falling(),
                    state.game.speed,
                    kind(i),
                ]
            )
        return original_bounce(i)

    def step(session):
        t = now()
        if clock['last'] is not None and not state.game.paused and state.choice.active is None:
            gear = str(state.game.speed)
            out['gear_seconds'][gear] = out['gear_seconds'].get(gear, 0) + (t - clock['last'])
        clock['last'] = t
        before = list(state.birds.vy)
        lost_before = list(state.birds.lost)
        active = state.choice.active
        if active is not None and (offer['current'] is None or offer['current']['ref'] is not active):
            offer['current'] = {
                'ref': active,
                'kind': active.get('kind'),
                'cards': [[c.get('id'), c.get('kind'), c.get('rarity')] for c in active.get('cards', [])],
                'taken': None,
                'rerolls': 0,
                'skipped': False,
                'level': state.game.level,
            }
            out['offers'].append(offer['current'])
        result = original_step(session)
        for i, vy in enumerate(state.birds.vy):
            if state.birds.lost[i]:
                if not lost_before[i] and i in fall_start:
                    out['falls'].append([round(t - fall_start.pop(i), 3), 'lost'])
                continue
            if vy == 1 and before[i] != 1:
                fall_start[i] = t
            elif vy != 1 and before[i] == 1 and i in fall_start:
                out['falls'].append([round(t - fall_start.pop(i), 3), 'bounced'])
        if (
            not state.game.paused
            and state.choice.active is None
            and (not out['layouts'] or t - out['layouts'][-1][0] >= 2.0)
        ):
            lanes = len(constants.layout.lane_positions)
            out['layouts'].append([round(t, 1)] + [lane_kind(lane) for lane in range(lanes)])
        if not out['levels'] or out['levels'][-1][1] != state.game.level:
            out['levels'].append([round(t, 1), state.game.level])
        return result

    def on_pick(card=None, pact=None, **_):
        picked = card or pact
        if offer['current'] is not None and picked is not None:
            offer['current']['taken'] = picked.get('id')

    def on_power(power=None, lane=None, **_):
        if lane is None:
            return  # a power-up picked up, not a bird's power
        name = str(power)
        out['powers'][name] = out['powers'].get(name, 0) + 1
        counts['power'] += 1

    def on_lost(**fields):
        out['deaths'].append([round(now(), 1), fields.get('cause'), state.game.level_group, state.game.level])

    input_handler.process_input = process_input
    actions._bounce_bird_up = bounce
    loop.Session.step = step
    handlers = [('card_picked', on_pick), ('pact_made', on_pick), ('power_used', on_power), ('bird_lost', on_lost)]
    for name, handler in handlers:
        events.on(name, handler)
    try:
        stats = play() if play is not None else runner.replay(data)
    finally:
        input_handler.process_input = original_input
        actions._bounce_bird_up = original_bounce
        loop.Session.step = original_step
        for name, handler in handlers:
            if hasattr(events, 'off'):
                events.off(name, handler)
    for item in out['offers']:
        item.pop('ref', None)
    summary = stats.summary()
    recorded = data.get('result', {})
    out['level'] = summary['level']
    out['score'] = summary['score']
    out['minutes'] = summary['minutes']
    out['matches'] = (
        bool(recorded) and recorded.get('level') == summary['level'] and recorded.get('score') == summary['score']
    )
    out['floor'] = constants.layout.starting_line
    return out


if __name__ == '__main__':
    main()
