"""Bat movement and behaviours: divers, spellcasters and their spells."""

import random
import time as time

from src.core import constants, state
from src.engine import bird_kinds, clock, enemy_stats
from src.engine.logic import afflictions
from src.entities.sprites import DINOSAUR, ORANGE, PURPLE


def per_tick(chance_per_second):
    """A chance per second turned into a chance per tick."""
    return chance_per_second * getattr(constants.timing, 'base_sleep', 0.033)


def _move_horizontally(bat):
    """Fly sideways: ``move_step`` columns every few ticks (fewer with a higher speed stat)."""
    speed = enemy_stats.get(bat, 'speed')
    interval = 3 if speed == 1 else max(1, int(3 / speed + 1e-9))
    if state.game.frame_count % interval:
        return
    step = max(1, int(enemy_stats.get(bat, 'move_step')))
    next_x = bat['x_pos'] + bat['direction'] * step
    if _check_bat_can_move(bat, next_x):
        bat['x_pos'] = next_x
        if bat['x_pos'] <= 0:
            bat['x_pos'] = 0
            bat['direction'] = 1
        elif bat['x_pos'] >= constants.layout.width - 8:
            bat['x_pos'] = constants.layout.width - 8
            bat['direction'] = -1
    else:
        bat['direction'] *= -1


def update_bat_positions():
    """Update positions of all bats (horizontal wave + vertical descent) and their abilities."""
    for bat in state.enemies.bats[:]:
        # Frozen bats move at a fraction of their speed
        slow = afflictions.slow_factor(bat)
        if slow < 1 and state.game.frame_count % max(1, round(1 / slow)) != 0:
            continue

        kinds = enemy_stats.bat_kinds(bat)
        _move_horizontally(bat)
        if 'diver' in kinds:
            _update_diver_bat(bat)
            continue  # divers handle their own height
        if 'spellcaster' in kinds:
            _update_spellcaster_bat(bat)
        for kind in kinds:
            ability = ABILITIES.get(kind)
            if ability:
                ability(bat)

        # Vertical descent to its height
        vert_interval = max(1, int(enemy_stats.get(bat, 'descent_interval')))
        if state.game.frame_count % vert_interval == 0 and bat['y_pos'] < bat['target_y']:
            bat['y_pos'] += 1


# Kind -> ability run every tick (new kinds add theirs here)
ABILITIES = {}


def _update_diver_bat(bat):
    """Diver: flying, diving (dive_rows rows, one every dive_interval ticks), stunned, returning."""
    diver_state = bat.get('diver_state', 'flying')
    if diver_state == 'flying':
        if state.game.frame_count % max(1, int(enemy_stats.get(bat, 'descent_interval'))) == 0:
            if bat['y_pos'] < bat['target_y']:
                bat['y_pos'] += 1
        ready = clock.now() >= bat.get('ability_ready', 0)
        if (
            ready
            and bat['y_pos'] >= bat['target_y']
            and random.random() < per_tick(enemy_stats.get(bat, 'ability_chance'))
        ):
            bat['diver_state'] = 'diving'
            bat['dive_start_y'] = bat['y_pos']

    elif diver_state == 'diving':
        if state.game.frame_count % max(1, int(enemy_stats.get(bat, 'dive_interval'))) == 0:
            bat['y_pos'] += 1
        dive_start = bat.get('dive_start_y', bat.get('diver_home_y', 5))
        if (
            bat['y_pos'] >= dive_start + enemy_stats.get(bat, 'dive_rows')
            or bat['y_pos'] >= constants.layout.starting_line - 3
        ):
            bat['diver_state'] = 'stunned'
            bat['stun_end_time'] = clock.now() + enemy_stats.get(bat, 'dive_stun')

    elif diver_state == 'stunned':
        if clock.now() >= bat.get('stun_end_time', 0):
            bat['diver_state'] = 'returning'

    elif diver_state == 'returning':
        if state.game.frame_count % max(1, int(enemy_stats.get(bat, 'return_interval'))) == 0:
            home_y = bat.get('diver_home_y', bat['target_y'])
            if bat['y_pos'] > home_y:
                bat['y_pos'] -= 1
            else:
                bat['diver_state'] = 'flying'
                bat['dive_start_y'] = None
                bat['ability_ready'] = clock.now() + enemy_stats.get(bat, 'ability_interval')


def _update_spellcaster_bat(bat):
    """Spellcaster: casts a known spell (ability_chance per second, ability_interval apart)."""
    now = clock.now()
    if bat.get('spell_state', 'idle') == 'casting':
        if now >= bat.get('casting_end_time', 0):
            _apply_spell_effect(bat)
            bat['spell_state'] = 'idle'
            bat['spell_cooldown'] = now + enemy_stats.get(bat, 'ability_interval')
        return
    if now < bat.get('spell_cooldown', 0):
        return
    # On screen and at its height
    if bat['y_pos'] < 0 or bat['y_pos'] < bat['target_y']:
        return
    if random.random() < per_tick(enemy_stats.get(bat, 'ability_chance')):
        bat['spell_state'] = 'casting'
        bat['casting_end_time'] = now + enemy_stats.get(bat, 'cast_time')
        bat['current_spell'] = random.choice(bat.get('known_spells', ['silence']))


