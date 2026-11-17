"""Progression: gears, grades, miles, levels, prestige, score and momentum."""

import functools
import random

from src.core import constants, state
from src.engine import events
from src.engine.birds import transform_bird_to_s
from src.engine.grades import compute_grade_from_xp
from src.entities.sprites import (
    BERSERK,
    CLOCKWORK,
    COOKIE,
    DINOSAUR,
    FROSTY,
    GLITCH,
    GOLD,
    ORANGE,
    PATCHWORK,
    POISON,
    PURPLE,
    RAINBOW,
    ROCK,
    STEALTH,
    TWISTER,
    WHITE,
)
from src.services.sound import get_audio


def calculate_gear_threshold(gear):
    """Calculate momentum threshold for given gear level (1-10)."""
    base = float(constants.progression.level_score_base)
    factor = float(constants.progression.level_score_factor)
    return int(base ** (factor ** (gear + 1)))


def compute_gear_from_momentum(momentum):
    """Compute gear level (1-10) from momentum.

    Gear controls game speed. Uses exponential progression.
    """
    max_gear = getattr(constants.speed, 'max_speed', 10)

    gear = 1
    while momentum >= calculate_gear_threshold(gear + 1):
        gear += 1
        if gear >= max_gear:
            break
    return gear


def get_mph_for_speed(speed_level):
    """Get miles per hour for a given speed level.

    At speed 1: 40 mph
    At speed 5: 200 mph
    At speed 10: 400 mph
    """
    mph_per_level = getattr(constants.speed, 'mph_per_level', 40)
    return speed_level * mph_per_level


def get_level_milestones():
    """Get list of 18 level milestones in miles.

    Returns list of cumulative distances: [3, 7, 12, 18, 25, 33, ...]
    """
    total_levels = getattr(constants.levels, 'total_levels', 18)
    starting_distance = getattr(constants.levels, 'starting_distance', 3)
    return _level_milestones(total_levels, starting_distance)


@functools.lru_cache(maxsize=8)
def _level_milestones(total_levels, starting_distance):
    """Cumulative level distances; every level is one mile longer than the last."""
    milestones = []
    current = 0
    increment = starting_distance
    for _ in range(total_levels):
        current += increment
        milestones.append(current)
        increment += 1
    return tuple(milestones)


