"""Abilities of the special bats: healer, bomber, plague, necromancer.

Every number comes from the bat's stats (enemy_stats.bats: kinds, worlds,
elite_kinds), so each can be tuned world by world:

- Healer: every ``ability_interval`` s heals the bats within ``heal_range``
  columns by ``heal_pct`` of their max HP.
- Bomber: when ready (``ability_interval``) drops a stone with
  ``ability_chance`` per second: a small obstacle (``stone_hp``) that falls a
  row every ``stone_interval`` ticks and stuns the bird it hits ``stone_stun`` s.
- Plague: a bird it touches is infected: it dies after ``plague_time`` s unless
  cured with ``plague_presses`` UP presses, and every second it may infect a
  bird in a lane next to it (``plague_spread``), wherever it is.
- Necromancer: when ready, with ``ability_chance`` per second, raises a zombie
  bird in an empty lane (``zombies`` at most). Zombies bounce by themselves
  while it lives, and scare (``zombie_fear`` s) a falling bird they pass in a
  lane next to theirs.
"""

import random

from src.core import constants, state
from src.engine import clock, enemy_stats, events, stats
from src.engine.birds import reset_bird_power, scare_bird, set_ball_vy
from src.entities.bird_types import BirdType, get_default_speed
from src.entities.sprites import ZOMBIE


def _per_tick(chance_per_second):
    return chance_per_second * getattr(constants.timing, 'base_sleep', 0.033)


def _ready(bat):
    """The ability is ready (ability_interval since its last use) and the bat is in place."""
    return clock.now() >= bat.get('ability_ready', 0) and bat['y_pos'] >= 0 and bat['y_pos'] >= bat['target_y']


def _used(bat):
    bat['ability_ready'] = clock.now() + enemy_stats.get(bat, 'ability_interval')


def _lane_of_x(x):
    positions = constants.layout.lane_positions
    return min(range(len(positions)), key=lambda lane: abs(positions[lane] - x))


# --------------------------------------------------------------------------- healer


def healer(bat):
    if not _ready(bat) or random.random() >= _per_tick(enemy_stats.get(bat, 'ability_chance')):
        return
    _used(bat)
    reach = enemy_stats.get(bat, 'heal_range')
    share = enemy_stats.get(bat, 'heal_pct')
    centre = bat['x_pos'] + 4
    healed = 0
    for other in state.enemies.bats:
        if abs(other['x_pos'] + 4 - centre) > reach:
            continue
        base = other.get('max_hp', other['hp'])
        top = int(base * (1 + enemy_stats.get(bat, 'overheal')))  # elites heal above max HP
        if other['hp'] < top:
            other['hp'] = min(top, other['hp'] + max(1, int(base * share)))
            healed += 1
    bat['healing_until'] = clock.now() + 0.5
    if healed:
        events.emit('bat_ability', kind='healer', count=healed)


# --------------------------------------------------------------------------- bomber

STONE_SPRITE = ['o']


def bomber(bat):
    if not _ready(bat) or random.random() >= _per_tick(enemy_stats.get(bat, 'ability_chance')):
        return
    _used(bat)
    obstacle_id = state.enemies.obstacle_id_counter
    state.enemies.obstacle_id_counter += 1
    stone = {
        'id': obstacle_id,
        'lane': _lane_of_x(bat['x_pos'] + 4),
        'y_pos': bat['y_pos'] + 2,
        'tier': 1,
        'kind': 'stone',
        'hp': int(enemy_stats.get(bat, 'stone_hp')),
        'sprite_width': 1,
        'sprite': STONE_SPRITE,
        'flipped': False,
    }
    enemy_stats.equip_obstacle(stone)
    # The bomber's stone numbers win over the generic stone kind
    stone['stats']['fall_interval'] = enemy_stats.get(bat, 'stone_interval')
    stone['stats']['stun'] = enemy_stats.get(bat, 'stone_stun')
    if enemy_stats.get(bat, 'stone_blast'):
        # Elite bombers: the stone explodes when broken
        stone['blast'] = {
            'push': enemy_stats.get(bat, 'blast_push'),
            'time': enemy_stats.get(bat, 'blast_push_time'),
            'fear': enemy_stats.get(bat, 'blast_fear'),
        }
    state.enemies.obstacles.append(stone)
    events.emit('bat_ability', kind='bomber', count=1)


# --------------------------------------------------------------------------- plague


def stone_blast(stone, bird=None):
    """A broken elite stone explodes in its lane: the bird that broke it (or, broken by a
    shot, a bird in its lane at most 1 row away) is knocked down and scared."""
    blast = stone['blast']
    if bird is not None:
        hit = [bird]
    else:
        hit = [
            j
            for j in range(len(state.birds.colors))
            if not state.birds.lost[j]
            and state.birds.random_lanes[j] == stone['lane']
            and abs(state.birds.y[j] - stone['y_pos']) <= 1
        ]
    for j in hit:
        set_ball_vy(j, 1)
        state.special.dive_fall_boosts[j] = {
            'frames': int(blast['time'] / constants.timing.base_sleep),
            'speed': blast['push'],
        }
        scare_bird(j, blast['fear'])
    events.emit('bat_ability', kind='stone blast', count=len(hit))