def _apply_spell_effect(bat):
    """Apply the effect of the spell the bat just cast, on the lanes under it."""
    spell = bat.get('current_spell', 'silence')
    tier = bat.get('tier', 2)
    affected_lanes = _get_bat_affected_lanes(bat)
    now = clock.now()

    if spell == 'silence':
        # No powers in those lanes
        duration = enemy_stats.get(bat, 'silence_time')
        for lane in affected_lanes:
            state.spells.silenced_lanes[lane] = {'end_time': now + duration, 'caster_tier': tier}

    elif spell == 'repugnant_wind':
        # Reverse tailwind: faster falls, slower climbs
        duration = enemy_stats.get(bat, 'wind_time')
        push = enemy_stats.get(bat, 'wind_push')
        for lane in affected_lanes:
            state.spells.repugnant_wind_lanes[lane] = {
                'end_time': now + duration,
                'speed_boost': push,
                'speed_nerf': push,
            }

    elif spell == 'exile':
        # Swap birds: highest damage potential in affected lanes <-> lowest outside
        _cast_exile_spell(affected_lanes)


def _get_bat_affected_lanes(bat):
    """Get the lanes affected by a bat's spell (based on bat position)."""
    bat_left = bat['x_pos']
    bat_right = bat['x_pos'] + 8  # Bat sprite width

    affected_lanes = []
    for lane_idx in range(constants.layout.num_lanes):
        lane_x = constants.layout.lane_positions[lane_idx]
        # Check if lane overlaps with bat
        lane_left = lane_x - 2
        lane_right = lane_x + 2
        if not (bat_right < lane_left or bat_left > lane_right):
            affected_lanes.append(lane_idx)

    return affected_lanes


def _calculate_bird_damage_potential(bird_idx):
    """Calculate a bird's damage potential for exile spell targeting."""
    if state.birds.lost[bird_idx]:
        return -1  # Lost birds have no potential

    # Simple formula: speed * (1 if moving up else 0.5) + tier bonus

    color = state.birds.colors[bird_idx]
    speed = state.birds.speeds[bird_idx]
    vy = state.birds.vy[bird_idx]

    # Base potential from speed and direction
    direction_mult = 1.5 if vy == -1 else 0.5
    potential = speed * direction_mult

    # Color bonuses for high-damage birds
    if color == ORANGE:
        potential += 10  # One-hit kill bird
    elif color == DINOSAUR:
        potential += 5  # Multi-hit bird
    elif color == PURPLE:
        potential += 3  # Charging bird

    return potential


def _cast_exile_spell(affected_lanes):
    """Cast exile spell: swap highest damage bird in lanes with lowest outside."""

    # Find bird with highest damage potential in affected lanes
    best_bird_idx = None
    best_potential = -1

    for bird_idx in range(constants.layout.num_balls):
        if state.birds.lost[bird_idx]:
            continue
        bird_lane = state.birds.random_lanes[bird_idx]
        if bird_lane in affected_lanes:
            potential = _calculate_bird_damage_potential(bird_idx)
            if potential > best_potential:
                best_potential = potential
                best_bird_idx = bird_idx

    if best_bird_idx is None:
        return  # No bird to exile

    # Find bird with lowest damage potential outside affected lanes (or empty lane)
    worst_bird_idx = None
    worst_potential = float('inf')
    empty_lane = None

    for bird_idx in range(constants.layout.num_balls):
        if state.birds.lost[bird_idx]:
            continue
        bird_lane = state.birds.random_lanes[bird_idx]
        if bird_lane not in affected_lanes:
            potential = _calculate_bird_damage_potential(bird_idx)
            if potential < worst_potential:
                worst_potential = potential
                worst_bird_idx = bird_idx

    # Also check for empty lanes outside affected lanes
    occupied_lanes = set()
    for bird_idx in range(constants.layout.num_balls):
        if not state.birds.lost[bird_idx]:
            occupied_lanes.add(state.birds.random_lanes[bird_idx])

    for lane_idx in range(constants.layout.num_lanes):
        if lane_idx not in affected_lanes and lane_idx not in occupied_lanes:
            empty_lane = lane_idx
            break  # Empty lane counts as lowest potential

    # Schedule the swap
    spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
    exile_cfg = getattr(spellcaster_cfg, 'exile', None) if spellcaster_cfg else None
    swap_delay = getattr(exile_cfg, 'swap_delay', 0.3) if exile_cfg else 0.3

    now = clock.now()
    state.spells.pending_exiles.append(
        {
            'swap_time': now + swap_delay,
            'bird_a_idx': best_bird_idx,
            'bird_b_idx': worst_bird_idx,  # Can be None if swapping to empty lane
            'empty_lane': empty_lane
            if worst_bird_idx is None or (empty_lane is not None and worst_potential > 0)
            else None,
        }
    )


def _check_bat_can_move(bat, next_x):
    """Check if bat can move to next_x position."""
    # Check collision with other bats
    for other_bat in state.enemies.bats:
        if other_bat is bat:
            continue
        other_left = other_bat['x_pos']
        other_right = other_bat['x_pos'] + 8
        next_left = next_x
        next_right = next_x + 8

        if not (next_right < other_left or next_left > other_right):
            return False

    # Check collision with birds
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        bird_y = state.birds.y[i]

        # Bat horizontal range
        bat_left = next_x
        bat_right = next_x + 8

        # Lane range
        lane_left, lane_right = bird_kinds.hit_span(i)

        horizontal_overlap = not (bat_right < lane_left or bat_left > lane_right)

        if horizontal_overlap and abs(bird_y - bat['y_pos']) < 8:
            return False

    return True
