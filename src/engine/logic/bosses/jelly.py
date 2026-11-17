"""Jelly Boss (Rotten Marshes)."""

import random

from src.core import constants, state
from src.engine import clock
from src.engine.logic.bosses.common import get_boss_config
from src.engine.loot_tables import adjust_rarity_weights, choose_loot_type
from src.engine.progression import add_score, award_xp, compute_prestige


def spawn_jelly_boss():
    """Spawn the Jelly Boss for level 3-3."""
    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)
    hp = getattr(jelly_boss_cfg, 'hp', 400) if jelly_boss_cfg else 400

    # Jelly boss is 6 lines tall
    boss_sprite_height = 6
    boss_sprite_width = 23  # Width of jelly boss sprite
    base_x = (constants.layout.width - boss_sprite_width) // 2

    # Target Y at 1/4 from top
    target_y_frac = getattr(jelly_boss_cfg, 'target_y_fraction', 0.25) if jelly_boss_cfg else 0.25
    target_y = int(constants.layout.starting_line * target_y_frac)

    state.enemies.boss = {
        'x_pos': base_x,
        'base_x_pos': base_x,
        'y_pos': -boss_sprite_height,
        'target_y': target_y,
        'hp': hp,
        'max_hp': hp,
        'state': 'descending',
        'anim_frame': 0,  # Index into animation sequence (0-9)
        'anim_timer': 0,  # Timer for animation steps
        'oscillation_dir': 1,
        'spawn_ts': clock.now(),
        'boss_type': 'jelly',
        'spawned_bats': 0,  # Number of bats spawned
        'bat_spawn_anim': None,  # Active spawn animation
    }
    state.enemies.boss_spawned = True


def update_jelly_boss():
    """Update Jelly Boss state and behavior."""
    boss = state.enemies.boss
    if boss is None:
        return

    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)
    boss_state = boss['state']

    if boss_state == 'descending':
        descent_speed = getattr(jelly_boss_cfg, 'descent_speed', 8) if jelly_boss_cfg else 8
        target_y = boss.get('target_y', 5)
        if state.game.frame_count % descent_speed == 0:
            boss['y_pos'] += 1
            if boss['y_pos'] >= target_y:
                boss['state'] = 'active'
                boss['y_pos'] = target_y

    elif boss_state == 'active':
        # Animation cycling through 10 frames
        anim_speed = getattr(jelly_boss_cfg, 'anim_frames_per_step', 30) if jelly_boss_cfg else 30
        boss['anim_timer'] = boss.get('anim_timer', 0) + 1

        if boss['anim_timer'] >= anim_speed:
            boss['anim_timer'] = 0
            boss['anim_frame']
            boss['anim_frame'] = (boss['anim_frame'] + 1) % 10  # 10 frames in sequence

            # Check if we just reached frame 8 (spawn frame, 1-indexed = frame index 7)
            spawn_frame = getattr(jelly_boss_cfg, 'spawn_frame', 8) if jelly_boss_cfg else 8
            spawn_frame_idx = spawn_frame - 1  # Convert to 0-indexed
            max_concurrent = getattr(jelly_boss_cfg, 'max_spawned_bats', 5) if jelly_boss_cfg else 5

            # Count currently ALIVE bats spawned by this boss (not total ever spawned)
            alive_boss_bats = sum(1 for bat in state.enemies.bats if bat.get('from_boss'))

            if boss['anim_frame'] == spawn_frame_idx and alive_boss_bats < max_concurrent:
                # Start bat spawn animation (o -> O -> () -> bat)
                boss['bat_spawn_anim'] = {
                    'active': True,
                    'frame': 0,  # Animation frame (0=o, 1=O, 2=(), 3=spawn bat)
                    'timer': 0,
                    'x_pos': boss['x_pos'] + 11,  # Center of boss head
                    'y_pos': boss['y_pos'] - 1,  # One row ABOVE boss (not inside)
                    'char': 'o',  # Starting character
                }

        # Update bat spawn animation if active
        _update_jelly_bat_spawn_anim(boss)

        # Oscillation movement
        oscillation_speed = getattr(jelly_boss_cfg, 'oscillation_speed', 10) if jelly_boss_cfg else 10
        oscillation_range = getattr(jelly_boss_cfg, 'oscillation_range', 3) if jelly_boss_cfg else 3
        if state.game.frame_count % oscillation_speed == 0:
            base_x = boss['base_x_pos']
            current_offset = boss['x_pos'] - base_x
            direction = boss.get('oscillation_dir', 1)
            new_offset = current_offset + direction
            if new_offset >= oscillation_range:
                new_offset = oscillation_range
                boss['oscillation_dir'] = -1
            elif new_offset <= -oscillation_range:
                new_offset = -oscillation_range
                boss['oscillation_dir'] = 1
            boss['x_pos'] = base_x + new_offset

    elif boss_state == 'dying':
        _convert_jelly_boss_to_obstacle(boss)
        state.enemies.boss = None
        state.enemies.boss_defeated = True


