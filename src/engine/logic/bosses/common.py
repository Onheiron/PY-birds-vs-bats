"""Shared boss helpers."""

import random
import time

from src.core import constants, state
from src.engine.loot_tables import adjust_rarity_weights, choose_loot_type
from src.engine.progression import add_score, award_xp, compute_prestige, get_level_milestones


def get_boss_config():
    """Get boss configuration."""
    return getattr(constants, 'boss', None)


def _get_miles_to_next_level():
    """Calculate miles remaining until next level transition."""

    milestones = get_level_milestones()
    current_level = state.game.level

    if current_level >= len(milestones):
        return float('inf')  # Max level reached

    next_threshold = milestones[current_level - 1] if current_level <= len(milestones) else milestones[-1]
    return max(0, next_threshold - state.game.miles)


def convert_boss_to_obstacle(boss):
    """Convert dead boss to a falling obstacle using BOSS_DEAD sprite."""
    boss_cfg = get_boss_config()

    # Get corpse HP from config (special boss corpse, not tier 4)
    corpse_cfg = getattr(boss_cfg, 'corpse', None)
    hp = getattr(corpse_cfg, 'hp', 64) if corpse_cfg else 64

    # Find closest lane to boss center
    boss_center_x = boss['x_pos'] + 9  # Boss is ~19 chars wide
    closest_lane = min(
        range(constants.layout.num_lanes), key=lambda lane: abs(constants.layout.lane_positions[lane] - boss_center_x)
    )

    # Assign unique ID
    obstacle_id = state.enemies.obstacle_id_counter
    state.enemies.obstacle_id_counter += 1

    state.enemies.obstacles.append(
        {
            'id': obstacle_id,
            'lane': closest_lane,
            'x_pos': boss['x_pos'],  # Keep exact X position for BOSS_DEAD sprite
            'y_pos': boss['y_pos'],
            'tier': 5,  # Special tier for boss corpse (not regular 1-4)
            'hp': hp,
            'max_hp': hp,
            'sprite_width': 19,  # Full boss sprite width
            'is_boss_corpse': True,  # Mark as boss corpse for special rendering
        }
    )

    # Award score and XP for defeating boss
    score = getattr(boss_cfg, 'score', 1000)
    xp = getattr(boss_cfg, 'xp', 100)
    add_score(score)

    # Award XP to all active birds
    for i in range(constants.layout.num_balls):
        if not state.birds.lost[i]:
            award_xp(i, xp // max(1, sum(1 for j in range(constants.layout.num_balls) if not state.birds.lost[j])))

    # Drop loot - boss drops 3 items with tier 3 weights
    loot_cfg = getattr(boss_cfg, 'loot', None)
    loot_count = getattr(loot_cfg, 'count', 3) if loot_cfg else 3
    loot_tier = getattr(loot_cfg, 'tier', 3) if loot_cfg else 3

    # Get tier 3 loot weights from bat_enemy config
    loot_weights = constants.bat_enemy.loot_base_weights
    if isinstance(loot_weights, dict):
        tier_weights = loot_weights.get(loot_tier, loot_weights.get(str(loot_tier), [30, 35, 25, 10]))
    else:
        tier_weights = getattr(loot_weights, str(loot_tier), [30, 35, 25, 10])

    # Adjust with prestige
    prestige = compute_prestige()
    adj_weights = adjust_rarity_weights(tier_weights, prestige)

    # Spawn loot items spread across lanes near boss
    for i in range(loot_count):
        rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
        loot_type = choose_loot_type(rarity)

        # Spread loot across nearby lanes
        lane_offset = i - loot_count // 2
        loot_lane = max(0, min(constants.layout.num_lanes - 1, closest_lane + lane_offset))

        state.items.loot_items.append(
            {
                'x_pos': constants.layout.lane_positions[loot_lane],
                'y_pos': boss['y_pos'] + 1,  # Just below boss
                'type': loot_type,
                'rarity': rarity,
                'spawn_ts': time.time(),
            }
        )
