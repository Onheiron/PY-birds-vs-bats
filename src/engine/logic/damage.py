"""Bird damage computation and enemy death handling."""

import random

from src.core import constants, state
from src.engine import clock, events
from src.engine.logic.drops import drop_loot
from src.engine.loot_tables import adjust_rarity_weights, choose_loot_type
from src.engine.progression import add_score, award_xp, compute_prestige
from src.entities.bird_types import get_bird_type_by_color
from src.entities.sprites import BLUE, GLITCH, ORANGE, STEALTH


def calculate_bird_damage(bird_idx):
    """Calculate damage a bird deals using formula:
    TOT = round(((GR * 0.1) + (DMG + DMGBOOST - DMGNERF)) * (SPD + SPDBOOST - SPDNERF))

    Where:
    - GR = gear/speed (state.game.speed, 1-10)
    - DMG = base damage from config (constants.birds.damage)
    - SPD = base speed from config (constants.birds.speed)
    - DMGBOOST/DMGNERF = damage modifiers
    - SPDBOOST/SPDNERF = speed modifiers
    """

    bird_color = state.birds.colors[bird_idx]

    # Get bird type name for config lookup
    bird_type = get_bird_type_by_color(bird_color)
    if bird_type is None:
        # Fallback for special colors like STEALTH
        if bird_color == STEALTH:
            bird_type = 'STEALTH'
        else:
            bird_type = 'YELLOW'  # Default fallback

    # Get type name in lowercase for config lookup
    type_name = bird_type.lower()

    # Get base stats from config
    dmg_config = getattr(constants.birds, 'damage', {})
    spd_config = getattr(constants.birds, 'speed', {})

    # Handle both dict and namespace
    if hasattr(dmg_config, '__getitem__'):
        base_dmg = dmg_config.get(type_name, 1)
    else:
        base_dmg = getattr(dmg_config, type_name, 1)

    if hasattr(spd_config, '__getitem__'):
        base_spd = spd_config.get(type_name, 2)
    else:
        base_spd = getattr(spd_config, type_name, 2)

    # Get gear (speed level 1-10)
    gear = state.game.speed

    # Initialize boost/nerf values
    dmg_boost = 0
    dmg_nerf = 0
    spd_boost = 0
    spd_nerf = 0

    # Special case: Orange does instant kill (very high damage)
    if bird_color == ORANGE:
        return 9999

    # Special case: Glitch has random multiplier
    if bird_color == GLITCH:
        glitch_min = getattr(constants.combat, 'glitch_dmg_multiplier_min', 1)
        glitch_max = getattr(constants.combat, 'glitch_dmg_multiplier_max', 8)
        random_mult = random.randint(glitch_min, glitch_max)
        base_dmg *= random_mult

    # Special case: Stealth when tangible (in stealth_timers) gets damage boost
    if bird_color == STEALTH and bird_idx in state.special.stealth_timers:
        stealth_tangible_boost = getattr(constants.combat, 'stealth_tangible_dmg_boost', 4)
        dmg_boost += stealth_tangible_boost

    # Blue power gives speed boost
    if bird_color == BLUE and state.birds.power_used[bird_idx]:
        spd_boost += 1

    # Scared birds have speed nerf (optional - could be damage nerf)
    if bird_idx in state.special.scared_birds:
        spd_nerf += 1

    # Calculate final damage using formula
    # TOT = round(((GR - gear_offset) * gear_coeff + (DMG + DMGBOOST - DMGNERF)) * (SPD + SPDBOOST - SPDNERF))
    dmg_formula = getattr(constants.combat, 'damage_formula', None)
    gear_offset = getattr(dmg_formula, 'gear_offset', 3) if dmg_formula else 3
    gear_coeff = getattr(dmg_formula, 'gear_coefficient', 0.1) if dmg_formula else 0.1
    gear_bonus = (gear - gear_offset) * gear_coeff
    effective_dmg = base_dmg + dmg_boost - dmg_nerf
    effective_spd = base_spd + spd_boost - spd_nerf

    # Ensure minimum values
    effective_dmg = max(0, effective_dmg)
    effective_spd = max(1, effective_spd)

    total_damage = round((gear_bonus + effective_dmg) * effective_spd)

    # Minimum damage of 1
    return max(1, total_damage)


