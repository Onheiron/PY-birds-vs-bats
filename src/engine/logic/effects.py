"""Timed effects: power-ups, bird states, spells and enemy debuffs."""

from src.core import constants
from src.core import state
import time
from src.entities.sprites import BLUE, CLOCKWORK, PURPLE, RAINBOW
from src.engine.logic.damage import _handle_bat_death
from src.services.sound import play_sfx
from src.engine.birds import reset_bird_power


def update_powerup_timers():
    """Update all powerup timers."""
    if state.powerups.wide_cursor_active:
        state.powerups.wide_cursor_frames -= 1
        if state.powerups.wide_cursor_frames <= 0:
            state.powerups.wide_cursor_active = False
            state.powerups.wide_cursor_lanes = 1

    if state.powerups.bounce_boost_active:
        state.powerups.bounce_boost_frames -= 1
        if state.powerups.bounce_boost_frames <= 0:
            state.powerups.bounce_boost_active = False
            state.powerups.bounce_boost_duration = 0

    if state.powerups.suction_active:
        state.powerups.suction_frames -= 1
        if state.powerups.suction_frames <= 0:
            state.powerups.suction_active = False
            state.powerups.suction_boost_duration = 0

    if state.powerups.tailwind_active:
        state.powerups.tailwind_frames -= 1
        if state.powerups.tailwind_frames <= 0:
            state.powerups.tailwind_active = False
            state.powerups.tailwind_up_bonus = 0
            state.powerups.tailwind_down_penalty = 0

    if state.powerups.timelapse_active:
        # Use real time instead of frame count
        if time.time() >= state.powerups.timelapse_end_time:
            state.powerups.timelapse_active = False
            state.powerups.timelapse_slowdown = 1.0


