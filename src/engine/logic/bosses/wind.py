"""Wind Boss (The Borders)."""

import random
import time

from src.core import constants, state
from src.engine.logic.bosses.common import get_boss_config
from src.engine.loot_tables import adjust_rarity_weights, choose_loot_type
from src.engine.progression import add_score, award_xp, compute_prestige


def spawn_wind_boss():
    """Spawn the Wind Boss for level 2-3."""
    wind_boss_cfg = getattr(constants, 'wind_boss', None)
    hp = getattr(wind_boss_cfg, 'hp', 120) if wind_boss_cfg else 120

    # Wind boss is wider (up to 26 chars) and taller (5 lines)
    boss_sprite_height = 5
    boss_sprite_width = 26
    base_x = (constants.layout.width - boss_sprite_width) // 2

    state.enemies.boss = {
        'x_pos': base_x,
        'base_x_pos': base_x,
        'y_pos': -boss_sprite_height,
        'hp': hp,
        'max_hp': hp,
        'state': 'descending',
        'anim_frame': 0,  # Index into animation sequence (0-9)
        'anim_timer': 0,  # Timer for animation steps
        'oscillation_dir': 1,
        'spawn_ts': time.time(),
        'boss_type': 'wind',
        'wind_phase': 'tailwind',  # 'tailwind' during pull up, 'headwind' during push down
    }
    state.enemies.boss_spawned = True
    state.enemies.bats = []
    state.enemies.mini_bats = []


def update_wind_boss():
    """Update Wind Boss state and behavior."""
    boss = state.enemies.boss
    if boss is None:
        return

    wind_boss_cfg = getattr(constants, 'wind_boss', None)
    boss_state = boss['state']

    if boss_state == 'descending':
        descent_speed = getattr(wind_boss_cfg, 'descent_speed', 8) if wind_boss_cfg else 8
        if state.game.frame_count % descent_speed == 0:
            boss['y_pos'] += 1
            if boss['y_pos'] >= 2:
                boss['state'] = 'active'
                boss['y_pos'] = 2

    elif boss_state == 'active':
        # Animation cycling through wing flap sequence
        anim_speed = getattr(wind_boss_cfg, 'anim_frames_per_step', 8) if wind_boss_cfg else 8
        boss['anim_timer'] = boss.get('anim_timer', 0) + 1

        if boss['anim_timer'] >= anim_speed:
            boss['anim_timer'] = 0
            boss['anim_frame'] = (boss['anim_frame'] + 1) % 10  # 10 frames in sequence

            # Determine wind phase based on animation frame
            # Frame 0 = max_up → headwind starts (obnoxious wind)
            # Frame 5 = max_down → tailwind starts
            if boss['anim_frame'] >= 5:
                boss['wind_phase'] = 'tailwind'
            else:
                boss['wind_phase'] = 'headwind'

        # Apply wind effects to all birds
        _apply_wind_boss_effect(boss)

        # Subtle oscillation
        oscillation_speed = getattr(wind_boss_cfg, 'oscillation_speed', 12) if wind_boss_cfg else 12
        oscillation_range = getattr(wind_boss_cfg, 'oscillation_range', 2) if wind_boss_cfg else 2
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
        _convert_wind_boss_to_obstacle(boss)
        state.enemies.boss = None
        state.enemies.boss_defeated = True