def handle_bat_death(bat, killer_bird_idx):
    """Handle bat death: score, loot drop, achievements."""
    tier = bat.get('tier', 1)
    bat_xp_per_tier = getattr(constants.combat, 'bat_destroy_xp_per_tier', 5)
    award_xp(killer_bird_idx, bat_xp_per_tier * tier)
    add_score(bat.get('max_hp', 0))

    # Bats spawned by bosses NEVER drop loot (general rule)
    if not bat.get('from_boss'):
        # Drop loot at closest lane
        bat_center_x = bat['x_pos'] + 4
        closest_lane = min(
            range(constants.layout.num_lanes),
            key=lambda lane: abs(constants.layout.lane_positions[lane] - bat_center_x),
        )

        prestige = compute_prestige()
        base_weights = getattr(constants.loot, 'base_rarity_weights', [1, 0.1, 0.01, 0.001, 0.0001, 0.00001])
        if isinstance(base_weights, list):
            pass
        else:
            base_weights = [1, 0.1, 0.01, 0.001, 0.0001, 0.00001]
        adj_weights = adjust_rarity_weights(base_weights, prestige)
        # 6 rarity tiers: common, uncommon, rare, epic, legendary, mythical
        rarity = random.choices(['common', 'uncommon', 'rare', 'epic', 'legendary', 'mythical'], weights=adj_weights)[0]
        loot_type = choose_loot_type(rarity)

        drop_loot(
            {
                'x_pos': constants.layout.lane_positions[closest_lane],
                'y_pos': bat['y_pos'],
                'type': loot_type,
                'rarity': rarity,
                'spawn_ts': clock.now(),
            },
            'bat',
        )

    # Notify achievements
    events.emit('bat_killed', bat=bat, tier=tier, killer=killer_bird_idx)
    state.enemies.bats.remove(bat)


def handle_mini_bat_death(mini_bat, killer_bird_idx):
    """Handle mini bat (tier 0) death: score, loot drop, XP."""
    tier = mini_bat.get('tier', 0)
    bat_xp_per_tier = getattr(constants.combat, 'bat_destroy_xp_per_tier', 5)
    # Tier 0 gives less XP but still something
    award_xp(killer_bird_idx, max(1, bat_xp_per_tier * tier) if tier > 0 else 5)
    add_score(mini_bat.get('max_hp', 8))

    # Bats spawned by bosses NEVER drop loot (general rule)
    if not mini_bat.get('from_boss'):
        # Drop loot based on tier 0 loot weights
        loot_weights = constants.bat_enemy.loot_base_weights
        if isinstance(loot_weights, dict):
            tier_weights = loot_weights.get(0, loot_weights.get('0', [80, 15, 5, 0]))
        else:
            tier_weights = getattr(loot_weights, '0', [80, 15, 5, 0])

        # Adjust with prestige
        prestige = compute_prestige()
        adj_weights = adjust_rarity_weights(tier_weights, prestige)
        rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
        loot_type = choose_loot_type(rarity)

        # Drop loot at mini bat position (find closest lane)
        mb_x = mini_bat['x_pos']
        closest_lane = min(
            range(constants.layout.num_lanes), key=lambda lane: abs(constants.layout.lane_positions[lane] - mb_x)
        )

        drop_loot(
            {
                'x_pos': constants.layout.lane_positions[closest_lane],
                'y_pos': mini_bat['y_pos'],
                'type': loot_type,
                'rarity': rarity,
                'spawn_ts': clock.now(),
            },
            'mini_bat',
        )

    events.emit('mini_bat_killed', bat=mini_bat, killer=killer_bird_idx)
    state.enemies.mini_bats.remove(mini_bat)
