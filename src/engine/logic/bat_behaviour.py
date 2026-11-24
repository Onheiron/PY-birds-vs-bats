"""How bats move: come in, settle, pick a spot, hold it, move on, fly out, come back.

Every bat (wave bats, logic/waves.py, and those a boss summons, which start
from where they appear) follows a plan (``bat['plan']``):

1. **enter**: it comes in from the top straight above the spot it picked and
   goes down to its cruising row: deeper the higher its tier
   (``behaviour.cruise_by_tier``, as a share of the screen from the top).
2. **hold**: it stays there ``hold`` seconds (a spellcaster until it has cast
   ``casts`` spells, at most ``cast_hold_max`` s).
3. **move**: it picks a new spot a few lanes away (``move_lanes``) and flies
   there; after ``stops`` spots it leaves.
4. **leave** / **out**: it flies out from the top and stays out ``out``
   seconds, then comes back in (enter) with the HP it has left. A bat that
   cannot move sideways for ``stuck_time`` seconds leaves too.

Spots are chosen from what lasts, not from where birds happen to be this
instant (a bat takes seconds to get anywhere): which bird is in a lane, how
strong it is, whether it has a power, how many synergy partners it has,
which lanes are full or empty.

- plain: lanes with birds, the stronger the likelier.
- armored: the strongest bird, to stand in its way.
- diver: the birds that score most (it dives on them).
- spellcaster: by the spell it is about to cast: silence over birds with a
  power (more with synergy partners), exile over the strongest bird,
  repugnant wind over the fullest group of lanes. It picks the spell when it
  picks the spot; the second cast is whatever it knows.
- healer: over the most wounded bat, keeping higher than the others.
- bomber and plague: over the fullest group of lanes.
- necromancer: over empty lanes (where it raises zombies), keeping high.

Elites hold and stay out for less (``elite_pace``). Values: bat_enemy.waves.behaviour.
"""

import random

from src.core import constants, state
from src.engine import clock, enemy_stats, stats, synergies
from src.engine.powers import POWERS
from src.entities.bird_types import get_bird_type_by_color
from src.entities.sprites import ZOMBIE

OUT_ROW = -8  # where a bat waits while out (nothing of it shows)


def _cfg(name, default):
    behaviour = getattr(getattr(constants.bat_enemy, 'waves', None), 'behaviour', None)
    return getattr(behaviour, name, default)


def _kind_cfg(bat, name, default):
    kinds = enemy_stats._as_dict(_cfg('kinds', None))
    entry = enemy_stats._as_dict(kinds.get(bat.get('kind') or 'plain'))
    return entry.get(name, _cfg(name, default))


def _between(pair, default):
    low, high = list(pair or default)
    return random.uniform(float(low), float(high))


def _pace(bat):
    return float(_cfg('elite_pace', 0.6)) if bat.get('elite') else 1.0


# --------------------------------------------------------------------------- what a lane is worth


def _birds():
    """Your living birds (zombies and dormant birds left out)."""
    birds = state.birds
    return [
        i
        for i in range(len(birds.colors))
        if not birds.lost[i] and birds.colors[i] != ZOMBIE and birds.y[i] < constants.layout.height
    ]


def _strength(i):
    return max(1.0, stats.bird(i, 'damage'))


def _power_value(i):
    """A bird with a power, worth more with synergy partners next to it."""
    if get_bird_type_by_color(state.birds.colors[i]) not in POWERS:
        return 0.0
    return 1.0 + len(synergies.neighbours(i))


def _per_lane(value):
    lanes = {}
    for i in _birds():
        lane = state.birds.random_lanes[i]
        lanes[lane] = lanes.get(lane, 0.0) + value(i)
    return lanes


def _cluster():
    """Lanes by the birds in them and in the lanes beside them."""
    full = {state.birds.random_lanes[i] for i in _birds()}
    n = constants.layout.num_lanes
    return {lane: sum(1 for x in (lane - 1, lane, lane + 1) if x in full) for lane in range(n)}


def _empty_lanes():
    full = {state.birds.random_lanes[i] for i in _birds()}
    return {lane: 1.0 for lane in range(constants.layout.num_lanes) if lane not in full}


