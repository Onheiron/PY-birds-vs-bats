"""Strategies for the bot: what it is trying to do, beyond keeping birds alive.

Every strategy is a set of Skill fields (src/sim/bot.py), so they can be
mixed and changed from the command line (``--bot-set formation=red_battery``)
or compared with ``tools/simulate.py --strategies default,brake,few_birds``.

- **Brake** (``max_gear``, ``brake_when_falling``): a swap costs momentum, so
  swapping two birds is a way to drop a gear when the game gets too fast or
  too many birds fall at once. Slower means less damage, score and distance.
- **Formation** (``formation``): swap birds into an arrangement where their
  synergies work: Reds side by side (each rising neighbour Red / Purple /
  Patchwork adds to a Red's shot), Blues next to Yellows (a Yellow's chain
  cures scared Blues beside the birds it bounces), Whites in the middle
  (they relay the powers of the birds within two lanes).
- **Few birds** (``keep_birds``): look after at most N birds and let the
  least valuable ones fall: fewer birds to juggle, less score and fewer kills.
- **Favourites** (``favorites``, ``cull_others``): protect some kinds first,
  take their bird cards and, with cull_others, let the other birds go to
  free lanes for new eggs (never while lives are low: ``min_lives_to_cull``).
- **Adaptive cards** (``card_policy=adaptive``, ``pact_policy=adaptive``):
  value every card by what the flock needs now (see card_value).
"""

from src.core import constants, state
from src.engine import stats
from src.engine.enemy_stats import RARITIES
from src.engine.progression import calculate_gear_threshold, compute_gear_from_momentum
from src.entities.bird_types import get_bird_type_by_color

# Named strategies: Skill fields to change from the base profile
STRATEGIES = {
    'default': {},
    'brake': {'max_gear': 7},
    'brake_hard': {'max_gear': 5, 'brake_when_falling': 4},
    'red_battery': {'formation': 'red_battery'},
    'yellow_guard': {'formation': 'yellow_guard'},
    'white_center': {'formation': 'white_center'},
    'yellow_sides': {'formation': 'yellow_sides'},
    'auto_formation': {'formation': 'auto'},
    'few_birds': {'keep_birds': 5},
    'favorites': {'favorites': ('RED', 'PURPLE', 'WHITE', 'STEALTH'), 'cull_others': True},
    'adaptive': {'card_policy': 'adaptive', 'pact_policy': 'adaptive'},
    # A build player: a few stats stacked from rare cards up, rerolls and timed cards otherwise
    'builder': {'card_policy': 'builder'},
    # No build at all: whatever card comes (the weak end the balance is measured against)
    'no_build': {'card_policy': 'random'},
    'cautious': {
        'max_gear': 7,
        'keep_birds': 7,
        'card_policy': 'adaptive',
        'pact_policy': 'adaptive',
    },
}

_RANK = {name: i for i, name in enumerate(RARITIES)}
_RARITY_VALUE = {'common': 1, 'uncommon': 2, 'rare': 3, 'epic': 5, 'legendary': 8, 'mythical': 12}
_SHOOTERS = {'RED', 'PURPLE', 'PATCHWORK'}
_CHAIN = {'YELLOW', 'PATCHWORK'}


def kind(i):
    return get_bird_type_by_color(state.birds.colors[i])


def alive():
    return [i for i in range(constants.layout.num_balls) if not state.birds.lost[i]]


# ---------------------------------------------------------------------- birds to keep


def bird_value(i, skill):
    """How much the bot wants to keep bird ``i``: favourites, then grade and rarity."""
    bird_type = kind(i)
    value = state.birds.per_bird_xp[i] ** 0.5 + 10 * stats.bird(i, 'prestige')
    if bird_type in skill.favorites:
        value += 10_000
    return value


def abandoned(skill):
    """Birds the bot lets fall on purpose.

    Every lost bird costs a life, so it lets go at most as many birds as it
    has lives above ``min_lives_to_cull``, least valuable first.
    """
    living = alive()
    budget = state.game.lives - skill.min_lives_to_cull
    if budget <= 0:
        return set()
    candidates = []
    if skill.cull_others and skill.favorites:
        candidates += [i for i in living if kind(i) not in skill.favorites]
    keep = sorted((i for i in living if i not in candidates), key=lambda i: bird_value(i, skill), reverse=True)
    candidates += keep[skill.keep_birds :]
    candidates.sort(key=lambda i: bird_value(i, skill))
    out = set(candidates[:budget])
    # Never let the very last bird go
    return out if len(living) - len(out) >= 1 else set()


