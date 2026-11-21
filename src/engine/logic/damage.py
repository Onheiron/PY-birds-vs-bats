"""Bird damage computation and enemy death handling."""

import random

from src.core import constants, state
from src.engine import bird_kinds, clock, enemy_stats, events, stats
from src.engine.logic.drops import drop_loot
from src.engine.loot_tables import choose_loot_type, roll_drop_rarity
from src.engine.progression import add_score, award_xp, hp_scale
from src.entities.sprites import GLITCH, ORANGE

VS_STAT = {'bat': 'vs_bats', 'obstacle': 'vs_obstacles', 'elite': 'vs_elites'}


def active_speed_boost(bird_idx):
    """Speed points a bird gains right now from boosts (never from the gear)."""
    special = state.special
    boost = 0.0
    if state.birds.vy[bird_idx] == -1:
        boost += stats.bird(bird_idx, 'rise_speed_bonus') / 10
        if special.sprint_until.get(bird_idx, 0) > clock.now():
            boost += stats.bird(bird_idx, 'bounce_sprint') / 10
        if special.speed_boosts.get(bird_idx, 0) > 0:
            boost += 1
        if state.powerups.tailwind_active:
            boost += max(0, state.powerups.tailwind_up_bonus)
    return max(0.0, boost)


def calculate_bird_damage(bird_idx, target='bat'):
    """Calculate damage a bird deals to a ``target`` ('bat', 'obstacle' or 'elite'):

    TOT = round((GR_BONUS + DMG + BOOST + damage_bonus) × SPEED_FACTOR
                × damage_mult × (1 + vs_<target>) × crit)
    SPEED_FACTOR = 1 + speed_damage × (SPD − 1)   (speed_damage 1 → × SPD)

    Where:
    - GR = gear/speed (state.game.speed, 1-10)
    - DMG = the bird's damage stat
    - SPD = the bird's speed stat / 10
    - DMGBOOST/DMGNERF = damage modifiers
    - SPDBOOST/SPDNERF = speed modifiers
    """

    bird_color = state.birds.colors[bird_idx]

    # Base damage and base speed (in speed points) from the bird's stats
    base_dmg = stats.bird(bird_idx, 'damage')
    base_spd = stats.bird(bird_idx, 'speed') / 10

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
    if bird_kinds.is_phased_in(bird_idx):
        stealth_tangible_boost = getattr(constants.combat, 'stealth_tangible_dmg_boost', 4)
        dmg_boost += stealth_tangible_boost

    # Active speed boosts count (not the gear: that is gear_bonus): the rise
    # bonus, the sprint after a bounce, power boosts (Blue) and tailwinds
    spd_boost += active_speed_boost(bird_idx)

    # Scared birds have speed nerf (optional - could be damage nerf)
    if bird_idx in state.special.scared_birds:
        spd_nerf += 1

    # Calculate final damage using formula
    # TOT = round(((GR - gear_offset) * gear_coeff + (DMG + DMGBOOST - DMGNERF)) * (SPD + SPDBOOST - SPDNERF))
    dmg_formula = getattr(constants.combat, 'damage_formula', None)
    gear_offset = getattr(dmg_formula, 'gear_offset', 3) if dmg_formula else 3
    gear_coeff = getattr(dmg_formula, 'gear_coefficient', 0.1) if dmg_formula else 0.1
    gear_bonus = (gear - gear_offset) * gear_coeff
    effective_dmg = base_dmg + dmg_boost - dmg_nerf + stats.bird(bird_idx, 'damage_bonus')
    effective_spd = base_spd + spd_boost - spd_nerf

    # Ensure minimum values
    effective_dmg = max(0, effective_dmg)
    effective_spd = max(1, effective_spd)

    speed_factor = 1 + stats.bird(bird_idx, 'speed_damage') * (effective_spd - 1)
    raw = (gear_bonus + effective_dmg) * speed_factor
    raw *= stats.bird(bird_idx, 'damage_mult') * (1 + stats.bird(bird_idx, VS_STAT.get(target, 'vs_bats')))
    crit = stats.bird(bird_idx, 'crit_chance')
    if crit > 0 and random.random() < crit:
        raw *= stats.bird(bird_idx, 'crit_damage')
    total_damage = round(raw)

    # Minimum damage of 1
    return max(1, total_damage)


def handle_bat_death(bat, killer_bird_idx):
    """Handle bat death: score, loot drop, achievements."""
    tier = bat.get('tier', 1)
    bat_xp_per_tier = getattr(constants.combat, 'bat_destroy_xp_per_tier', 5)
    award_xp(killer_bird_idx, bat_xp_per_tier * tier * enemy_stats.get(bat, 'xp_mult'))
    add_score(bat.get('max_hp', 0) / hp_scale() * enemy_stats.get(bat, 'score_mult'))

    # Bats spawned by bosses NEVER drop loot (general rule)
    if not bat.get('from_boss'):
        # Drop loot at closest lane
        bat_center_x = bat['x_pos'] + 4
        closest_lane = min(
            range(constants.layout.num_lanes),
            key=lambda lane: abs(constants.layout.lane_positions[lane] - bat_center_x),
        )

        rarity = roll_drop_rarity('bat', tier)
        rarity = enemy_stats.upgrade_rarity(rarity, enemy_stats.get(bat, 'loot_rarity_bonus'))
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
    add_score(mini_bat.get('max_hp', 8 * hp_scale()) / hp_scale())

    # Bats spawned by bosses NEVER drop loot (general rule)
    if not mini_bat.get('from_boss'):
        rarity = roll_drop_rarity('mini_bat')
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
