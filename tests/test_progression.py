"""Levels, grades, gears and bird type lookups."""

import pytest

from src.core import constants, state
from src.engine import progression
from src.engine.birds import get_color_name
from src.engine.grades import compute_grade_from_xp
from src.entities.bird_types import BIRD_TYPES, BirdType, get_bird_type_by_color, get_color_for_bird_type


def test_level_milestones_grow_by_one_more_mile_each_level():
    milestones = progression.get_level_milestones()
    assert milestones[:6] == (3, 7, 12, 18, 25, 33)
    assert len(milestones) == constants.levels.total_levels
    steps = [b - a for a, b in zip(milestones, milestones[1:])]
    assert steps == list(range(4, 4 + len(steps)))


@pytest.mark.parametrize(
    'miles, expected',
    [
        (0, (1, 1, 1)),
        (2.99, (1, 1, 1)),
        (3, (2, 1, 2)),
        (7, (3, 1, 3)),
        (12, (4, 2, 1)),
        (150, (16, 6, 1)),
        (10_000, (18, 6, 3)),
    ],
)
def test_level_from_miles(miles, expected):
    assert progression.compute_level_from_miles(miles) == expected


def test_grades_rise_with_xp():
    order = ['D', 'C1', 'C2', 'B1', 'B2', 'A1', 'A2', 'S']
    seen = []
    for xp in range(0, 20_000, 25):
        label, _color = compute_grade_from_xp(xp)
        if not seen or seen[-1] != label:
            seen.append(label)
    assert seen == order[: len(seen)]
    assert seen[0] == 'D' and len(seen) >= 4


def test_gear_thresholds_are_increasing_and_match_gear_lookup():
    thresholds = [progression.calculate_gear_threshold(gear) for gear in range(2, 11)]
    assert thresholds == sorted(thresholds)
    assert progression.compute_gear_from_momentum(0) == 1
    assert progression.compute_gear_from_momentum(thresholds[0]) == 2
    assert progression.compute_gear_from_momentum(thresholds[0] - 1) == 1
    # The top gear depends on the world (speed.max_gear_by_world)
    caps = list(constants.speed.max_gear_by_world)
    for world in (1, 2, 6):
        state.game.level_group = world
        assert progression.compute_gear_from_momentum(10**12) == caps[world - 1]
    state.game.level_group = 1


def test_momentum_factor_is_negative_low_and_positive_high():
    state.init(seed=1)
    bottom = constants.layout.starting_line
    assert progression.compute_momentum_factor(bottom) == -1.0
    assert progression.compute_momentum_factor(1) == 2.0
    factors = [progression.compute_momentum_factor(y) for y in range(bottom, 0, -1)]
    assert factors == sorted(factors)


def test_every_bird_type_round_trips_through_its_colour():
    for bird_type in BIRD_TYPES:
        colour = BIRD_TYPES[bird_type]['color']
        assert get_bird_type_by_color(colour) == bird_type
        assert get_color_name(colour) == bird_type.lower()
    assert get_bird_type_by_color('not a colour') is None
    assert get_color_name('not a colour') == 'unknown'


def test_sentinel_bird_colours():
    assert get_color_for_bird_type(BirdType.STEALTH) == 'STEALTH'
    assert get_color_for_bird_type(BirdType.RAINBOW) == 'RAINBOW'