def _update_jelly_bat_spawn_anim(boss):
    """Update the bat spawn animation from jelly boss (o -> O -> () -> bat)."""
    anim = boss.get('bat_spawn_anim')
    if anim is None or not anim.get('active'):
        return

    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)
    anim_duration = getattr(jelly_boss_cfg, 'spawn_anim_duration', 0.5) if jelly_boss_cfg else 0.5
    # ~5 fps, so for 0.5s total with 4 frames = ~0.6 game frames per step
    # But let's use at least 1 frame per step
    frames_per_anim_step = max(1, int(anim_duration * 5 / 4))  # 5 fps, 4 animation steps

    anim['timer'] += 1
    if anim['timer'] >= frames_per_anim_step:
        anim['timer'] = 0
        anim['frame'] += 1

        # Update character based on frame: 0=o, 1=O, 2=(), 3=spawn bat
        if anim['frame'] == 1:
            anim['char'] = 'O'
        elif anim['frame'] == 2:
            anim['char'] = '()'
        elif anim['frame'] >= 3:
            # Animation complete, spawn the bat
            _spawn_bat_from_jelly_boss(boss, anim)
            boss['bat_spawn_anim'] = None
            boss['spawned_bats'] = boss.get('spawned_bats', 0) + 1


def _spawn_bat_from_jelly_boss(boss, anim):
    """Spawn an actual bat from the jelly boss animation."""
    # Choose a random bat type based on current level
    level = state.game.level

    # Get tier weights from config (same logic as spawn_bat)
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

    # Determine special bat types (same logic as spawn_bat)
    armored = False
    diver = False
    spellcaster = False

    # Check for diver (any tier)
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

    # Create the bat at the animation position
    bat_data = {
        'x_pos': anim['x_pos'] - 4,  # Center the bat sprite
        'y_pos': anim['y_pos'],
        'direction': random.choice([-1, 1]),
        'tier': tier,
        'hp': hp,
        'max_hp': hp,
        'target_y': boss['y_pos'] + 8,  # Target below the boss
        'spawn_ts': clock.now(),
        'armored': armored,
        'diver': diver,
        'spellcaster': spellcaster,
        'from_boss': True,  # Mark as spawned from boss (no loot drop)
        'descending_past_boss': True,  # Still passing in front of boss
    }

    # Add diver-specific fields
    if diver:
        bat_data['diver_state'] = 'flying'
        bat_data['diver_home_y'] = bat_data['target_y']
        bat_data['dive_start_y'] = None
        bat_data['stun_end_time'] = None

    # Add spellcaster-specific fields
    if spellcaster:
        bat_data['spell_state'] = 'idle'
        bat_data['spell_cooldown'] = 0
        bat_data['casting_end_time'] = None
        # Determine known spells based on tier
        spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
        spells_by_tier = getattr(spellcaster_cfg, 'spells_by_tier', None) if spellcaster_cfg else None
        if spells_by_tier:
            if isinstance(spells_by_tier, dict):
                num_spells = spells_by_tier.get(tier, spells_by_tier.get(str(tier), 1))
            else:
                num_spells = getattr(spells_by_tier, str(tier), 1)
        else:
            num_spells = min(tier - 1, 3)
        all_spells = ['silence', 'repugnant_wind', 'exile']
        bat_data['known_spells'] = all_spells[:num_spells]

    # Add to spawn queue
    state.enemies.spawn_queue.append({'type': 'bat', 'data': bat_data})


def _convert_jelly_boss_to_obstacle(boss):
    """Convert dead Jelly Boss to a falling obstacle."""
    boss_cfg = get_boss_config()
    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)

    corpse_cfg = getattr(jelly_boss_cfg, 'corpse', None) if jelly_boss_cfg else None
    hp = getattr(corpse_cfg, 'hp', 80) if corpse_cfg else 80

    boss_center_x = boss['x_pos'] + 11  # Jelly boss is ~23 chars wide
    closest_lane = min(
        range(constants.layout.num_lanes), key=lambda lane: abs(constants.layout.lane_positions[lane] - boss_center_x)
    )

    obstacle_id = state.enemies.obstacle_id_counter
    state.enemies.obstacle_id_counter += 1

    state.enemies.obstacles.append(
        {
            'id': obstacle_id,
            'lane': closest_lane,
            'x_pos': boss['x_pos'],
            'y_pos': boss['y_pos'],
            'tier': 5,
            'hp': hp,
            'max_hp': hp,
            'sprite_width': 23,
            'is_boss_corpse': True,
            'is_jelly_boss_corpse': True,
        }
    )

    # Award score and XP
    score = getattr(jelly_boss_cfg, 'score', 1500) if jelly_boss_cfg else 1500
    xp = getattr(jelly_boss_cfg, 'xp', 150) if jelly_boss_cfg else 150
    add_score(score)

    for i in range(constants.layout.num_balls):
        if not state.birds.lost[i]:
            award_xp(i, xp // max(1, sum(1 for j in range(constants.layout.num_balls) if not state.birds.lost[j])))

    # Drop loot
    loot_cfg = getattr(boss_cfg, 'loot', None)
    loot_count = getattr(loot_cfg, 'count', 3) if loot_cfg else 3
    loot_tier = getattr(loot_cfg, 'tier', 3) if loot_cfg else 3

    loot_weights = constants.bat_enemy.loot_base_weights
    if isinstance(loot_weights, dict):
        tier_weights = loot_weights.get(loot_tier, loot_weights.get(str(loot_tier), [30, 35, 25, 10]))
    else:
        tier_weights = getattr(loot_weights, str(loot_tier), [30, 35, 25, 10])

    prestige = compute_prestige()
    adj_weights = adjust_rarity_weights(tier_weights, prestige)

    for i in range(loot_count):
        rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
        loot_type = choose_loot_type(rarity)

        lane_offset = i - loot_count // 2
        loot_lane = max(0, min(constants.layout.num_lanes - 1, closest_lane + lane_offset))

        state.items.loot_items.append(
            {
                'x_pos': constants.layout.lane_positions[loot_lane],
                'y_pos': boss['y_pos'] + 3,
                'type': loot_type,
                'rarity': rarity,
                'spawn_ts': clock.now(),
            }
        )