def _apply_wind_boss_effect(boss):
    """Apply tailwind or headwind effect from Wind Boss with gradual intensity."""
    wind_boss_cfg = getattr(constants, 'wind_boss', None)
    wind_phase = boss.get('wind_phase', 'tailwind')
    anim_frame = boss.get('anim_frame', 0)

    if wind_phase == 'tailwind':
        # Tailwind: frames 5-9 (max_down to pull_up_4)
        # Frame 5 = intensity 0, frame 9 = intensity 4 (max)
        intensity = anim_frame - 5  # 0 to 4
        max_intensity = 4

        tw_cfg = getattr(wind_boss_cfg, 'tailwind', None) if wind_boss_cfg else None
        up_min = getattr(tw_cfg, 'up_bonus_min', 1) if tw_cfg else 1
        up_max = getattr(tw_cfg, 'up_bonus_max', 3) if tw_cfg else 3
        down_min = getattr(tw_cfg, 'down_penalty_min', 0) if tw_cfg else 0
        down_max = getattr(tw_cfg, 'down_penalty_max', 2) if tw_cfg else 2

        # Interpolate based on intensity
        t = intensity / max_intensity if max_intensity > 0 else 0
        up_bonus = int(up_min + (up_max - up_min) * t)
        down_penalty = int(down_min + (down_max - down_min) * t)

        state.powerups.wind_boss_up_bonus = up_bonus
        state.powerups.wind_boss_down_penalty = down_penalty
    else:
        # Headwind: frames 0-4 (max_up to push_down_4)
        # Frame 0 = intensity 0, frame 4 = intensity 4 (max)
        intensity = anim_frame  # 0 to 4
        max_intensity = 4

        hw_cfg = getattr(wind_boss_cfg, 'headwind', None) if wind_boss_cfg else None
        up_min = getattr(hw_cfg, 'up_penalty_min', 1) if hw_cfg else 1
        up_max = getattr(hw_cfg, 'up_penalty_max', 2) if hw_cfg else 2
        down_min = getattr(hw_cfg, 'down_bonus_min', 1) if hw_cfg else 1
        down_max = getattr(hw_cfg, 'down_bonus_max', 3) if hw_cfg else 3

        # Interpolate based on intensity
        t = intensity / max_intensity if max_intensity > 0 else 0
        up_penalty = int(up_min + (up_max - up_min) * t)
        down_bonus = int(down_min + (down_max - down_min) * t)

        # Negative values = headwind
        state.powerups.wind_boss_up_bonus = -up_penalty
        state.powerups.wind_boss_down_penalty = -down_bonus


def _convert_wind_boss_to_obstacle(boss):
    """Convert dead Wind Boss to a falling obstacle."""
    boss_cfg = get_boss_config()
    wind_boss_cfg = getattr(constants, 'wind_boss', None)

    corpse_cfg = getattr(boss_cfg, 'corpse', None)
    hp = getattr(corpse_cfg, 'hp', 64) if corpse_cfg else 64

    boss_center_x = boss['x_pos'] + 13  # Wind boss is ~26 chars wide
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
            'sprite_width': 26,
            'is_boss_corpse': True,
            'is_wind_boss_corpse': True,
        }
    )

    # Clear wind effects
    state.powerups.wind_boss_up_bonus = 0
    state.powerups.wind_boss_down_penalty = 0

    # Award score and XP
    score = getattr(wind_boss_cfg, 'score', 1200) if wind_boss_cfg else 1200
    xp = getattr(wind_boss_cfg, 'xp', 120) if wind_boss_cfg else 120
    add_score(score)

    for i in range(constants.layout.num_balls):
        if not state.birds.lost[i]:
            award_xp(i, xp // max(1, sum(1 for j in range(constants.layout.num_balls) if not state.birds.lost[j])))

    # Drop loot
    loot_cfg = getattr(boss_cfg, 'loot', None)
    loot_count = getattr(loot_cfg, 'count', 3) if loot_cfg else 3
    loot_tier = getattr(loot_cfg, 'tier', 3) if loot_cfg else 3

    # Get tier loot weights from bat_enemy config
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

        # Spread loot across nearby lanes
        lane_offset = i - loot_count // 2
        loot_lane = max(0, min(constants.layout.num_lanes - 1, closest_lane + lane_offset))

        state.items.loot_items.append(
            {
                'x_pos': constants.layout.lane_positions[loot_lane],
                'y_pos': boss['y_pos'] + 2,
                'type': loot_type,
                'rarity': rarity,
                'spawn_ts': time.time(),
            }
        )
