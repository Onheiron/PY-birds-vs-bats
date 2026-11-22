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
from src.engine import clock, enemy_stats, events
from src.engine.birds import scare_bird

ZOMBIE_STEP_TICKS = 2  # a zombie moves a row every 2 ticks


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
        top = other.get('max_hp', other['hp'])
        if other['hp'] < top:
            other['hp'] = min(top, other['hp'] + max(1, int(top * share)))
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
    state.enemies.obstacles.append(stone)
    events.emit('bat_ability', kind='bomber', count=1)


# --------------------------------------------------------------------------- plague


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
    if not _ready(bat) or random.random() >= _per_tick(enemy_stats.get(bat, 'ability_chance')):
        return
    _used(bat)
    mine = [z for z in state.enemies.zombies if z['owner'] == bat.get('uid')]
    if len(mine) >= int(enemy_stats.get(bat, 'zombies')):
        return
    taken = {state.birds.random_lanes[i] for i in range(len(state.birds.colors)) if not state.birds.lost[i]}
    taken |= {z['lane'] for z in state.enemies.zombies}
    empty = [lane for lane in range(constants.layout.num_lanes) if lane not in taken]
    if not empty:
        return
    state.enemies.zombies.append(
        {
            'lane': random.choice(empty),
            'y': constants.layout.starting_line,
            'vy': -1,
            'owner': bat.get('uid'),
            'fear': enemy_stats.get(bat, 'zombie_fear'),
            'scared': [],
        }
    )
    events.emit('bat_ability', kind='necromancer', count=1)


def update_zombies():
    """Zombies bounce by themselves while their necromancer lives; they scare falling neighbours."""
    owners = {b.get('uid') for b in state.enemies.bats}
    state.enemies.zombies = [z for z in state.enemies.zombies if z['owner'] in owners]
    if state.game.frame_count % ZOMBIE_STEP_TICKS:
        return
    for zombie in state.enemies.zombies:
        zombie['y'] += zombie['vy']
        if zombie['y'] <= 1:
            zombie['vy'] = 1
            zombie['scared'] = []  # a new pass
        elif zombie['y'] >= constants.layout.starting_line:
            zombie['vy'] = -1
            zombie['scared'] = []
        for j in range(len(state.birds.colors)):
            if state.birds.lost[j] or j in zombie['scared'] or state.birds.vy[j] != 1:
                continue
            if abs(state.birds.random_lanes[j] - zombie['lane']) == 1 and abs(state.birds.y[j] - zombie['y']) <= 1:
                zombie['scared'].append(j)
                scare_bird(j, zombie['fear'])


def update():
    """Per tick: plague spreading and zombies."""
    spread_plague()
    update_zombies()


ABILITIES = {'healer': healer, 'bomber': bomber, 'necromancer': necromancer}
