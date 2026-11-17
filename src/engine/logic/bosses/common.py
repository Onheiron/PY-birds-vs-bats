"""Shared boss helpers."""

from src.core import constants, state
from src.engine import clock
from src.engine.logic.drops import drop_loot
from src.engine.loot_tables import choose_loot_type, roll_drop_rarity
from src.engine.progression import add_score, award_xp


def get_boss_config():
    """Get boss configuration."""
    return getattr(constants, 'boss', None)


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

    for i in range(loot_count):
        rarity = roll_drop_rarity('boss')
        loot_type = choose_loot_type(rarity)

        # Spread loot across nearby lanes
        lane_offset = i - loot_count // 2
        loot_lane = max(0, min(constants.layout.num_lanes - 1, closest_lane + lane_offset))

        drop_loot(
            {
                'x_pos': constants.layout.lane_positions[loot_lane],
                'y_pos': boss['y_pos'] + 1,  # Just below boss
                'type': loot_type,
                'rarity': rarity,
                'spawn_ts': clock.now(),
            },
            'boss',
        )
