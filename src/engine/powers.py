"""Bird powers, triggered by bouncing a bird that is already rising."""

from src.core import constants
from src.core import state
from src.engine.birds import allow_consume_power
from src.engine.birds import find_bird_in_lane
from src.engine.birds import get_color_name
from src.engine.birds import reset_bird_power
from src.engine.birds import set_ball_vy
from src.services import achievements
import random
import time
from src.entities.sprites import BERSERK, BLUE, CLOCKWORK, COOKIE, FROSTY, GLITCH, PATCHWORK, POISON, PURPLE, RED, ROCK, STEALTH, TWISTER, WHITE, YELLOW


def _activate_bird_power(bird_idx):
    """Activate a bird's special power."""
    from src.engine.grades import compute_grade_from_xp

    # POISONED BIRDS: power is blocked while poisoned (cure handled in main input handler)
    if bird_idx in state.special.poisoned_birds:
        return

    # Check if lane is silenced by spellcaster bat
    bird_lane = state.birds.random_lanes[bird_idx]
    if bird_lane in state.spells.silenced_lanes:
        # Power blocked by silence spell
        return

    # Check allowed uses
    label, _ = compute_grade_from_xp(state.birds.per_bird_xp[bird_idx])
    allowed_uses = 2 if (label and label.startswith('A')) else 1

    if not allow_consume_power(bird_idx, allowed_uses):
        return

    bird_color = state.birds.colors[bird_idx]

    # Notify achievements
    color_name = get_color_name(bird_color)
    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power=color_name, lane=bird_lane)

    # Execute power based on color
    if bird_color == YELLOW:
        _power_yellow(bird_idx, bird_lane)
    elif bird_color == RED:
        _power_red(bird_idx, bird_lane)
    elif bird_color == PURPLE:
        _power_purple(bird_idx)
    elif bird_color == COOKIE:
        _power_cookie(bird_idx, bird_lane)
    elif bird_color == BLUE:
        _power_blue(bird_idx)
    elif bird_color == WHITE:
        _power_white(bird_idx, bird_lane)
    elif bird_color == CLOCKWORK:
        _power_clockwork(bird_idx)
    elif bird_color == STEALTH:
        _power_stealth(bird_idx, bird_lane)
    elif bird_color == TWISTER:
        _power_twister(bird_idx, bird_lane)
    elif bird_color == FROSTY:
        _power_frosty(bird_idx)
    elif bird_color == POISON:
        _power_poison(bird_idx)
    elif bird_color == BERSERK:
        _power_berserk(bird_idx)
    elif bird_color == ROCK:
        _power_rock(bird_idx)


def _power_yellow(bird_idx, bird_lane):
    """Yellow power: bounce adjacent yellows, slow others."""
    for adj_offset in [-1, 1]:
        adj_lane = bird_lane + adj_offset
        if not (0 <= adj_lane < constants.layout.num_lanes):
            continue

        adj_bird = find_bird_in_lane(adj_lane)
        if adj_bird < 0 or state.birds.lost[adj_bird]:
            continue
        if state.birds.vy[adj_bird] != 1:  # Must be falling
            continue

        adj_color = state.birds.colors[adj_bird]
        if adj_color == YELLOW or adj_color == PATCHWORK:
            # Bounce adjacent yellow/patchwork
            if adj_color == GLITCH and random.random() < constants.glitch.bounce_ignore_chance:
                continue
            set_ball_vy(adj_bird, -1)
            reset_bird_power(adj_bird)
            achievements.append_recent_action('bounce', lane=adj_lane,
                                             color=adj_color, frame_count=state.game.frame_count)
            # Cure scared blue birds nearby
            _cure_nearby_scared_blues(adj_lane)
        else:
            # Slow non-yellow bird
            state.special.speed_boosts[adj_bird] = -int(3.0 / constants.timing.base_sleep)