def infect(bird, bat=None, source=None):
    """Infect ``bird`` with the plague of ``bat`` (or copy the infection ``source``)."""
    special = state.special
    if state.birds.lost[bird] or bird in special.poisoned_birds:
        return False
    if source is None:
        source = {
            'time': enemy_stats.get(bat, 'plague_time'),
            'presses': int(enemy_stats.get(bat, 'plague_presses')),
            'spread': enemy_stats.get(bat, 'plague_spread'),
        }
        bleed = enemy_stats.get(bat, 'plague_bleed')
        if bleed > 0 and bird not in special.bleeding_birds:
            # Elite plague: it bleeds first (UP presses hurt), then turns to poison
            special.bleeding_birds[bird] = {
                'end_time': clock.now() + bleed,
                'lives_needed': source['presses'],
                'lives_lost': 0,
                'then_plague': source,
            }
            events.emit('bat_ability', kind='plague', count=1)
            return True
    special.poisoned_birds[bird] = {
        'death_time': clock.now() + source['time'],
        'cure_attempts_needed': source['presses'],
        'cure_attempts_done': 0,
        'plague': dict(source),
    }
    events.emit('bat_ability', kind='plague', count=1)
    return True


def spread_plague():
    """Every second an infected bird may infect a bird in a lane next to it (run every tick)."""
    for bird, info in list(state.special.poisoned_birds.items()):
        plague = info.get('plague')
        if not plague or state.birds.lost[bird]:
            continue
        if random.random() >= _per_tick(plague['spread']):
            continue
        lane = state.birds.random_lanes[bird]
        near = [
            j
            for j in range(len(state.birds.colors))
            if not state.birds.lost[j]
            and abs(state.birds.random_lanes[j] - lane) == 1
            and j not in state.special.poisoned_birds
        ]
        if near:
            infect(random.choice(near), source=plague)


# --------------------------------------------------------------------------- necromancer


def necromancer(bat):
    """Raise a zombie bird in an empty lane (a lost bird's slot), up to ``zombies`` of its own."""
    if not _ready(bat) or random.random() >= _per_tick(enemy_stats.get(bat, 'ability_chance')):
        return
    _used(bat)
    zombies = state.special.zombies
    mine = [i for i, z in zombies.items() if z.get('owner') == bat.get('uid') and not state.birds.lost[i]]
    if len(mine) >= int(enemy_stats.get(bat, 'zombies')):
        return
    birds = state.birds
    taken = {birds.random_lanes[i] for i in range(len(birds.colors)) if not birds.lost[i]}
    free = [i for i in range(len(birds.colors)) if birds.lost[i] and birds.random_lanes[i] not in taken]
    if not free:
        return
    slot = random.choice(free)
    birds.lost[slot] = False
    stats.clear_bird(slot)
    _make_zombie(slot)
    birds.y[slot] = constants.layout.starting_line
    set_ball_vy(slot, -1)
    zombies[slot] = {
        'raised': True,
        'owner': bat.get('uid'),
        'fear': enemy_stats.get(bat, 'zombie_fear'),
        'bite': enemy_stats.get(bat, 'zombie_bite'),
        'passed': [],
        'vy': -1,
    }
    events.emit('bat_ability', kind='necromancer', count=1)


def _make_zombie(i):
    birds = state.birds
    birds.colors[i] = ZOMBIE
    birds.speeds[i] = get_default_speed(BirdType.ZOMBIE)
    birds.per_bird_xp[i] = 0
    reset_bird_power(i)


def _bite(j, zombie):
    """A zombie's bite: bird ``j`` becomes a zombie too (still yours, but it scores nothing)."""
    stats.clear_bird(j)
    _make_zombie(j)
    state.special.zombies[j] = {
        'raised': False,
        'owner': None,
        'fear': zombie['fear'],
        'bite': zombie['bite'],
        'passed': [],
        'vy': state.birds.vy[j],
    }
    events.emit('bat_ability', kind='zombie bite', count=1)


def necromancer_alive():
    return any('necromancer' in enemy_stats.bat_kinds(b) for b in state.enemies.bats)


def update_zombies():
    """Zombie birds: they bounce by themselves while a necromancer lives (else you bounce
    them); passing a falling bird in a lane next to theirs they scare it, and may bite it."""
    zombies = state.special.zombies
    birds = state.birds
    for i in [i for i in zombies if birds.lost[i] or birds.colors[i] != ZOMBIE]:
        del zombies[i]
    if not zombies:
        return
    alive = necromancer_alive()
    for z, info in list(zombies.items()):  # a bite adds zombies
        if info['vy'] != birds.vy[z]:
            info['vy'] = birds.vy[z]
            info['passed'] = []  # a new climb or fall
        if alive and birds.vy[z] == 1 and birds.y[z] >= constants.layout.starting_line:
            birds.y[z] = constants.layout.starting_line
            set_ball_vy(z, -1)
        for j in range(len(birds.colors)):
            if j == z or birds.lost[j] or j in zombies or j in info['passed'] or birds.vy[j] != 1:
                continue
            if j in state.special.scared_birds:
                continue
            if abs(birds.random_lanes[j] - birds.random_lanes[z]) == 1 and abs(birds.y[j] - birds.y[z]) <= 1:
                info['passed'].append(j)
                scare_bird(j, info['fear'])
                if random.random() < info['bite']:
                    _bite(j, info)


def lost_raised_zombie(i):
    """Was bird ``i`` a zombie a necromancer raised (never yours: losing it costs no life)?"""
    zombie = state.special.zombies.get(i)
    return bool(zombie and zombie.get('raised'))


def update():
    """Per tick: plague spreading and zombies."""
    spread_plague()
    update_zombies()


ABILITIES = {'healer': healer, 'bomber': bomber, 'necromancer': necromancer}
