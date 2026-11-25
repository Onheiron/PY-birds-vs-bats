"""Progression: gears, grades, miles, levels, prestige, score and momentum."""

import functools
import random

from src.core import constants, state
from src.engine import events, stats
from src.engine.birds import transform_bird_to_s
from src.entities.sprites import (
    GLITCH,
)
from src.services.sound import get_audio


def calculate_gear_threshold(gear):
    """Calculate momentum threshold for given gear level (1-10)."""
    base = float(constants.progression.level_score_base)
    factor = float(constants.progression.level_score_factor)
    return int(base ** (factor ** (gear + 1)))


def gear_cap():
    """The highest gear now: speed.max_speed, lowered by the world's speed.max_gear_by_world."""
    max_gear = getattr(constants.speed, 'max_speed', 10)
    by_world = getattr(constants.speed, 'max_gear_by_world', None)
    if by_world:
        by_world = list(by_world)
        max_gear = min(max_gear, int(by_world[min(max(1, state.game.level_group), len(by_world)) - 1]))
    return max_gear


def momentum_cap():
    """The most momentum there can be now: just under the next gear past the cap."""
    cap = gear_cap()
    if cap >= getattr(constants.speed, 'max_speed', 10):
        return float('inf')
    return float(calculate_gear_threshold(cap + 1) - 1)


def compute_gear_from_momentum(momentum):
    """Compute gear level (1-10) from momentum.

    Gear controls game speed. Uses exponential progression.
    """
    max_gear = getattr(constants.speed, 'max_speed', 10)
    # Each world can cap the gear (speed.max_gear_by_world): speed ramps up world by world
    by_world = getattr(constants.speed, 'max_gear_by_world', None)
    if by_world:
        by_world = list(by_world)
        max_gear = min(max_gear, int(by_world[min(max(1, state.game.level_group), len(by_world)) - 1]))

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


def compute_prestige():
    """Compute prestige multiplier based on active bird grades and rarity."""
    total = 1.0

    for i in range(len(state.birds.per_bird_xp)):
        if state.birds.lost[i]:
            continue

        bird_color = state.birds.colors[i]

        # GLITCH birds contribute random prestige
        if bird_color == GLITCH:
            total += float(random.randint(1, 7))
            continue

        # Kind of bird + grade (bird_stats.types / bird_stats.growth)
        total += stats.bird(i, 'prestige')

    # Flock bonuses from cards and pacts
    total = (total + stats.flock('prestige_bonus')) * stats.flock('prestige_mult')
    return float(total)


def flock_alive():
    """Your living birds (a zombie is not yours any more)."""
    from src.entities.sprites import ZOMBIE

    birds = state.birds
    return sum(1 for i in range(len(birds.colors)) if not birds.lost[i] and birds.colors[i] != ZOMBIE)


def flock_bonus():
    """(multiplier, label) of the flock bonus: more living birds, more score (score.flock_bonus)."""
    alive = flock_alive()
    for entry in getattr(constants.score, 'flock_bonus', None) or []:
        entry = entry if isinstance(entry, dict) else vars(entry)
        if alive >= int(entry.get('birds', 0)):
            return float(entry.get('mult', 1.0)), str(entry.get('label', 'FLOCK'))
    return 1.0, 'FLOCK'


def add_score(amount, by_bird=None):
    """Add score (always increases). Used for leaderboard/achievements.

    This function ONLY affects score. Momentum is handled separately by update_momentum().
    """
    amt = float(amount)
    prestige = compute_prestige()
    score_amount = amt * prestige * flock_bonus()[0]

    state.game.score += score_amount * 0.2

    if by_bird is not None and 0 <= int(by_bird) < len(state.birds.per_bird_xp):
        # Moving earns XP too: as much as the score, × progression.move_xp_factor
        award_xp(int(by_bird), max(0.0, amt) * float(getattr(constants.progression, 'move_xp_factor', 1.0)))

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
    loss_mult = getattr(constants.speed, 'momentum_loss_multiplier', gain_mult)

    # Apply momentum factor directly (already centered at 0): growing and falling have their own pace
    delta = momentum_factor * (gain_mult if momentum_factor >= 0 else loss_mult)
    state.game.momentum += delta

    # Clamp to minimum, and to the top of the highest gear this world allows: momentum
    # gathered over the cap would make the gear jump when the next world lifts it
    state.game.momentum = max(1.0, min(state.game.momentum, momentum_cap()))

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
    # Some birds learn faster (Cookie: ×1.5, Quick Study cards...). Fractions of a
    # point are kept for the next award, so small bonuses are not lost to rounding.
    carry = state.special.xp_carry
    from src.engine import synergies

    gain = stats.bird(bi, 'xp_gain') + synergies.xp_bonus(bi)
    xp = max(0.0, float(xp_amount)) * gain + carry.get(bi, 0.0)
    whole = int(xp)
    carry[bi] = xp - whole
    state.birds.per_bird_xp[bi] += whole
    transform_bird_to_s(bi)


def hp_scale():
    """HP and damage are on a ×hp_scale scale; XP and score derived from them divide by it."""
    return getattr(constants.combat, 'hp_scale', 1) or 1


def award_damage_xp(bird_idx, damage, source='contact', target='enemy'):
    """XP for dealing ``damage`` (one XP per hp_scale points of damage).

    ``source`` ('contact', 'shot', 'dot') and ``target`` ('enemy', 'boss') only
    describe the hit for the damage_dealt event.
    """
    award_xp(bird_idx, damage / hp_scale())
    if 0 <= bird_idx < len(state.birds.colors):
        from src.entities.bird_types import get_bird_type_by_color

        kind = get_bird_type_by_color(state.birds.colors[bird_idx])
        events.emit('damage_dealt', bird=bird_idx, kind=kind, source=source, target=target, amount=damage)


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