def compute_level_from_miles(miles):
    """Compute level (1-18) from miles traveled.

    Returns (level_number, group, sub) where:
    - level_number: 1-18
    - group: 1-6
    - sub: 1-3
    """
    milestones = get_level_milestones()
    levels_per_group = getattr(constants.levels, 'levels_per_group', 3)

    level = 1
    for i, threshold in enumerate(milestones):
        if miles >= threshold:
            level = i + 2  # Level 2 at first milestone, etc.
        else:
            break

    # Cap at max level
    level = min(level, len(milestones))

    # Calculate group and sub-level
    group = ((level - 1) // levels_per_group) + 1
    sub = ((level - 1) % levels_per_group) + 1

    return level, group, sub


def format_level_display(level, group, sub):
    """Format level for display as 'G-S' (e.g., '2-3')."""
    return f"{group}-{sub}"


def update_miles(delta_time):
    """Update miles traveled based on current speed and elapsed time.

    Args:
        delta_time: Time elapsed in seconds since last update

    Returns:
        True if level changed, False otherwise
    """
    if delta_time <= 0:
        return False

    # Block mile progression while boss is alive
    if state.enemies.boss is not None:
        return False

    # Get current speed and calculate mph
    mph = get_mph_for_speed(state.game.speed)

    # Convert mph to miles per second and add
    miles_per_second = mph / 3600.0
    state.game.miles += miles_per_second * delta_time

    # Check if level changed
    old_level = state.game.level
    new_level, new_group, new_sub = compute_level_from_miles(state.game.miles)

    if new_level != old_level:
        old_group = state.game.level_group
        state.game.level = new_level
        state.game.level_group = new_group
        state.game.level_sub = new_sub
        # Reset boss spawn flag for new level
        state.enemies.boss_spawned = False
        state.enemies.boss_defeated = False
        # Update music theme if biome changed
        if new_group != old_group:
            audio = get_audio()
            if audio:
                audio.update_music_for_biome(new_group)
        return True

    return False


def update_gear():
    """Update gear based on current momentum.

    Returns:
        True if gear changed, False otherwise
    """
    old_gear = state.game.speed
    new_gear = compute_gear_from_momentum(state.game.momentum)

    if new_gear != old_gear:
        state.game.speed = new_gear
        return True

    return False


def get_frame_sleep_for_speed(speed_level):
    """Get frame sleep time for given speed level.

    Interpolates between frame_sleep_at_speed_1 and frame_sleep_at_speed_10.
    """
    min_speed = getattr(constants.speed, 'min_speed', 1)
    max_speed = getattr(constants.speed, 'max_speed', 10)
    sleep_at_1 = getattr(constants.speed, 'frame_sleep_at_speed_1', 0.18)
    sleep_at_10 = getattr(constants.speed, 'frame_sleep_at_speed_10', 0.02)

    # Normalize speed to 0-1 range
    t = (speed_level - min_speed) / (max_speed - min_speed) if max_speed > min_speed else 0
    t = max(0, min(1, t))

    # Linear interpolation
    return sleep_at_1 + t * (sleep_at_10 - sleep_at_1)


def compute_prestige():
    """Compute prestige multiplier based on active bird grades and rarity."""
    total = 1.0

    # Rarity-based prestige bonuses
    # COMMON (0): yellow, red, blue, patchwork
    # UNCOMMON (+1): frosty, poison, berserk, purple, rock
    # RARE (+2): clockwork, cookie, stealth, twister
    # EPIC (+3): white, orange, gold
    # LEGENDARY (+4): dinosaur, glitch (random 1-7)
    # MYTHICAL (+5): rainbow
    rarity_bonuses = {
        # Common (+0) - yellow, red, blue, patchwork have no bonus
        PATCHWORK: 0.0,
        # Uncommon (+1)
        FROSTY: 1.0,
        POISON: 1.0,
        BERSERK: 1.0,
        PURPLE: 1.0,
        ROCK: 1.0,
        # Rare (+2)
        CLOCKWORK: 2.0,
        COOKIE: 2.0,
        STEALTH: 2.0,
        TWISTER: 2.0,
        # Epic (+3)
        WHITE: 3.0,
        ORANGE: 3.0,
        GOLD: 3.0,
        # Legendary (+4)
        DINOSAUR: 4.0,
        GLITCH: 0.0,  # Handled separately (random 1-7)
        # Mythical (+5)
        RAINBOW: 5.0,
    }

    for i in range(len(state.birds.per_bird_xp)):
        if state.birds.lost[i]:
            continue

        bird_color = state.birds.colors[i]

        # GLITCH birds contribute random prestige
        if bird_color == GLITCH:
            total += float(random.randint(1, 7))
            continue

        # Add rarity bonus
        rarity_bonus = rarity_bonuses.get(bird_color, 0.0)
        total += rarity_bonus

        # Add grade bonus
        label, _ = compute_grade_from_xp(state.birds.per_bird_xp[i])
        add = constants.prestige.modifiers.get(label, 0.0)
        total += add

    return float(total)


def add_score(amount, by_bird=None):
    """Add score (always increases). Used for leaderboard/achievements.

    This function ONLY affects score. Momentum is handled separately by update_momentum().
    """
    amt = float(amount)
    prestige = compute_prestige()
    score_amount = amt * prestige

    state.game.score += score_amount * 0.2

    if by_bird is not None and 0 <= int(by_bird) < len(state.birds.per_bird_xp):
        xp_award = int(max(0, int(amount)))
        state.birds.per_bird_xp[int(by_bird)] += xp_award
        transform_bird_to_s(int(by_bird))

    events.emit('score_changed', score=state.game.score)


def compute_momentum_factor(y_pos):
    """Compute MOMENTUM factor based on Y position (center of mass).

    Returns factor for momentum change:
    - -1.0 at starting_line (bottom) → momentum decreases
    -  0.0 at zero height (configurable, default 0.33)
    - +2.0 at ceiling (top) → momentum increases fast
    """
    starting_line = constants.layout.starting_line
    ceiling = 1

    # Get zero height from config (0.0 = bottom, 1.0 = top)
    zero_fraction = getattr(constants.speed, 'momentum_zero_height', 0.33)
    zero_point = starting_line - (starting_line - ceiling) * zero_fraction

    if y_pos >= starting_line:
        return -1.0
    if y_pos >= zero_point:
        # Between starting_line and zero point: -1.0 -> 0.0
        t = (starting_line - y_pos) / (starting_line - zero_point)
        return -1.0 + t * 1.0
    if y_pos > ceiling:
        # Between zero point and ceiling: 0.0 -> +2.0
        t = (zero_point - y_pos) / (zero_point - ceiling)
        return t * 2.0
    return 2.0


def update_momentum(momentum_factor):
    """Update momentum based on center of mass momentum factor.

    momentum_factor: -1.0 (bottom) to +2.0 (top), 0 at 1/3 height
    NO prestige, NO other factors - ONLY center of mass affects momentum.
    """
    gain_mult = getattr(constants.speed, 'momentum_gain_multiplier', 1.0)

    # Apply momentum factor directly (already centered at 0)
    delta = momentum_factor * gain_mult
    state.game.momentum += delta

    # Clamp to minimum
    state.game.momentum = max(1.0, state.game.momentum)

    gear_changed = update_gear()

    if gear_changed:
        audio = get_audio()
        if audio:
            # Update tempo for new gear (higher gear = faster tempo)
            audio.update_tempo_for_gear(state.game.speed)


def award_xp(bird_idx, xp_amount):
    """Credit XP to a bird without affecting score."""
    bi = int(bird_idx)
    if bi < 0 or bi >= len(state.birds.per_bird_xp):
        return
    xp = int(max(0, int(xp_amount)))
    # Cookie birds gain 1.5x XP (XP bank)
    if state.birds.colors[bi] == COOKIE:
        xp = int(xp * 1.5)
    state.birds.per_bird_xp[bi] += xp
    transform_bird_to_s(bi)


def deduct_momentum(amount):
    """Deduct momentum safely (used for swaps). Score is NOT affected."""
    state.game.momentum = max(0, state.game.momentum - amount)

    # Update gear if momentum changed significantly
    gear_changed = update_gear()

    if gear_changed:
        audio = get_audio()
        if audio:
            # Update tempo for new gear (higher gear = faster tempo)
            audio.update_tempo_for_gear(state.game.speed)