def update_special_bird_states():
    """Update special bird state timers (speed boosts, scared, stealth, etc.)."""
    # Speed boosts
    for bird_idx in list(state.special.speed_boosts.keys()):
        if state.special.speed_boosts[bird_idx] > 0:
            state.special.speed_boosts[bird_idx] -= 1
            if state.special.speed_boosts[bird_idx] <= 0:
                del state.special.speed_boosts[bird_idx]
                if state.birds.colors[bird_idx] == BLUE:
                    reset_bird_power(bird_idx)
        else:
            state.special.speed_boosts[bird_idx] += 1
            if state.special.speed_boosts[bird_idx] >= 0:
                del state.special.speed_boosts[bird_idx]

    # Scared birds
    for bird_idx in list(state.special.scared_birds.keys()):
        state.special.scared_birds[bird_idx] -= 1
        if state.special.scared_birds[bird_idx] <= 0:
            del state.special.scared_birds[bird_idx]

    # Stunned birds (from obstacle collision or flower)
    now = time.time()
    for bird_idx in list(state.special.stunned_birds.keys()):
        stun_info = state.special.stunned_birds[bird_idx]
        if isinstance(stun_info, dict):
            # Time-based stun (from flower)
            if now >= stun_info.get('end_time', 0):
                del state.special.stunned_birds[bird_idx]
        else:
            # Frame-based stun (from obstacle collision)
            state.special.stunned_birds[bird_idx] -= 1
            if state.special.stunned_birds[bird_idx] <= 0:
                del state.special.stunned_birds[bird_idx]

    # Dive fall boosts (from diver bats)
    for bird_idx in list(state.special.dive_fall_boosts.keys()):
        boost_info = state.special.dive_fall_boosts[bird_idx]
        boost_info['frames'] -= 1
        if boost_info['frames'] <= 0:
            del state.special.dive_fall_boosts[bird_idx]

    # Stealth timers
    for bird_idx in list(state.special.stealth_timers.keys()):
        state.special.stealth_timers[bird_idx] -= 1
        if state.special.stealth_timers[bird_idx] <= 0:
            del state.special.stealth_timers[bird_idx]
            if bird_idx in state.special.stealth_prev_speeds:
                state.birds.speeds[bird_idx] = state.special.stealth_prev_speeds.pop(bird_idx)

    # Purple just-fired protection
    for i in range(constants.layout.num_balls):
        if state.special.purple_just_fired_frames[i] > 0:
            state.special.purple_just_fired_frames[i] -= 1

    # Poisoned birds - check death timer
    now = time.time()
    for bird_idx in list(state.special.poisoned_birds.keys()):
        poison_info = state.special.poisoned_birds[bird_idx]
        death_time = poison_info.get('death_time', 0)
        if now >= death_time:
            # Bird dies from poison!
            if not state.birds.lost[bird_idx]:
                dead_color = state.birds.colors[bird_idx]
                state.birds.lost[bird_idx] = True
                state.birds.y[bird_idx] = constants.layout.height - 1
                state.game.lives -= 1
                # Check if a pending bird can now transform
                from src.engine.birds import check_pending_transforms
                check_pending_transforms(dead_color)
                if state.game.lives <= 0:
                    state.game.game_over = True
            # Remove from poisoned dict
            del state.special.poisoned_birds[bird_idx]

    # Bleeding birds - check if bleed expired (bird survives if timer runs out)
    for bird_idx in list(state.special.bleeding_birds.keys()):
        bleed_info = state.special.bleeding_birds[bird_idx]
        end_time = bleed_info.get('end_time', 0)
        if now >= end_time:
            # Bleed expired - bird survives!
            del state.special.bleeding_birds[bird_idx]

    # ROCK boost cleanup - restore original speed when expired
    for bird_idx in list(state.special.rock_boosted.keys()):
        if now >= state.special.rock_boosted[bird_idx]:
            del state.special.rock_boosted[bird_idx]
            # Restore original speed
            if bird_idx in state.special.rock_prev_speeds:
                state.birds.speeds[bird_idx] = state.special.rock_prev_speeds.pop(bird_idx)

    # FROSTY boost cleanup
    for bird_idx in list(state.special.frosty_boosted.keys()):
        if now >= state.special.frosty_boosted[bird_idx]:
            del state.special.frosty_boosted[bird_idx]

    # POISON boost cleanup
    for bird_idx in list(state.special.poison_boosted.keys()):
        if now >= state.special.poison_boosted[bird_idx]:
            del state.special.poison_boosted[bird_idx]

    # BERSERK boost cleanup
    for bird_idx in list(state.special.berserk_boosted.keys()):
        if now >= state.special.berserk_boosted[bird_idx]:
            del state.special.berserk_boosted[bird_idx]

    # Clockwork charge decay
    decay_seconds = getattr(constants.clockwork, 'decay_seconds', 30.0)
    for i in range(constants.layout.num_balls):
        if state.birds.colors[i] != CLOCKWORK or state.birds.lost[i]:
            continue

        charge = state.special.clockwork_charge.get(i)
        if charge is None:
            charge = constants.clockwork.initial_charge
            state.special.clockwork_charge[i] = charge
            state.special.clockwork_last_decay[i] = now

        last_decay = state.special.clockwork_last_decay.get(i, now)

        # Decay one charge level every decay_seconds
        if charge > 0 and now - last_decay >= decay_seconds:
            state.special.clockwork_charge[i] = charge - 1
            state.special.clockwork_last_decay[i] = now

    # RAINBOW charge decay and death
    decay_per_second = getattr(constants.rainbow, 'decay_per_second', 5)
    for i in range(constants.layout.num_balls):
        if state.birds.colors[i] != RAINBOW or state.birds.lost[i]:
            continue

        charge = state.special.rainbow_charge.get(i)
        if charge is None:
            max_charge = getattr(constants.rainbow, 'max_charge', 100)
            charge = max_charge
            state.special.rainbow_charge[i] = charge
            state.special.rainbow_last_decay[i] = now

        last_decay = state.special.rainbow_last_decay.get(i, now)

        # Decay charge every second
        if now - last_decay >= 1.0:
            elapsed = now - last_decay
            decay_amount = int(elapsed * decay_per_second)
            state.special.rainbow_charge[i] = max(0, charge - decay_amount)
            state.special.rainbow_last_decay[i] = now

            # Check if charge depleted - RAINBOW dies immediately
            if state.special.rainbow_charge[i] <= 0:
                dead_color = state.birds.colors[i]
                state.birds.lost[i] = True
                state.birds.y[i] = constants.layout.height - 1  # Show X at bottom
                state.birds.per_bird_xp[i] = 0
                state.game.lives -= 1
                play_sfx('bird_lost')
                # Check pending transforms
                from src.engine.birds import check_pending_transforms
                check_pending_transforms(dead_color)
                if state.game.lives <= 0:
                    state.game.game_over = True


def update_spell_effects():
    """Update spell effects from spellcaster bats."""
    now = time.time()

    # Update silenced lanes (remove expired)
    for lane in list(state.spells.silenced_lanes.keys()):
        if now >= state.spells.silenced_lanes[lane]['end_time']:
            del state.spells.silenced_lanes[lane]

    # Update repugnant wind lanes (remove expired)
    for lane in list(state.spells.repugnant_wind_lanes.keys()):
        if now >= state.spells.repugnant_wind_lanes[lane]['end_time']:
            del state.spells.repugnant_wind_lanes[lane]

    # Process pending exile swaps
    for exile in state.spells.pending_exiles[:]:
        if now >= exile['swap_time']:
            _execute_exile_swap(exile)
            state.spells.pending_exiles.remove(exile)


def _execute_exile_swap(exile):
    """Execute an exile swap between birds."""
    bird_a_idx = exile['bird_a_idx']
    bird_b_idx = exile['bird_b_idx']
    empty_lane = exile.get('empty_lane')

    # Validate bird A still exists
    if state.birds.lost[bird_a_idx]:
        return

    if empty_lane is not None:
        # Swap bird A to empty lane
        state.birds.random_lanes[bird_a_idx] = empty_lane
        state.birds.cols[bird_a_idx] = constants.layout.lane_positions[empty_lane]
    elif bird_b_idx is not None and not state.birds.lost[bird_b_idx]:
        # Swap lanes between bird A and bird B
        lane_a = state.birds.random_lanes[bird_a_idx]
        lane_b = state.birds.random_lanes[bird_b_idx]

        state.birds.random_lanes[bird_a_idx] = lane_b
        state.birds.random_lanes[bird_b_idx] = lane_a
        state.birds.cols[bird_a_idx] = constants.layout.lane_positions[lane_b]
        state.birds.cols[bird_b_idx] = constants.layout.lane_positions[lane_a]