def _wounded(bat):
    """Lanes under the other bats, by how hurt they are."""
    lanes = {}
    for other in state.enemies.bats:
        if other is bat or other['y_pos'] < 0:
            continue
        missing = 1 - other['hp'] / max(1, other.get('max_hp', other['hp']))
        if missing > 0:
            lane = _lane_of_x(other['x_pos'] + enemy_stats.bat_width(other) // 2)
            lanes[lane] = max(lanes.get(lane, 0.0), missing)
    return lanes


def _spell_lanes(spell):
    if spell == 'silence':
        return _per_lane(_power_value)
    if spell == 'exile':
        return _per_lane(lambda i: _strength(i) ** 2)
    return _cluster()  # repugnant wind


def lane_weights(bat):
    """Lane -> how much this bat wants to be over it."""
    kind = bat.get('kind')
    if kind == 'armored':
        weights = _per_lane(lambda i: _strength(i) ** 2)
    elif kind == 'diver':
        weights = _per_lane(lambda i: stats.bird(i, 'score_mult'))
    elif kind == 'spellcaster':
        known = bat.get('known_spells') or ['silence']
        bat['next_spell'] = random.choice(known)
        weights = _spell_lanes(bat['next_spell'])
        # Rather in the middle, where its spell reaches most lanes
        middle = (constants.layout.num_lanes - 1) / 2
        weights = {lane: w * (1.5 - abs(lane - middle) / max(1, middle) * 0.5) for lane, w in weights.items()}
    elif kind == 'healer':
        weights = _wounded(bat) or _per_lane(lambda i: 1.0)
    elif kind in ('bomber', 'plague'):
        weights = _cluster()
    elif kind == 'necromancer':
        weights = _empty_lanes() or _per_lane(lambda i: 1.0 / _strength(i))
    else:
        weights = _per_lane(_strength)
    return {lane: w for lane, w in weights.items() if w > 0}


# --------------------------------------------------------------------------- spots


def _lane_of_x(x):
    positions = constants.layout.lane_positions
    return min(range(len(positions)), key=lambda lane: abs(positions[lane] - x))


def _x_over(bat, lane):
    width = enemy_stats.bat_width(bat)
    x = constants.layout.lane_positions[lane] - width // 2
    return max(0, min(constants.layout.width - width, x))


def _taken(bat, x):
    """Would the bat at column ``x`` overlap another bat (or the spot one is heading to)?"""
    width = enemy_stats.bat_width(bat)
    for other in state.enemies.bats:
        if other is bat:
            continue
        other_width = enemy_stats.bat_width(other)
        spots = [other['x_pos']] if other['y_pos'] >= 0 else []
        plan = other.get('plan')
        if plan and plan.get('target_x') is not None:
            spots.append(plan['target_x'])
        for left in spots:
            if not (x + width < left or x > left + other_width):
                return True
    return False


def pick_spot(bat, near=None):
    """Column the bat goes to: a wanted lane (within ``move_lanes`` of ``near``), free of other bats."""
    weights = lane_weights(bat)
    if near is not None:
        reach = int(_kind_cfg(bat, 'move_lanes', 3))
        here = _lane_of_x(near + enemy_stats.bat_width(bat) // 2)
        weights = {lane: w for lane, w in weights.items() if 0 < abs(lane - here) <= reach} or weights
    lanes = list(weights) or list(range(constants.layout.num_lanes))
    random.shuffle(lanes)
    lanes.sort(key=lambda lane: -weights.get(lane, 1.0) * random.uniform(0.6, 1.0))
    for lane in lanes:
        x = _x_over(bat, lane)
        if not _taken(bat, x):
            return x
    from src.engine.logic.waves import free_column

    return free_column(bat)


def _cruise_row(bat):
    table = enemy_stats._as_dict(_cfg('cruise_by_tier', None))
    tier = bat.get('tier', 1)
    low, high = list(table.get(tier, table.get(str(tier))) or (0.2, 0.4))
    shift = float(_kind_cfg(bat, 'cruise_shift', 0.0))
    screen = constants.layout.starting_line
    row = int(screen * (random.uniform(float(low), float(high)) + shift))
    return max(2, min(screen - 4, row))


# --------------------------------------------------------------------------- the plan


def start(bat):
    """(Re)start the plan: in from the top, straight above the spot it picked."""
    from src.engine.logic.spawning import entry_row

    bat['x_pos'] = pick_spot(bat)
    bat['y_pos'] = entry_row(bat.get('kind'))
    bat['direction'] = random.choice([-1, 1])
    if 'diver' not in enemy_stats.bat_kinds(bat):
        bat['target_y'] = _cruise_row(bat)  # divers keep the high row they dive from
    else:
        bat['diver_state'] = 'flying'
        bat['dive_start_y'] = None
    bat['casts_done'] = 0
    bat.pop('blocked_since', None)
    bat['plan'] = {
        'phase': 'enter',
        'target_x': bat['x_pos'],
        'stops': random.randint(*[int(v) for v in _kind_cfg(bat, 'stops', [3, 5])]),
        'until': 0,
    }


def busy(bat):
    """Out of the fight: flying out or waiting off screen (no abilities, no descent)."""
    plan = bat.get('plan')
    return bool(plan) and plan['phase'] in ('leave', 'out')


def update(bat):
    """One tick of a bat's plan (its sideways moves and its comings and goings)."""
    plan = bat.get('plan')
    if plan is None:
        if bat['y_pos'] >= 0:
            # Already on screen (summoned by a boss): it starts from where it is
            bat['plan'] = {
                'phase': 'move',
                'target_x': pick_spot(bat, near=bat['x_pos']),
                'stops': random.randint(*[int(v) for v in _kind_cfg(bat, 'stops', [3, 5])]),
                'until': 0,
            }
        else:
            start(bat)
        plan = bat['plan']
    now = clock.now()
    phase = plan['phase']
    if phase == 'out':
        if now >= plan['until']:
            start(bat)
        return
    if phase == 'leave':
        if state.game.frame_count % 2 == 0:
            bat['y_pos'] -= 1
        if bat['y_pos'] <= OUT_ROW + 2:
            bat['y_pos'] = OUT_ROW
            plan['phase'] = 'out'
            plan['until'] = now + _between(_kind_cfg(bat, 'out', [1.0, 3.0]), (1, 3)) * _pace(bat)
        return
    if bat.get('diver_state', 'flying') != 'flying':
        return  # diving, stunned or climbing back: the diver's own moves
    if bat['x_pos'] != plan['target_x']:
        _fly_to(bat, plan['target_x'])
        return
    settled = bat['y_pos'] >= bat['target_y'] or 'diver' in enemy_stats.bat_kinds(bat)
    if phase in ('enter', 'move'):
        if not settled:
            from src.engine.bat_ai import can_descend

            if not can_descend(bat):
                _blocked(bat)  # a bird below would end up above it: out from the top if it lasts
            else:
                bat.pop('blocked_since', None)
        if settled:
            plan['phase'] = 'hold'
            plan['until'] = now + _between(_kind_cfg(bat, 'hold', [1.0, 2.0]), (1, 2)) * _pace(bat)
            plan['hold_end'] = now + float(_cfg('cast_hold_max', 10.0))
        return
    # hold
    if bat.get('kind') == 'spellcaster':
        casts = int(_kind_cfg(bat, 'casts', 2))
        if bat.get('spell_state') == 'casting' or (bat.get('casts_done', 0) < casts and now < plan['hold_end']):
            return
        leave(bat)  # its spells cast: out, and back in somewhere else
        return
    if now < plan['until']:
        return
    plan['stops'] -= 1
    if plan['stops'] <= 0:
        leave(bat)
        return
    plan['phase'] = 'move'
    plan['target_x'] = pick_spot(bat, near=bat['x_pos'])


def leave(bat):
    bat['plan']['phase'] = 'leave'
    bat['plan']['target_x'] = None


def _fly_to(bat, target_x):
    """A step towards ``target_x`` at the bat's speed; boxed in too long, it leaves."""
    from src.engine.bat_ai import _check_bat_can_move

    speed = enemy_stats.get(bat, 'speed')
    interval = 3 if speed == 1 else max(1, int(3 / speed + 1e-9))
    if state.game.frame_count % interval:
        return
    step = max(1, int(enemy_stats.get(bat, 'move_step')))
    direction = 1 if target_x > bat['x_pos'] else -1
    bat['direction'] = direction
    next_x = bat['x_pos'] + direction * min(step, abs(target_x - bat['x_pos']))
    if _check_bat_can_move(bat, next_x):
        bat['x_pos'] = next_x
        bat.pop('blocked_since', None)
        return
    _blocked(bat)


def _blocked(bat):
    """It cannot go on (other bats, or a bird it must not pass under): it leaves if this lasts."""
    since = bat.setdefault('blocked_since', clock.now())
    if clock.now() - since >= float(getattr(getattr(constants.bat_enemy, 'waves', None), 'stuck_time', 1.5)):
        bat.pop('blocked_since', None)
        leave(bat)
