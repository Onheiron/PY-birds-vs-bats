"""Enemy, obstacle, flower and cloud spawning plus despawn."""

import random

from src.core import constants, state
from src.engine import clock, enemy_stats, events
from src.engine.birds import check_pending_transforms
from src.engine.logic.flowers import maybe_add_flower_to_obstacle
from src.engine.logic.helpers import get_obstacle_lanes
from src.engine.notifications import notify
from src.entities.sprites import (
    OBSTACLE_SPRITE_T1,
    ORANGE,
    get_biome_obstacles,
    get_obstacle_hitbox_lanes,
    get_obstacle_sprite_width,
    get_random_obstacle_sprite,
)
from src.services import save_manager


def spawn_obstacle():
    """Potentially spawn a new obstacle."""
    state.enemies.obstacle_spawn_timer -= 1
    if state.enemies.obstacle_spawn_timer > 0:
        return

    # Use milestone level (1-18) for spawning, not speed
    level = state.game.level
    level_group = state.game.level_group  # 1-6
    sub_level = ((level - 1) % 3) + 1  # 1, 2, or 3 within biome

    # Get spawn rate parameters from config
    spawning = constants.obstacle.spawning
    biome_base = getattr(spawning, 'biome_base', 40)
    biome_decay = getattr(spawning, 'biome_decay', 0.85)
    sublevel_decay = getattr(spawning, 'sublevel_decay', 0.9)
    min_spawn_rate = getattr(spawning, 'min_spawn_rate', 6)

    # Spawn rate formula from config
    base_spawn_rate = max(
        min_spawn_rate, int(biome_base * (biome_decay**level_group) * (sublevel_decay ** (sub_level - 1)))
    )
    state.enemies.obstacle_spawn_timer = base_spawn_rate

    # Get tier weights from config
    tier_weights = constants.obstacle.tier_weights
    if level <= 3:
        weights = getattr(tier_weights, 'level_1_3', [60, 28, 10, 2])
    elif level <= 6:
        weights = getattr(tier_weights, 'level_4_6', [45, 35, 15, 5])
    elif level <= 9:
        weights = getattr(tier_weights, 'level_7_9', [30, 35, 25, 10])
    elif level <= 12:
        weights = getattr(tier_weights, 'level_10_12', [20, 35, 30, 15])
    elif level <= 15:
        weights = getattr(tier_weights, 'level_13_15', [10, 30, 38, 22])
    else:
        weights = getattr(tier_weights, 'level_16_18', [5, 20, 45, 30])

    tier = random.choices([1, 2, 3, 4], weights=weights)[0]

    # Ottieni sprite del bioma per calcolare larghezza
    biome_obstacles_preview = get_biome_obstacles(level_group)
    new_sprite = biome_obstacles_preview.get(tier, OBSTACLE_SPRITE_T1)
    new_sprite_width = get_obstacle_sprite_width(new_sprite)

    # Mappa quali lane sono occupate (usa hitbox dinamica)
    occupied_lanes = set()
    for obs in state.enemies.obstacles:
        if obs['y_pos'] < 5:  # Solo ostacoli vicini al top
            occupied_lanes.update(get_obstacle_lanes(obs))

    # Trova posizioni valide per il nuovo ostacolo
    valid_start_lanes = []
    for start_lane in range(constants.layout.num_lanes):
        # Calcola quali lane occuperebbe il nuovo ostacolo in questa posizione
        lanes_needed = get_obstacle_hitbox_lanes(
            start_lane, new_sprite_width, constants.layout.lane_positions, constants.layout.num_lanes
        )
        if not lanes_needed & occupied_lanes:
            valid_start_lanes.append(start_lane)

    if not valid_start_lanes:
        state.enemies.obstacle_spawn_timer = max(5, base_spawn_rate // 4)
        return

    # Permetti più ostacoli consecutivi ai livelli alti (level 1-18)
    consecutive_limit = 2 + level // 4  # 2 at lv1, 3 at lv4, 4 at lv8, 5 at lv12, 6 at lv16
    if len(state.enemies.spawn_queue) >= consecutive_limit:
        obstacle_count = sum(
            1 for item in state.enemies.spawn_queue[-consecutive_limit:] if item.get('type') == 'obstacle'
        )
        if obstacle_count >= consecutive_limit:
            state.enemies.obstacle_spawn_timer = max(5, base_spawn_rate // 4)
            return

    lane = random.choice(valid_start_lanes)

    # Get HP from config with level scaling
    hp_by_tier = constants.obstacle.hp_by_tier
    # Handle both dict and namespace access
    if isinstance(hp_by_tier, dict):
        base_hp = hp_by_tier.get(tier, hp_by_tier.get(str(tier), 5))
    else:
        base_hp = getattr(hp_by_tier, str(tier), 5)
    level_hp_mult = getattr(constants.obstacle, 'level_hp_multiplier', 0.1)
    level_multiplier = 1.0 + (level - 1) * level_hp_mult
    hp = int(base_hp * level_multiplier)

    # Seleziona sprite casuale (variante + eventuale flip)
    sprite, flipped = get_random_obstacle_sprite(level_group, tier, allow_flip=True)
    sprite_height = len(sprite)
    sprite_width = get_obstacle_sprite_width(sprite)

    # Spawn fuori schermo: y negativo così entra gradualmente
    start_y = -sprite_height + 1

    # Assign unique ID to obstacle
    obstacle_id = state.enemies.obstacle_id_counter
    state.enemies.obstacle_id_counter += 1

    obstacle = {
        'id': obstacle_id,
        'lane': lane,
        'y_pos': start_y,
        'tier': tier,
        'hp': hp,
        'sprite_width': sprite_width,
        'sprite': sprite,  # Sprite specifica (variante + flip)
        'flipped': flipped,
    }
    state.enemies.spawn_queue.append({'type': 'obstacle', 'data': enemy_stats.equip_obstacle(obstacle)})


def spawn_bat():
    """Maybe spawn a bat, as the current world says (bat_enemy.worlds)."""
    state.enemies.bat_spawn_timer -= 1
    if state.enemies.bat_spawn_timer > 0:
        return
    world = enemy_stats.world_table()
    interval = int(world.get('spawn_interval', 0) or 0)
    max_bats = int(world.get('max_bats', 0) or 0)
    if interval <= 0 or max_bats <= 0:
        state.enemies.bat_spawn_timer = 60  # no bats in this world: look again later
        return
    state.enemies.bat_spawn_timer = interval
    if len(state.enemies.bats) >= max_bats:
        state.enemies.bat_spawn_timer = interval // 2
        return

    level = state.game.level
    tier = enemy_stats.roll_tier(world)
    hp = _bat_hp(tier, level)
    x_pos = random.randint(0, constants.layout.width - 8)
    low, high = list(world.get('height') or [3, 8])
    target_y = random.randint(int(low), max(int(low), min(int(high), constants.layout.starting_line - 3)))
    kind = enemy_stats.roll_kind(tier, world)
    if kind == 'diver':
        # Divers keep high, to have room for their dive
        low_f, high_f = list(world.get('dive_height') or [0.1, 0.3])
        screen = constants.layout.starting_line
        target_y = random.randint(max(1, int(screen * low_f)), max(2, int(screen * high_f)))
    start_y = -(3 if kind == 'spellcaster' else 2) + 1  # spellcasters are 3 lines tall, others 2
    bat = enemy_stats.make_bat(tier, kind, x_pos, start_y, target_y, hp, enemy_stats.roll_elite())
    state.enemies.spawn_queue.append({'type': 'bat', 'data': bat})


def _bat_hp(tier, level):
    """Base HP of a bat of ``tier`` at ``level`` (bat_enemy.hp_by_tier, + level_hp_multiplier per level)."""
    table = constants.bat_enemy.hp_by_tier
    if isinstance(table, dict):
        hp = table.get(tier, table.get(str(tier), 20))
    else:
        hp = getattr(table, str(tier), 20)
    return int(hp * (1 + (level - 1) * float(getattr(constants.bat_enemy, 'level_hp_multiplier', 0.0))))


def process_spawn_queue():
    """Process the spawn queue to actually spawn entities."""

    while state.enemies.spawn_queue:
        item = state.enemies.spawn_queue.pop(0)
        if item['type'] == 'obstacle':
            obstacle_data = item['data']

            # Check if swamp biome (level_group 4) - obstacles can have flowers
            if state.game.level_group == 4:
                maybe_add_flower_to_obstacle(obstacle_data)

            state.enemies.obstacles.append(obstacle_data)
            # Track obstacle discovery by tier
            tier = obstacle_data.get('tier', 1)
            tier_names = {1: 'TREE', 2: 'ROCK', 3: 'CLOUD', 4: 'BARRIER'}
            save_manager.discover_obstacle(tier_names.get(tier, 'TREE'))
        elif item['type'] == 'bat':
            state.enemies.bats.append(item['data'])
            if item['data'].get('elite'):
                notify(enemy_stats.affix_names(item['data']['affixes']) + ' bat', title='Elite!')
            # Track bat discovery by tier
            tier = item['data'].get('tier', 1)
            tier_names = {1: 'BASIC', 2: 'FAST', 3: 'DIVE', 4: 'BOSS'}
            save_manager.discover_bat(tier_names.get(tier, 'BASIC'))


def spawn_cloud_bank():
    """Spawn cloud banks for Mountain Range biome (level group 6)."""
    # Only spawn in Mountain Range biome
    if state.game.level_group != 6:
        state.enemies.cloud_banks = []  # Clear clouds when leaving biome
        return

    state.enemies.cloud_spawn_timer -= 1
    if state.enemies.cloud_spawn_timer > 0:
        return

    # Spawn rate - clouds spawn occasionally
    state.enemies.cloud_spawn_timer = random.randint(80, 150)

    # Max clouds on screen
    if len(state.enemies.cloud_banks) >= 3:
        return

    # Cloud spans multiple lanes
    width = random.randint(8, 16)
    x_pos = random.randint(0, constants.layout.width - width)

    # Cloud height (2-4 rows)
    height = random.randint(2, 4)

    # Start above screen
    y_pos = -height

    state.enemies.cloud_banks.append(
        {
            'x_pos': x_pos,
            'y_pos': y_pos,
            'width': width,
            'height': height,
            'opacity': random.choice([0.3, 0.5, 0.7]),  # Varying opacity
        }
    )


def update_cloud_banks():
    """Move cloud banks down and remove off-screen ones."""
    if state.game.level_group != 6:
        return

    # Move clouds down (slower than obstacles)
    if state.game.frame_count % 8 == 0:
        for cloud in state.enemies.cloud_banks:
            cloud['y_pos'] += 1

    # Remove clouds that are off screen
    state.enemies.cloud_banks = [
        cloud for cloud in state.enemies.cloud_banks if cloud['y_pos'] < constants.layout.height + 5
    ]


def despawn_old_entities():
    """Remove entities that have been around too long."""
    now = clock.now()

    # Bats fly away after their linger stat (armored bats stay longer)
    for bat in state.enemies.bats[:]:
        if now - bat.get('spawn_ts', now) > enemy_stats.get(bat, 'linger'):
            state.enemies.bats.remove(bat)

    # Loot despawn after configured time
    loot_despawn = getattr(constants.loot, 'loot_despawn_time', 30)
    for loot in state.items.loot_items[:]:
        if now - loot.get('spawn_ts', now) > loot_despawn:
            # Orange eggs kill their bird when they despawn
            if loot.get('type') == 'orange_egg' and loot.get('y_pos') == constants.layout.starting_line:
                lane_x = loot.get('x_pos')
                for li in range(constants.layout.num_lanes):
                    if constants.layout.lane_positions[li] == lane_x:
                        for bi in range(constants.layout.num_balls):
                            if (
                                state.birds.random_lanes[bi] == li
                                and state.birds.colors[bi] == ORANGE
                                and state.birds.y[bi] == 999
                                and not state.birds.lost[bi]
                            ):
                                state.birds.lost[bi] = True
                                state.birds.y[bi] = constants.layout.height - 1
                                state.game.lives -= 1
                                events.emit('bird_lost', bird=bi, color=ORANGE, cause='crushed')
                                # Check if a pending bird can now transform

                                check_pending_transforms(ORANGE)
                                if state.game.lives <= 0:
                                    state.game.game_over = True
                                break
                        break
            state.items.loot_items.remove(loot)
