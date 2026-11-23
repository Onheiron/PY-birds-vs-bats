"""World hazards: what each world adds besides its enemies.

Every hazard is set per world in the ``hazards`` section of config.yml (a
world without an entry does not have it):

- ``winds``: gusts on a few adjacent lanes. World 1 (Windy Woods) only has
  tailwind (birds climb faster and fall slower); world 6 (Mountain Range)
  also has headwind (the opposite).
- ``emerging``: a share of the obstacles rise out of the ground (marsh mud in
  world 3, darkness in world 5) at a random height instead of falling in from
  the top; for ``warning`` seconds they are only bubbles and do not block.
- ``darkness``: only the lanes around the cursor (and the lanes of Clockwork
  birds) can be seen; fireflies dropped by bats light everything for a while.
- ``stalactites``: a lane shows cracks at the top for ``warning`` seconds,
  then a stalactite falls fast down it.
- ``peaks``: a share of the obstacles are peaks (stats: enemy_stats.obstacles.kinds.peak).
- ``fog``: low cloud banks drifting down over the birds.

Obstacle kinds (emerging, stalactite, peak) take their stats from
``enemy_stats.obstacles.kinds``.
"""

import random

from src.core import constants, state
from src.engine import clock, enemy_stats


def _section(name):
    return getattr(getattr(constants, 'hazards', None), name, None)


def setting(name, world=None):
    """The ``hazards.<name>`` entry of a world (default: the current one) as a dict, or None."""
    table = enemy_stats._as_dict(_section(name))
    w = max(1, state.game.level_group if world is None else world)
    entry = table.get(w, table.get(str(w)))
    return enemy_stats._as_dict(entry) if entry is not None else None


def _between(pair, default):
    low, high = list(pair or default)
    return random.uniform(float(low), float(high))


def update():
    """Run every tick: world intro, winds, stalactites, fog."""
    _announce_world()
    now = clock.now()
    _update_winds(now)
    _update_stalactites(now)
    _update_fog()


def _announce_world():
    """When a world starts, say what it brings (hazards.intro)."""
    world = state.game.level_group
    if state.hazards.world_seen == world:
        return
    state.hazards.world_seen = world
    table = enemy_stats._as_dict(_section('intro'))
    text = table.get(world, table.get(str(world)))
    if text:
        from src.engine.notifications import notify
        from src.entities.sprites import get_biome_name

        notify(str(text), title=f'{get_biome_name(world)}:')


# --------------------------------------------------------------------------- winds


def _update_winds(now):
    winds = state.hazards.lane_winds
    for lane in [lane for lane, w in winds.items() if now >= w['end']]:
        del winds[lane]
    cfg = setting('winds')
    if cfg is None:
        state.hazards.next_wind = None
        return
    if state.hazards.next_wind is None:
        state.hazards.next_wind = now + _between(cfg.get('interval'), (12, 20))
        return
    if now < state.hazards.next_wind:
        return
    state.hazards.next_wind = now + _between(cfg.get('interval'), (12, 20))
    n = constants.layout.num_lanes
    count = max(1, min(n, round(_between(cfg.get('lanes'), (2, 4)))))
    first = random.randint(0, n - count)
    tail = random.random() < float(cfg.get('tail_chance', 1.0))
    strength = float(cfg.get('strength', 1))
    for lane in range(first, first + count):
        winds[lane] = {'end': now + float(cfg.get('duration', 5.0)), 'tail': tail, 'strength': strength}


def lane_wind(lane):
    """(rise bonus, fall bonus) in speed points from the wind in ``lane`` (negative: slower)."""
    wind = state.hazards.lane_winds.get(lane)
    if not wind:
        return 0.0, 0.0
    s = wind['strength']
    return (s, -s) if wind['tail'] else (-s, s)


# --------------------------------------------------------------------------- obstacles


def obstacle_kind():
    """Kind of a new regular obstacle in this world: 'emerging', 'peak' or None."""
    emerging = setting('emerging')
    if emerging and random.random() < float(emerging.get('share', 0)):
        return 'emerging'
    peaks = setting('peaks')
    if peaks and random.random() < float(peaks.get('share', 0)):
        return 'peak'
    return None


def place_emerging(obstacle):
    """Put an emerging obstacle mid-screen, not solid for the warning time."""
    cfg = setting('emerging') or {}
    screen = constants.layout.starting_line
    obstacle['y_pos'] = int(screen * _between(cfg.get('rows'), (0.35, 0.70)))
    obstacle['emerge_until'] = clock.now() + float(cfg.get('warning', 1.0))
    obstacle['look'] = cfg.get('look', 'mud')


def is_emerging(obstacle):
    """Still rising out of the ground: only bubbles, it neither moves nor blocks."""
    return clock.now() < obstacle.get('emerge_until', 0)