def _cure_nearby_scared_blues(lane):
    """Cure scared blue birds in adjacent lanes."""
    for cross_offset in [-1, 1]:
        cross_lane = lane + cross_offset
        if not (0 <= cross_lane < constants.layout.num_lanes):
            continue
        for bi in range(constants.layout.num_balls):
            if (state.birds.random_lanes[bi] == cross_lane and
                not state.birds.lost[bi] and
                state.birds.colors[bi] == BLUE and
                bi in state.special.scared_birds and
                state.birds.vy[bi] == 1):
                del state.special.scared_birds[bi]


def _power_red(bird_idx, bird_lane):
    """Red power: launch projectile with damage bonus from adjacent reds."""
    damage_bonus = 0
    for adj_offset in [-1, 1]:
        adj_lane = bird_lane + adj_offset
        if not (0 <= adj_lane < constants.layout.num_lanes):
            continue
        for idx in range(constants.layout.num_balls):
            if state.birds.random_lanes[idx] == adj_lane and not state.birds.lost[idx]:
                adj_color = state.birds.colors[idx]
                if adj_color in (RED, PURPLE, PATCHWORK) and state.birds.vy[idx] == -1:
                    damage_bonus += 1
                break

    state.special.red_projectiles.append({
        'x_pos': constants.layout.lane_positions[bird_lane],
        'y_pos': state.birds.y[bird_idx],
        'lane': bird_lane,
        'damage': 1 + damage_bonus,
        'powered': damage_bonus > 0,
        'owner': bird_idx,
        'speed': 1,
        'color': RED
    })


def _power_purple(bird_idx):
    """Purple power: begin charging."""
    if state.special.purple_state[bird_idx] == 0:
        state.special.purple_state[bird_idx] = 1
        state.special.purple_primed_frame[bird_idx] = state.game.frame_count
        state.special.purple_hold_counter[bird_idx] = 0


def _power_cookie(bird_idx, bird_lane):
    """Cookie power: drop a cookie crumb with XP."""
    crumb_xp = int(max(0, int(state.birds.per_bird_xp[bird_idx] * 0.75)))

    state.items.loot_items.append({
        'x_pos': constants.layout.lane_positions[bird_lane],
        'y_pos': state.birds.y[bird_idx],
        'type': 'cookie_crumb',
        'rarity': 'rare',
        'xp': crumb_xp,
        'spawn_ts': time.time()
    })

    # Track crumbs made
    state.special.cookie_crumbs_made[bird_idx] = state.special.cookie_crumbs_made.get(bird_idx, 0) + 1

    # After 5 crumbs, cookie bird dies
    if state.special.cookie_crumbs_made.get(bird_idx, 0) >= 5:
        if not state.birds.lost[bird_idx]:
            dead_color = state.birds.colors[bird_idx]
            state.birds.lost[bird_idx] = True
            state.birds.y[bird_idx] = constants.layout.height - 1
            state.birds.per_bird_xp[bird_idx] = 0
            state.game.lives -= 1
            # Check if a pending bird can now transform
            from src.engine.birds import check_pending_transforms
            check_pending_transforms(dead_color)
            if state.game.lives <= 0:
                state.game.game_over = True


def _power_blue(bird_idx):
    """Blue power: speed boost."""
    boost_frames = int(3.0 / constants.timing.base_sleep)
    state.special.speed_boosts[bird_idx] = boost_frames


def _power_white(bird_idx, bird_lane):
    """White power: affect 4 adjacent lanes."""
    from src.engine.grades import compute_grade_from_xp

    for adj_offset in [-2, -1, 1, 2]:
        adj_lane = bird_lane + adj_offset
        if not (0 <= adj_lane < constants.layout.num_lanes):
            continue

        adj_bird = find_bird_in_lane(adj_lane)
        if adj_bird < 0 or state.birds.lost[adj_bird]:
            continue

        adj_color = state.birds.colors[adj_bird]

        if state.birds.vy[adj_bird] == 1:  # Falling - bounce it
            if adj_bird in state.special.scared_birds and adj_color != PURPLE:
                continue
            if adj_bird in state.special.stunned_birds:
                continue
            if adj_color == GLITCH and random.random() < constants.glitch.bounce_ignore_chance:
                continue
            set_ball_vy(adj_bird, -1)
            reset_bird_power(adj_bird)
            achievements.append_recent_action('bounce', lane=adj_lane,
                                             color=adj_color, frame_count=state.game.frame_count)
        elif state.birds.vy[adj_bird] == -1:  # Rising - activate power
            label, _ = compute_grade_from_xp(state.birds.per_bird_xp[adj_bird])
            adj_allowed = 2 if (label and label.startswith('A')) else 1
            if allow_consume_power(adj_bird, adj_allowed):
                _activate_adjacent_power(adj_bird, adj_lane)


