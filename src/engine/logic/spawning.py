"""Enemy, obstacle, flower and cloud spawning plus despawn."""

import random

from src.core import constants, state
from src.engine import clock
from src.engine.birds import check_pending_transforms
from src.engine.logic.flowers import maybe_add_flower_to_obstacle
from src.engine.logic.helpers import get_obstacle_lanes
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

    state.enemies.spawn_queue.append(
        {
            'type': 'obstacle',
            'data': {
                'id': obstacle_id,
                'lane': lane,
                'y_pos': start_y,
                'tier': tier,
                'hp': hp,
                'sprite_width': sprite_width,
                'sprite': sprite,  # Sprite specifica (variante + flip)
                'flipped': flipped,
            },
        }
    )


def spawn_bat():
    """Potentially spawn a new bat."""
    state.enemies.bat_spawn_timer -= 1
    if state.enemies.bat_spawn_timer > 0:
        return

    # Use milestone level (1-18) for spawning, not speed
    level = state.game.level
    if level < 4:  # Bats start at level 2-1 (milestone 4)
        return

    # Get spawn rate from config
    spawn_rates = getattr(constants.bat_enemy, 'spawn_rate_by_level', None)
    if level <= 6:
        base_spawn_rate = getattr(spawn_rates, 'level_4_6', 200) if spawn_rates else 200
    elif level <= 9:
        base_spawn_rate = getattr(spawn_rates, 'level_7_9', 150) if spawn_rates else 150
    elif level <= 12:
        base_spawn_rate = getattr(spawn_rates, 'level_10_12', 100) if spawn_rates else 100
    elif level <= 15:
        base_spawn_rate = getattr(spawn_rates, 'level_13_15', 70) if spawn_rates else 70
    else:
        base_spawn_rate = getattr(spawn_rates, 'level_16_18', 50) if spawn_rates else 50

    state.enemies.bat_spawn_timer = base_spawn_rate

    # Get max bats from config
    max_bats_cfg = getattr(constants.bat_enemy, 'max_bats_by_level', None)
    if level <= 6:
        max_bats = getattr(max_bats_cfg, 'level_4_6', 1) if max_bats_cfg else 1
    elif level <= 9:
        max_bats = getattr(max_bats_cfg, 'level_7_9', 2) if max_bats_cfg else 2
    elif level <= 12:
        max_bats = getattr(max_bats_cfg, 'level_10_12', 3) if max_bats_cfg else 3
    elif level <= 15:
        max_bats = getattr(max_bats_cfg, 'level_13_15', 4) if max_bats_cfg else 4
    else:
        max_bats = getattr(max_bats_cfg, 'level_16_18', 5) if max_bats_cfg else 5

    if len(state.enemies.bats) >= max_bats:
        state.enemies.bat_spawn_timer = base_spawn_rate // 2
        return

    # Get tier weights from config
    tier_weights_cfg = getattr(constants.bat_enemy, 'tier_weights_by_level', None)
    if level <= 6:
        weights = getattr(tier_weights_cfg, 'level_4_6', [70, 25, 5, 0]) if tier_weights_cfg else [70, 25, 5, 0]
    elif level <= 9:
        weights = getattr(tier_weights_cfg, 'level_7_9', [50, 35, 12, 3]) if tier_weights_cfg else [50, 35, 12, 3]
    elif level <= 12:
        weights = getattr(tier_weights_cfg, 'level_10_12', [30, 40, 22, 8]) if tier_weights_cfg else [30, 40, 22, 8]
    elif level <= 15:
        weights = getattr(tier_weights_cfg, 'level_13_15', [15, 35, 35, 15]) if tier_weights_cfg else [15, 35, 35, 15]
    else:
        weights = getattr(tier_weights_cfg, 'level_16_18', [5, 25, 45, 25]) if tier_weights_cfg else [5, 25, 45, 25]
    tier = random.choices([1, 2, 3, 4], weights=weights)[0]

    # Get HP from config
    bat_hp_by_tier = constants.bat_enemy.hp_by_tier
    if isinstance(bat_hp_by_tier, dict):
        hp = bat_hp_by_tier.get(tier, bat_hp_by_tier.get(str(tier), 20))
    else:
        hp = getattr(bat_hp_by_tier, str(tier), 20)

    # Spawn position X
    x_pos = random.randint(0, constants.layout.width - 8)

    # Get target Y from config
    target_y_cfg = getattr(constants.bat_enemy, 'target_y_by_level', None)
    if level <= 6:
        y_range = getattr(target_y_cfg, 'level_4_6', None) if target_y_cfg else None
        target_y_min = (
            y_range.get('min', 3) if isinstance(y_range, dict) else (getattr(y_range, 'min', 3) if y_range else 3)
        )
        target_y_max = (
            y_range.get('max', 8) if isinstance(y_range, dict) else (getattr(y_range, 'max', 8) if y_range else 8)
        )
    elif level <= 9:
        y_range = getattr(target_y_cfg, 'level_7_9', None) if target_y_cfg else None
        target_y_min = (
            y_range.get('min', 5) if isinstance(y_range, dict) else (getattr(y_range, 'min', 5) if y_range else 5)
        )
        target_y_max = (
            y_range.get('max', 12) if isinstance(y_range, dict) else (getattr(y_range, 'max', 12) if y_range else 12)
        )
    elif level <= 12:
        y_range = getattr(target_y_cfg, 'level_10_12', None) if target_y_cfg else None
        target_y_min = (
            y_range.get('min', 8) if isinstance(y_range, dict) else (getattr(y_range, 'min', 8) if y_range else 8)
        )
        target_y_max = (
            y_range.get('max', 16) if isinstance(y_range, dict) else (getattr(y_range, 'max', 16) if y_range else 16)
        )
    elif level <= 15:
        y_range = getattr(target_y_cfg, 'level_13_15', None) if target_y_cfg else None
        target_y_min = (
            y_range.get('min', 10) if isinstance(y_range, dict) else (getattr(y_range, 'min', 10) if y_range else 10)
        )
        target_y_max = (
            y_range.get('max', 20) if isinstance(y_range, dict) else (getattr(y_range, 'max', 20) if y_range else 20)
        )
    else:
        y_range = getattr(target_y_cfg, 'level_16_18', None) if target_y_cfg else None
        target_y_min = (
            y_range.get('min', 12) if isinstance(y_range, dict) else (getattr(y_range, 'min', 12) if y_range else 12)
        )
        target_y_max = (
            y_range.get('max', 23)
            if isinstance(y_range, dict)
            else (getattr(y_range, 'max', 23) if y_range else constants.layout.starting_line - 5)
        )

    target_y = random.randint(target_y_min, min(target_y_max, constants.layout.starting_line - 3))

    # Check if bat should be armored or diver (mutually exclusive)
    armored = False
    diver = False

    # First check for diver (any tier)
    diver_cfg = getattr(constants.bat_enemy, 'diver', None)
    if diver_cfg:
        min_diver_tier = getattr(diver_cfg, 'min_tier', 1)
        if tier >= min_diver_tier:
            diver_prob_cfg = getattr(diver_cfg, 'spawn_probability_by_level', None)
            if diver_prob_cfg:
                if level <= 3:
                    diver_prob = getattr(diver_prob_cfg, 'level_1_3', 0.0)
                elif level <= 6:
                    diver_prob = getattr(diver_prob_cfg, 'level_4_6', 0.08)
                elif level <= 9:
                    diver_prob = getattr(diver_prob_cfg, 'level_7_9', 0.12)
                elif level <= 12:
                    diver_prob = getattr(diver_prob_cfg, 'level_10_12', 0.16)
                elif level <= 15:
                    diver_prob = getattr(diver_prob_cfg, 'level_13_15', 0.20)
                else:
                    diver_prob = getattr(diver_prob_cfg, 'level_16_18', 0.25)
                diver = random.random() < diver_prob

    # If not diver, check for spellcaster (tier 2+ only)
    spellcaster = False
    if not diver:
        spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
        if spellcaster_cfg:
            min_spell_tier = getattr(spellcaster_cfg, 'min_tier', 2)
            if tier >= min_spell_tier:
                spell_prob_cfg = getattr(spellcaster_cfg, 'spawn_probability_by_level', None)
                if spell_prob_cfg:
                    if level <= 3:
                        spell_prob = getattr(spell_prob_cfg, 'level_1_3', 0.0)
                    elif level <= 6:
                        spell_prob = getattr(spell_prob_cfg, 'level_4_6', 0.05)
                    elif level <= 9:
                        spell_prob = getattr(spell_prob_cfg, 'level_7_9', 0.08)
                    elif level <= 12:
                        spell_prob = getattr(spell_prob_cfg, 'level_10_12', 0.12)
                    elif level <= 15:
                        spell_prob = getattr(spell_prob_cfg, 'level_13_15', 0.15)
                    else:
                        spell_prob = getattr(spell_prob_cfg, 'level_16_18', 0.20)
                    spellcaster = random.random() < spell_prob

    # If not diver or spellcaster, check for armored (tier 2+ only)
    if not diver and not spellcaster:
        armored_cfg = getattr(constants.bat_enemy, 'armored', None)
        if armored_cfg:
            min_armor_tier = getattr(armored_cfg, 'min_tier', 2)
            if tier >= min_armor_tier:
                armor_prob_cfg = getattr(armored_cfg, 'spawn_probability_by_level', None)
                if armor_prob_cfg:
                    if level <= 3:
                        armor_prob = getattr(armor_prob_cfg, 'level_1_3', 0.0)
                    elif level <= 6:
                        armor_prob = getattr(armor_prob_cfg, 'level_4_6', 0.05)
                    elif level <= 9:
                        armor_prob = getattr(armor_prob_cfg, 'level_7_9', 0.10)
                    elif level <= 12:
                        armor_prob = getattr(armor_prob_cfg, 'level_10_12', 0.15)
                    elif level <= 15:
                        armor_prob = getattr(armor_prob_cfg, 'level_13_15', 0.20)
                    else:
                        armor_prob = getattr(armor_prob_cfg, 'level_16_18', 0.25)
                    armored = random.random() < armor_prob

    # Diver bats have different Y position (upper half of screen)
    final_target_y = target_y
    if diver and diver_cfg:
        y_range_cfg = getattr(diver_cfg, 'y_range_by_level', None)
        if y_range_cfg:
            if level <= 3:
                y_frac = getattr(y_range_cfg, 'level_1_3', None)
            elif level <= 6:
                y_frac = getattr(y_range_cfg, 'level_4_6', None)
            elif level <= 9:
                y_frac = getattr(y_range_cfg, 'level_7_9', None)
            elif level <= 12:
                y_frac = getattr(y_range_cfg, 'level_10_12', None)
            elif level <= 15:
                y_frac = getattr(y_range_cfg, 'level_13_15', None)
            else:
                y_frac = getattr(y_range_cfg, 'level_16_18', None)

            if y_frac:
                min_frac = y_frac.get('min', 0.10) if isinstance(y_frac, dict) else getattr(y_frac, 'min', 0.10)
                max_frac = y_frac.get('max', 0.30) if isinstance(y_frac, dict) else getattr(y_frac, 'max', 0.30)
                screen_height = constants.layout.starting_line
                y_min = int(screen_height * min_frac)
                y_max = int(screen_height * max_frac)
                final_target_y = random.randint(max(1, y_min), max(2, y_max))

    # Spellcasters are 3 lines tall, others are 2
    bat_sprite_height = 3 if spellcaster else 2
    start_y = -bat_sprite_height + 1

    bat_data = {
        'x_pos': x_pos,
        'y_pos': start_y,
        'direction': random.choice([-1, 1]),
        'tier': tier,
        'hp': hp,
        'max_hp': hp,
        'target_y': final_target_y,
        'spawn_ts': clock.now(),
        'armored': armored,
        'diver': diver,
        'spellcaster': spellcaster,
    }

    # Add diver-specific fields
    if diver:
        bat_data['diver_state'] = 'flying'  # 'flying', 'diving', 'stunned', 'returning'
        bat_data['diver_home_y'] = final_target_y  # Remember home position
        bat_data['dive_start_y'] = None  # Y when dive started
        bat_data['stun_end_time'] = None  # When stun ends

    # Add spellcaster-specific fields
    if spellcaster:
        bat_data['spell_state'] = 'idle'  # 'idle', 'casting'
        bat_data['spell_cooldown'] = 0  # Time until can cast again
        bat_data['casting_end_time'] = None  # When casting animation ends
        # Determine known spells based on tier
        spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
        spells_by_tier = getattr(spellcaster_cfg, 'spells_by_tier', None) if spellcaster_cfg else None
        if spells_by_tier:
            if isinstance(spells_by_tier, dict):
                num_spells = spells_by_tier.get(tier, spells_by_tier.get(str(tier), 1))
            else:
                num_spells = getattr(spells_by_tier, str(tier), 1)
        else:
            num_spells = min(tier - 1, 3)  # Default: tier 2=1, tier 3=2, tier 4=3
        # Spells in order: silence, repugnant_wind, exile
        all_spells = ['silence', 'repugnant_wind', 'exile']
        bat_data['known_spells'] = all_spells[:num_spells]

    state.enemies.spawn_queue.append({'type': 'bat', 'data': bat_data})


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

    # Bats despawn after configured time (armored bats stay longer)
    bat_despawn = getattr(constants.loot, 'bat_despawn_time', 60)
    armored_cfg = getattr(constants.bat_enemy, 'armored', None)
    armored_despawn = getattr(armored_cfg, 'despawn_time', 150) if armored_cfg else 150

    for bat in state.enemies.bats[:]:
        is_armored = bat.get('armored', False)
        despawn_time = armored_despawn if is_armored else bat_despawn
        if now - bat.get('spawn_ts', now) > despawn_time:
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
                                # Check if a pending bird can now transform

                                check_pending_transforms(ORANGE)
                                if state.game.lives <= 0:
                                    state.game.game_over = True
                                break
                        break
            state.items.loot_items.remove(loot)
