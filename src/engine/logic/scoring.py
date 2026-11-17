"""Score, momentum and frame pacing."""

import random

from src.core import constants, state
from src.engine import stats
from src.engine.physics import moves_this_tick
from src.engine.progression import add_score, compute_momentum_factor, update_momentum
from src.entities.sprites import GLITCH, GOLD


def _compute_score_position_multiplier(y_pos):
    """Compute SCORE multiplier based on Y position.

    Returns multiplier for score calculation:
    - x0.5 at starting_line (bottom)
    - x1.0 at breakeven height (configurable, default 0.33)
    - x2.0 at ceiling (top)
    """
    starting_line = constants.layout.starting_line
    ceiling = 1

    # Get breakeven height from config (0.0 = bottom, 1.0 = top)
    breakeven_fraction = getattr(constants.score, 'score_breakeven_height', 0.33)
    breakeven_point = starting_line - (starting_line - ceiling) * breakeven_fraction

    if y_pos >= starting_line:
        return 0.5
    if y_pos >= breakeven_point:
        t = (starting_line - y_pos) / (starting_line - breakeven_point)
        return 0.5 + t * 0.5
    if y_pos > ceiling:
        t = (breakeven_point - y_pos) / (breakeven_point - ceiling)
        return 1.0 + t * 1.0
    return 2.0


def _compute_center_of_mass():
    """Calculate center of mass (weighted average Y position of active birds).

    Weight = bird speed × its weight stat. Returns None if no active birds.
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue
        bird_y = state.birds.y[i]
        # Skip dormant birds
        if bird_y >= constants.layout.height:
            continue

        weight = max(1, state.birds.speeds[i]) * stats.bird(i, 'weight')
        weighted_sum += bird_y * weight
        total_weight += weight

    if total_weight <= 0:
        return None

    return weighted_sum / total_weight


def update_score_tick():
    """Award score and momentum based on active birds (called each frame).

    SCORE = sum of (speed × type × grade) × score_mult × level_mult × prestige
    MOMENTUM = momentum_factor only (from center of mass)
    """

    # Calculate center of mass once
    center_y = _compute_center_of_mass()
    if center_y is None:
        return  # No active birds

    # Score multiplier: 0.5 (bottom) to 2.0 (top)
    score_mult = _compute_score_position_multiplier(center_y)

    # Momentum factor: -1.0 (bottom) to +2.0 (top), 0 at 1/3 height
    momentum_factor = compute_momentum_factor(center_y)

    # Level multiplier (higher levels = more points)
    level = state.game.level
    level_mult = 1.0 + (level - 1) * 0.1  # Level 1 = 1.0, Level 18 = 2.7

    # Calculate total score from all active birds

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        current_speed = state.birds.speeds[i]
        bird_color = state.birds.colors[i]
        bird_y = state.birds.y[i]

        # Skip orange birds in dormant state (y=999)
        if bird_y >= constants.layout.height:
            continue

        # Only on move frames (based on bird speed)
        if not moves_this_tick(current_speed):
            continue

        # Type multiplier
        type_mult = stats.bird(i, 'score_mult')

        # Glitch has random multiplier
        if bird_color == GLITCH:
            glitch_min = getattr(constants.combat, 'glitch_dmg_multiplier_min', 1)
            glitch_max = getattr(constants.combat, 'glitch_dmg_multiplier_max', 8)
            type_mult = random.uniform(glitch_min * 0.5, glitch_max * 0.5)

        # Grade multiplier based on bird's XP
        grade_mult = 1 + stats.bird(i, 'score_grade_bonus')

        # Gold bird special handling
        if bird_color == GOLD:
            base_score = getattr(constants.loot, 'gold_bird_score_per_tick', 100)
        else:
            base_score = current_speed * type_mult * grade_mult

        # SCORE: base × score_mult × level_mult (prestige applied in add_score)
        final_score = base_score * score_mult * level_mult
        add_score(final_score, by_bird=i)

    # MOMENTUM: depends ONLY on center of mass (momentum_factor: -1 to +2)
    update_momentum(momentum_factor)