# ---------------------------------------------------------------------- swaps


def swap_cost():
    gear = compute_gear_from_momentum(state.game.momentum)
    return (calculate_gear_threshold(gear + 1) - calculate_gear_threshold(gear)) * 0.2


def can_swap():
    return state.game.momentum >= swap_cost() and state.enemies.boss is None


def _lane_kinds():
    """lane -> bird type of the living bird whose home it is (None if empty)."""
    out = {}
    for i in range(constants.layout.num_balls):
        out[state.birds.home_lanes[i]] = None if state.birds.lost[i] else kind(i)
    return out


def formation_score(lanes, formation, prefs=None):
    """How well an arrangement (lane -> bird type) suits ``formation``.

    'learned': each kind as far from the middle lane as the player keeps it
    (``prefs``: kind -> lanes from the middle, see tools/fit_bot.py).
    """
    n = constants.layout.num_lanes
    if formation == 'player':
        return player_formation_score(lanes, prefs)
    if formation == 'learned':
        target = learned_layout(lanes, prefs)
        return sum(1.0 for lane, k in lanes.items() if k is not None and target.get(lane) == k)
    score = 0.0
    for lane in range(n):
        here = lanes.get(lane)
        if here is None:
            continue
        for other in (lane - 1, lane + 1):
            there = lanes.get(other)
            if there is None:
                continue
            auto = formation == 'auto'
            battery = (formation == 'red_battery' or auto) and here in _SHOOTERS and there in _SHOOTERS
            guard = (formation == 'yellow_guard' or auto) and here == 'BLUE' and there in _CHAIN
            if battery or guard:
                score += 1
        # Yellows in pairs at the edges bounce each other: the cursor can stay in the middle
        if formation in ('yellow_sides', 'auto') and here in _CHAIN and (lane <= 1 or lane >= n - 2):
            score += 1 + sum(0.5 for other in (lane - 1, lane + 1) if lanes.get(other) in _CHAIN)
        if formation in ('white_center', 'auto') and here == 'WHITE':
            score += 3 - min(3, abs(lane - n // 2))
        if formation in ('white_center', 'auto') and here in ('YELLOW', 'RED', 'BLUE'):
            whites = [lane2 for lane2, k in lanes.items() if k == 'WHITE']
            score += 0.5 * sum(1 for w in whites if abs(w - lane) <= 2)
    return score


# Kinds whose afflictions ride on the shots of the Reds next to them
_SHOT_EFFECTS = ('POISON', 'FROSTY', 'BERSERK')


def player_formation_score(lanes, prefs=None):
    """The player's formation rules (the 'me' bot), for any flock:

    1. faster birds nearer the middle: the cursor travels less, on average, to save them;
    2. Reds side by side: a wall of shots (a Patchwork counts, at the sides of the block);
    3. Poison, Frosty, Berserk right beside the Red block: the outer shots carry their
       affliction and the middle ones keep their full damage;
    4. the White third from an edge: its power also bounces the two lanes beyond it;
    5. at the edges the birds that need the cursor least: Clockwork (it bounces by
       itself) and Yellows in pairs (they bounce each other);
    6. ties broken by where the player usually keeps each kind (``prefs``).
    """
    from src.entities.bird_types import get_default_speed

    n = constants.layout.num_lanes
    middle = (n - 1) / 2
    prefs = prefs or {}
    kinds = [k for k in lanes.values() if k is not None]
    if not kinds:
        return 0.0
    speeds = {k: get_default_speed(k) for k in set(kinds)}
    fastest = max(speeds.values()) or 1
    score = 0.0
    for lane, k in lanes.items():
        if k is None:
            continue
        distance = abs(lane - middle)
        score -= speeds[k] / fastest * distance  # 1
        left, right = lanes.get(lane - 1), lanes.get(lane + 1)
        if k == 'RED':
            score += 1.5 * sum(1 for other in (left, right) if other == 'RED')  # 2 (3 a pair)
        if k == 'PATCHWORK' and 'RED' in (left, right):
            score += 2.5  # it strengthens the Red beside it: one side of the wall is its
        if k in _SHOT_EFFECTS and 'RED' in (left, right):
            score += 2.0  # 3
        if k == 'WHITE' and lane in (2, n - 3):
            score += 3.0  # 4
        if k == 'CLOCKWORK' and lane in (0, n - 1):
            score += 2.0  # 5
        if k == 'YELLOW' and (lane <= 1 or lane >= n - 2):
            score += 1.0 + 0.5 * sum(1 for other in (left, right) if other == 'YELLOW')
        if k in prefs:
            score -= 0.05 * abs(distance - prefs[k])  # 6
    return score


def learned_layout(lanes, prefs):
    """The player's formation for these birds: the middle lanes to the kinds they keep in
    the middle (``prefs``: kind -> lanes from the middle), the edges to the others."""
    n = constants.layout.num_lanes
    middle = (n - 1) / 2
    prefs = prefs or {}
    default = sum(prefs.values()) / len(prefs) if prefs else middle / 2
    kinds = sorted((k for k in lanes.values() if k is not None), key=lambda k: (prefs.get(k, default), k))
    # Lanes from the middle out, alternating sides (left first)
    order = sorted(range(n), key=lambda lane: (abs(lane - middle), lane))
    free = [lane for lane in order if lane in lanes]
    return dict(zip(free, kinds, strict=False))


def best_formation_swap(formation, prefs=None):
    """(lane_a, lane_b) of the single swap that improves the formation most, or None."""
    n = constants.layout.num_lanes
    # Every lane, even one whose slot moved away through a portal
    known = _lane_kinds()
    lanes = {lane: known.get(lane) for lane in range(n)}
    current = formation_score(lanes, formation, prefs)
    best, best_gain = None, 0.0
    for a in range(n):
        for b in range(a + 1, n):
            if lanes.get(a) == lanes.get(b):
                continue
            trial = dict(lanes)
            trial[a], trial[b] = trial[b], trial[a]
            gain = formation_score(trial, formation, prefs) - current
            if gain > best_gain + 1e-9:
                best, best_gain = (a, b), gain
    return best


def brake_swap(cursor, formation='none', prefs=None):
    """Two lanes to swap just to shed momentum: rising birds near the cursor first.

    A swap sends both birds back to the starting line, rising; birds that are
    already rising lose least by it. With a formation it never spoils it: two
    birds of the same kind, or a swap that puts it right (the last swaps of a
    braking spree restore the formation).
    """
    living = [i for i in alive() if state.birds.y[i] < constants.layout.height]
    if len(living) < 2:
        return None
    if formation != 'none':
        fixing = best_formation_swap(formation, prefs)
        if fixing:
            return fixing
        same = [
            (abs(state.birds.home_lanes[a] - cursor) + abs(state.birds.home_lanes[b] - cursor), a, b)
            for a in living
            for b in living
            if a < b and kind(a) == kind(b)
        ]
        if same:
            _d, a, b = min(same)
            return state.birds.home_lanes[a], state.birds.home_lanes[b]
    rising = sorted(
        (i for i in living if state.birds.vy[i] == -1), key=lambda i: abs(state.birds.home_lanes[i] - cursor)
    )
    falling = sorted((i for i in living if state.birds.vy[i] == 1), key=lambda i: state.birds.y[i])
    a, b = (rising + falling)[:2]
    return state.birds.home_lanes[a], state.birds.home_lanes[b]


def wants_brake(skill, falling):
    if not can_swap():
        return False
    if skill.max_gear and state.game.speed > skill.max_gear:
        return True
    return bool(skill.brake_when_falling) and falling >= skill.brake_when_falling


# ---------------------------------------------------------------------- cards


def _needs():
    """What the flock lacks right now, as weights (1 = normal)."""
    living = alive()
    n = constants.layout.num_balls
    scared = sum(1 for i in living if i in state.special.scared_birds)
    early = max(0.0, 1 - (state.game.level - 1) / 12)  # 1 at the start, 0 from level 13
    lives = state.game.lives
    return {
        'survival': 1 + (2 if lives <= 3 else 0) + (1 if len(living) <= n // 2 else 0),
        'fear': 1 + scared,
        'economy': 0.5 + 1.5 * early,  # luck, prestige, more choices pay off over time
        'boss': 2.0 if state.enemies.boss is not None else 0.6,
        'damage': 1.0 + 0.1 * len(state.enemies.bats),
        'xp': 1 + sum(1 for i in living if state.birds.per_bird_xp[i] < 200) / max(1, len(living)),
    }


# Which need each stat answers (and how much one point / one percent is worth)
_STAT_NEED = {
    'damage_mult': ('damage', 0.08),
    'damage_bonus': ('damage', 0.05),
    'crit_chance': ('damage', 20),
    'crit_damage': ('damage', 2),
    'armor_pierce': ('damage', 0.15),
    'vs_bats': ('damage', 6),
    'vs_obstacles': ('damage', 4),
    'vs_elites': ('boss', 5),
    'rise_speed_bonus': ('survival', 0.25),
    'fall_speed_bonus': ('survival', -0.3),
    'fear_resist': ('fear', 8),
    'fear_duration_mult': ('fear', -0.08),
    'fear_immunity': ('fear', 10),
    'floor_save': ('survival', 30),
    'impact_stun': ('survival', -0.04),
    'power_potency': ('damage', 0.05),
    'power_duration': ('damage', 0.04),
    'power_uses': ('damage', 3),
    'pickup_radius': ('economy', 0.8),
    'luck': ('economy', 20),
    'egg_luck': ('economy', 60),
    'xp_gain': ('xp', 0.06),
    'score_mult': ('economy', 0.04),
    'prestige_bonus': ('economy', 1.2),
    'prestige_mult': ('economy', 0.1),
    'choices': ('economy', 4),
    'elite_chance': ('survival', -20),
}


def effect_value(effect, needs):
    """Worth of one effect for the flock now (negative for a drawback)."""
    if 'powerup' in effect:
        return 1.5 * needs['survival']
    if 'xp' in effect:
        return effect['xp'] / 15 * needs['xp']
    if 'rerolls' in effect or 'skips' in effect:
        return 1.5 * needs['economy']
    if 'enemy' in effect:
        changes = effect['enemy']
        changes = changes if isinstance(changes, dict) else vars(changes)
        return -sum(abs(v) for v in changes.values()) * 0.06 * needs['survival']
    need, unit = _STAT_NEED.get(effect.get('stat'), ('damage', 0.0))
    amount = effect['pct'] if 'pct' in effect else effect.get('add', 0)
    value = amount * unit * needs[need]
    if effect.get('seconds'):
        value *= 0.35 * needs['boss']
    return value


def wants_bird(bird_type, skill):
    """Would the strategy keep a new bird of this kind?"""
    if skill.favorites and skill.cull_others and bird_type not in skill.favorites:
        return False
    if skill.favorites and bird_type in skill.favorites:
        return True
    return len(alive()) < skill.keep_birds


def card_value(card, skill, needs=None):
    """Worth of an egg card (or a pact) for the flock right now."""
    needs = needs or _needs()
    if card['kind'] == 'refuse':
        return 0.0
    if card['kind'] == 'bird':
        bird_type = card['bird']
        if not wants_bird(bird_type, skill):
            return 0.0
        if bird_type in skill.favorites:
            return 20 * _RARITY_VALUE[card['rarity']]
        return 2.5 * _RARITY_VALUE[card['rarity']] * needs['survival']
    return sum(effect_value(e, needs) for e in card['effects'] + card.get('drawbacks', []))


def choose_card(offer, skill):
    """Index of the best option of an offer under the adaptive policy."""
    needs = _needs()
    values = [card_value(c, skill, needs) for c in offer['cards']]
    return max(range(len(values)), key=lambda i: values[i])


def describe(skill):
    """One line naming the strategy fields that differ from the defaults."""
    from dataclasses import fields

    from src.sim.bot import Skill

    defaults = Skill()
    names = (
        'max_gear',
        'brake_when_falling',
        'formation',
        'keep_birds',
        'favorites',
        'cull_others',
        'card_policy',
        'pact_policy',
    )
    parts = [
        f'{f.name}={getattr(skill, f.name)}'
        for f in fields(skill)
        if f.name in names and getattr(skill, f.name) != getattr(defaults, f.name)
    ]
    return ', '.join(parts) or 'default'