def update_enemy_debuffs():
    """Update enemy debuffs applied by FROSTY/POISON/BERSERK birds."""
    now = time.time()

    # FROZEN enemies - cleanup expired, no damage tick
    for enemy_id in list(state.special.frozen_enemies.keys()):
        debuff = state.special.frozen_enemies[enemy_id]
        if now >= debuff['end_time']:
            del state.special.frozen_enemies[enemy_id]
            continue
        # Check if bat is still alive
        bat = debuff.get('bat')
        if bat and bat not in state.enemies.bats:
            del state.special.frozen_enemies[enemy_id]

    # POISONED enemies - damage tick every second
    for enemy_id in list(state.special.poisoned_enemies.keys()):
        debuff = state.special.poisoned_enemies[enemy_id]
        if now >= debuff['end_time']:
            del state.special.poisoned_enemies[enemy_id]
            continue
        bat = debuff.get('bat')
        if bat and bat not in state.enemies.bats:
            del state.special.poisoned_enemies[enemy_id]
            continue
        # Apply damage tick
        if now - debuff['last_tick'] >= 1.0:
            debuff['last_tick'] = now
            damage = debuff.get('damage_per_second', 2)
            if bat:
                bat['hp'] -= damage
                if bat['hp'] <= 0:
                    _handle_bat_death(bat, 0)  # No specific killer
                    del state.special.poisoned_enemies[enemy_id]

    # BLEEDING enemies - damage tick every second, armor reduction
    for enemy_id in list(state.special.bleeding_enemies.keys()):
        debuff = state.special.bleeding_enemies[enemy_id]
        if now >= debuff['end_time']:
            del state.special.bleeding_enemies[enemy_id]
            continue
        bat = debuff.get('bat')
        if bat and bat not in state.enemies.bats:
            del state.special.bleeding_enemies[enemy_id]
            continue
        # Apply damage tick
        if now - debuff['last_tick'] >= 1.0:
            debuff['last_tick'] = now
            damage = debuff.get('damage_per_second', 1)
            if bat:
                bat['hp'] -= damage
                if bat['hp'] <= 0:
                    _handle_bat_death(bat, 0)
                    del state.special.bleeding_enemies[enemy_id]


def update_purple_charging():
    """Update purple bird charging state machine.

    Purple charges ONLY while UP is held. Releases when UP is released.
    Damage: <1s = 1, <2s = 4, <3s = 16, 3s (auto) = 64

    We detect "UP released" by checking time since last UP input.
    Terminal key repeat: first repeat after ~500ms, then every ~30ms.
    So if no UP for 0.6s, user definitely released the key.
    """
    # Seconds without UP to consider it "released"
    # Must be > terminal key repeat initial delay (~500ms)
    RELEASE_THRESHOLD_SECS = 0.6

    now = time.time()

    for b in range(constants.layout.num_balls):
        ps = state.special.purple_state[b]

        if ps == 1:  # Primed - waiting for hold confirmation
            # Transition to charging state, record start TIME
            if not state.birds.lost[b] and state.birds.vy[b] == -1:
                state.special.purple_state[b] = 2
                state.special.purple_charge_started_frame[b] = now  # Using as timestamp now

        elif ps == 2:  # Charging - only while UP is held
            charge_start_time = state.special.purple_charge_started_frame[b]
            charge_seconds = now - charge_start_time
            time_since_up = now - state.special.last_up_time

            # Auto-fire at 3 seconds (max charge)
            if charge_seconds >= 3:
                _fire_purple_projectile(b, 3)
            # Release shot when UP hasn't been pressed for too long
            elif time_since_up >= RELEASE_THRESHOLD_SECS:
                _fire_purple_projectile(b, charge_seconds)


def _fire_purple_projectile(bird_idx, charge_seconds):
    """Fire a purple charged projectile.

    Damage based on charge time (discrete tiers):
    - <1s: 4^0 = 1
    - <2s: 4^1 = 4
    - <3s: 4^2 = 16
    - 3s:  4^3 = 64
    """
    charge_tier = min(3, int(charge_seconds))  # 0, 1, 2, or 3
    damage = int(pow(4, charge_tier))
    lane = state.birds.random_lanes[bird_idx]

    state.special.red_projectiles.append({
        'x_pos': constants.layout.lane_positions[lane],
        'y_pos': state.birds.y[bird_idx],
        'lane': lane,
        'damage': damage,
        'powered': damage > 1,
        'owner': bird_idx,
        'speed': 4,
        'color': PURPLE
    })

    state.special.purple_just_fired_frames[bird_idx] = 3
    state.special.purple_state[bird_idx] = 0
    state.special.purple_charge_started_frame[bird_idx] = 0
    state.special.purple_primed_frame[bird_idx] = 0