def _activate_adjacent_power(adj_bird, adj_lane):
    """Activate an adjacent bird's power (triggered by white bird)."""
    adj_color = state.birds.colors[adj_bird]

    if adj_color == YELLOW:
        _power_yellow(adj_bird, adj_lane)
    elif adj_color == RED:
        _power_red(adj_bird, adj_lane)
    elif adj_color == BLUE:
        _power_blue(adj_bird)


def _power_clockwork(bird_idx):
    """Clockwork power: increase charge."""
    cur = state.special.clockwork_charge.get(bird_idx, constants.clockwork.initial_charge)
    if cur is None:
        cur = constants.clockwork.initial_charge
    newc = min(constants.clockwork.max_charge, cur + 1)
    state.special.clockwork_charge[bird_idx] = newc
    if newc > 0:
        state.birds.speeds[bird_idx] = newc


def _power_stealth(bird_idx, bird_lane):
    """Stealth power: become tangible with speed boost."""
    state.special.stealth_timers[bird_idx] = max(1, int(constants.stealth.tangible_seconds / constants.timing.base_sleep))
    state.special.stealth_prev_speeds[bird_idx] = state.birds.speeds[bird_idx]
    state.birds.speeds[bird_idx] = constants.stealth.speed_boost
    achievements.append_recent_action('stealth', lane=bird_lane, color=STEALTH, frame_count=state.game.frame_count)


def _power_twister(bird_idx, bird_lane):
    """Twister power: create local tailwind in current lane + 2 adjacent."""
    duration = getattr(constants.twister, 'tailwind_duration', 2.0)
    end_time = time.time() + duration
    # Affected lanes: current + adjacent
    lanes = [bird_lane]
    if bird_lane > 0:
        lanes.append(bird_lane - 1)
    if bird_lane < constants.layout.num_lanes - 1:
        lanes.append(bird_lane + 1)
    state.special.twister_tailwind[bird_idx] = {
        'end_time': end_time,
        'lanes': lanes
    }
    achievements.append_recent_action('twister', lane=bird_lane, color=TWISTER, frame_count=state.game.frame_count)


def _power_frosty(bird_idx):
    """Frosty power: boost freeze chance to 60% for 2s."""
    duration = getattr(constants.frosty, 'boost_duration', 2.0)
    state.special.frosty_boosted[bird_idx] = time.time() + duration


def _power_poison(bird_idx):
    """Poison power: boost poison chance to 60% for 2s."""
    duration = getattr(constants.poison, 'boost_duration', 2.0)
    state.special.poison_boosted[bird_idx] = time.time() + duration


def _power_berserk(bird_idx):
    """Berserk power: boost bleed chance to 60% for 2s."""
    duration = getattr(constants.berserk, 'boost_duration', 2.0)
    state.special.berserk_boosted[bird_idx] = time.time() + duration


def _power_rock(bird_idx):
    """Rock power: boost push to 2 rows and speed to 3 for 3s."""
    duration = getattr(constants.rock, 'boost_duration', 3.0)
    # Save original speed before boosting
    if bird_idx not in state.special.rock_boosted:
        state.special.rock_prev_speeds = getattr(state.special, 'rock_prev_speeds', {})
        state.special.rock_prev_speeds[bird_idx] = state.birds.speeds[bird_idx]
    state.special.rock_boosted[bird_idx] = time.time() + duration
    state.birds.speeds[bird_idx] = getattr(constants.rock, 'boosted_speed', 3)