def _update_stalactites(now):
    cfg = setting('stalactites')
    if cfg is None:
        state.hazards.next_stalactite = None
        state.hazards.stalactite_warnings = []
        return
    if state.hazards.next_stalactite is None:
        state.hazards.next_stalactite = now + _between(cfg.get('interval'), (6, 10))
    elif now >= state.hazards.next_stalactite and state.enemies.boss is None:
        state.hazards.next_stalactite = now + _between(cfg.get('interval'), (6, 10))
        lane = random.randrange(constants.layout.num_lanes)
        state.hazards.stalactite_warnings.append({'lane': lane, 'falls_at': now + float(cfg.get('warning', 1.0))})
    for warning in state.hazards.stalactite_warnings[:]:
        if now >= warning['falls_at']:
            state.hazards.stalactite_warnings.remove(warning)
            _drop_stalactite(warning['lane'], int(cfg.get('hp', 40)))


STALACTITE_SPRITE = ['▼']


def _drop_stalactite(lane, hp):
    obstacle_id = state.enemies.obstacle_id_counter
    state.enemies.obstacle_id_counter += 1
    obstacle = {
        'id': obstacle_id,
        'lane': lane,
        'y_pos': 0,
        'tier': 1,
        'kind': 'stalactite',
        'hp': hp,
        'sprite_width': 1,
        'sprite': STALACTITE_SPRITE,
        'flipped': False,
    }
    state.enemies.obstacles.append(enemy_stats.equip_obstacle(obstacle))


# --------------------------------------------------------------------------- darkness


def dark():
    """Is the screen dark right now (a dark world and no firefly light)?"""
    return setting('darkness') is not None and clock.now() >= state.hazards.light_until


def lit_lanes():
    """Lanes that can be seen in the dark: around the cursor, and the Clockwork birds' lanes."""
    cfg = setting('darkness') or {}
    radius = int(cfg.get('light_radius', 1))
    n = constants.layout.num_lanes
    lanes = {lane for lane in range(state.player.lane - radius, state.player.lane + radius + 1) if 0 <= lane < n}
    if cfg.get('clockwork_light', True):
        from src.entities.sprites import CLOCKWORK

        for i, color in enumerate(state.birds.colors):
            if color == CLOCKWORK and not state.birds.lost[i]:
                lanes.add(state.birds.random_lanes[i])
    return lanes


def visible(lane, y, lit=None):
    """Can a player see row ``y`` of ``lane``? Not in the dark outside the lit lanes, nor under fog.

    ``lit``: the lit lanes, when the caller already has them (None: work them out).
    """
    if dark():
        if lane not in (lit if lit is not None else lit_lanes()):
            return False
    x = constants.layout.lane_positions[lane]
    for cloud in state.enemies.cloud_banks:
        if (
            cloud['x_pos'] <= x < cloud['x_pos'] + cloud['width']
            and cloud['y_pos'] <= y < cloud['y_pos'] + cloud['height']
        ):
            return False
    return True


def maybe_drop_firefly(x_pos, y_pos):
    """A bat killed in a dark world may drop a firefly."""
    cfg = setting('darkness')
    if cfg is None or random.random() >= float(cfg.get('firefly_drop', 0)):
        return
    from src.engine.logic.drops import drop_loot

    positions = constants.layout.lane_positions
    lane_x = min(positions, key=lambda x: abs(x - x_pos))  # loot sits on a lane
    drop_loot({'x_pos': lane_x, 'y_pos': y_pos, 'type': 'firefly', 'rarity': 'common', 'spawn_ts': clock.now()}, 'bat')


def collect_firefly():
    cfg = setting('darkness') or {}
    state.hazards.light_until = clock.now() + float(cfg.get('firefly_light', 8.0))


# --------------------------------------------------------------------------- fog


def _update_fog():
    """Low cloud banks drifting down over the birds (hazards.fog)."""
    cfg = setting('fog')
    if cfg is None:
        state.enemies.cloud_banks = []
        return
    if state.game.frame_count % max(1, int(cfg.get('fall_interval', 8))) == 0:
        for cloud in state.enemies.cloud_banks:
            cloud['y_pos'] += 1
    state.enemies.cloud_banks = [c for c in state.enemies.cloud_banks if c['y_pos'] < constants.layout.height + 5]
    state.enemies.cloud_spawn_timer -= 1
    if state.enemies.cloud_spawn_timer > 0:
        return
    state.enemies.cloud_spawn_timer = int(_between(cfg.get('interval'), (80, 150)))
    if len(state.enemies.cloud_banks) >= int(cfg.get('max', 3)):
        return
    width = int(_between(cfg.get('width'), (8, 16)))
    height = int(_between(cfg.get('height'), (2, 4)))
    state.enemies.cloud_banks.append(
        {
            'x_pos': random.randint(0, max(0, constants.layout.width - width)),
            'y_pos': -height,
            'width': width,
            'height': height,
            'opacity': random.choice([0.3, 0.5, 0.7]),
        }
    )
