"""Bird, bat, obstacle and projectile collisions."""

import random
import time

from src.core import constants, state
from src.engine.birds import get_scared_frames, reset_bird_power, set_ball_vy
from src.engine.logic.damage import _calculate_bird_damage, _handle_bat_death
from src.engine.logic.flowers import _apply_flower_collision_effect
from src.engine.logic.helpers import _get_obstacle_lanes
from src.engine.logic.mini_bats import handle_obstacle_destroyed, try_spawn_mini_bat_on_hit
from src.engine.progression import add_score, award_xp
from src.entities.sprites import (
    BERSERK,
    BLUE,
    CLOCKWORK,
    DINOSAUR,
    FROSTY,
    GLITCH,
    OBSTACLE_LANE_WIDTH,
    OBSTACLE_SPRITE_T1,
    OBSTACLE_SPRITES,
    ORANGE,
    POISON,
    RAINBOW,
    ROCK,
    STEALTH,
)
from src.services.sound import play_sfx


def check_bird_ceiling_bounce():
    """Check if birds hit ceiling and bounce them."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue
        if state.birds.y[i] <= 1:
            # ORANGE special: goes to dormant state
            if state.birds.colors[i] == ORANGE:
                lane = state.birds.random_lanes[i]
                state.birds.y[i] = 999  # Out of play
                set_ball_vy(i, 0)
                reset_bird_power(i)
                state.birds.speeds[i] = 0
                # Spawn orange egg loot (both native and transformed Orange birds)
                state.items.loot_items.append(
                    {
                        'x_pos': constants.layout.lane_positions[lane],
                        'y_pos': constants.layout.starting_line,
                        'type': 'orange_egg',
                        'rarity': 'epic',
                        'spawn_ts': time.time(),
                    }
                )
                continue

            # RAINBOW special: warp to floor instead of bounce
            if state.birds.colors[i] == RAINBOW:
                # Check if still has charge
                charge = state.special.rainbow_charge.get(i, 100)
                if charge > 0:
                    # Warp to floor, keep going up (will warp again)
                    state.birds.y[i] = constants.layout.starting_line - 1
                    # Keep vy=-1 (going up) - continues through the warp
                continue

            # Normal bounce
            state.birds.y[i] = 1
            set_ball_vy(i, 1)
            reset_bird_power(i)


def check_bird_floor_collision():
    """Check if birds hit floor (game over condition)."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue
        if state.birds.y[i] < constants.layout.height - 1:
            continue

        bird_color = state.birds.colors[i]

        # CLOCKWORK auto-bounce if has charge
        if bird_color == CLOCKWORK:
            charge = state.special.clockwork_charge.get(i)
            if charge is None:
                charge = constants.clockwork.initial_charge
                state.special.clockwork_charge[i] = charge
            if charge > 0:
                state.birds.y[i] = constants.layout.starting_line
                set_ball_vy(i, -1)
                reset_bird_power(i)
                continue

        # RAINBOW warp to ceiling if has charge
        if bird_color == RAINBOW:
            charge = state.special.rainbow_charge.get(i, 100)
            if charge > 0:
                # Warp to ceiling, keep going down
                state.birds.y[i] = 2
                # Keep vy=1 (going down) - continues through the warp
                continue
            # No charge - RAINBOW dies (handled below)

        # ORANGE birds don't die at floor
        if bird_color == ORANGE:
            continue

        # GLITCH survival chance
        if bird_color == GLITCH and random.random() < constants.glitch.survive_on_floor_chance:
            state.birds.y[i] = constants.layout.starting_line
            set_ball_vy(i, -1)
            reset_bird_power(i)
            continue

        # Bird dies
        dead_color = state.birds.colors[i]
        state.birds.lost[i] = True
        state.birds.y[i] = constants.layout.height - 1
        state.birds.per_bird_xp[i] = 0
        state.game.lives -= 1
        play_sfx('bird_lost')

        # Check if a pending bird can now transform
        from src.engine.birds import check_pending_transforms

        check_pending_transforms(dead_color)

        if state.game.lives <= 0:
            state.game.game_over = True


def check_bird_obstacle_collision():
    """Check bird-obstacle collisions."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i] or state.birds.vy[i] != -1:
            continue

        # Skip charging purple
        if state.special.purple_state[i] == 2 or state.special.purple_just_fired_frames[i] > 0:
            continue

        bird_lane = state.birds.random_lanes[i]
        bird_color = state.birds.colors[i]
        next_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_color == STEALTH and i not in state.special.stealth_timers:
            continue

        for obs in state.enemies.obstacles[:]:
            # Check if bird lane is within obstacle's lanes
            obs_lanes = _get_obstacle_lanes(obs)
            if bird_lane not in obs_lanes:
                continue

            # Check vertical proximity (consider sprite height)
            obs_tier = obs.get('tier', 1)
            sprite_height = len(OBSTACLE_SPRITES.get(obs_tier, OBSTACLE_SPRITE_T1))
            if next_y < obs['y_pos'] - 1 or next_y > obs['y_pos'] + sprite_height:
                continue

            # Hit obstacle
            damage = _calculate_bird_damage(i)

            # Check if obstacle has a mature flower - apply effect before damage
            flower = obs.get('flower')
            from src.entities.sprites import FLOWER_MATURE_FRAME

            if flower and flower.get('active') and flower.get('frame', 0) >= FLOWER_MATURE_FRAME:
                _apply_flower_collision_effect(flower, i)

            if bird_color == ORANGE:
                obs['hp'] = 0
            else:
                obs['hp'] -= damage
                award_xp(i, damage)
                # Also damage flower if present
                if flower and flower.get('active') and flower.get('hp', 0) > 0:
                    flower['hp'] -= damage
                    if flower['hp'] <= 0:
                        flower['active'] = False

            # Try to spawn mini bat on each hit (tier 3+ only, if Y position ok)
            try_spawn_mini_bat_on_hit(obs)

            if obs['hp'] <= 0:
                tier = obs.get('tier', 1)
                xp_per_tier = getattr(constants.combat, 'obstacle_destroy_xp_per_tier', 5)
                score_per_tier = getattr(constants.combat, 'obstacle_destroy_score_per_tier', 50)
                award_xp(i, xp_per_tier * tier)
                add_score(tier * score_per_tier)
                # Handle mini bat hiding before removing obstacle
                handle_obstacle_destroyed(obs)
                state.enemies.obstacles.remove(obs)
                play_sfx('destroy')
            else:
                set_ball_vy(i, 1)
                # Applica stun (1 secondo) - impedisce bounce
                stun_frames = int(1.0 / constants.timing.base_sleep)
                state.special.stunned_birds[i] = stun_frames
                # Aggiungi a scared_birds per speed boost in caduta (1 secondo)
                state.special.scared_birds[i] = stun_frames
                if bird_color == BLUE:
                    reset_bird_power(i)
                play_sfx('hit')
            break


def check_bird_bat_collision():
    """Check bird-bat collisions."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i] or state.birds.vy[i] != -1:
            continue

        if state.special.purple_state[i] == 2 or state.special.purple_just_fired_frames[i] > 0:
            continue

        bird_lane = state.birds.random_lanes[i]
        bird_lane_x = constants.layout.lane_positions[bird_lane]
        bird_color = state.birds.colors[i]
        next_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_color == STEALTH and i not in state.special.stealth_timers:
            continue

        bird_height = 3 if bird_color == DINOSAUR else 2

        for bat in state.enemies.bats[:]:
            bat_left = bat['x_pos']
            bat_right = bat['x_pos'] + 8
            bat_top = bat['y_pos']
            bat_bottom = bat['y_pos'] + 1

            lane_left = bird_lane_x - 2
            lane_right = bird_lane_x + 2

            horizontal_overlap = not (bat_right < lane_left or bat_left > lane_right)
            vertical_overlap = not (next_y + bird_height < bat_top or next_y > bat_bottom)

            if not (horizontal_overlap and vertical_overlap):
                continue

            # Hit bat
            damage = _calculate_bird_damage(i)

            # Apply armor damage reduction for armored bats
            is_armored = bat.get('armored', False)
            if is_armored and bird_color != ORANGE:
                armored_cfg = getattr(constants.bat_enemy, 'armored', None)
                if armored_cfg:
                    bat_tier = bat.get('tier', 1)
                    dmg_reduction_cfg = getattr(armored_cfg, 'damage_reduction_by_tier', None)
                    if dmg_reduction_cfg:
                        if isinstance(dmg_reduction_cfg, dict):
                            reduction = dmg_reduction_cfg.get(bat_tier, dmg_reduction_cfg.get(str(bat_tier), 0))
                        else:
                            reduction = getattr(dmg_reduction_cfg, str(bat_tier), 0)
                        # Reduce armor by FROZEN/BLEEDING debuffs
                        bat_id = id(bat)
                        if bat_id in state.special.frozen_enemies:
                            frozen_reduction = state.special.frozen_enemies[bat_id].get('armor_reduction', 2)
                            reduction = max(0, reduction - frozen_reduction)
                        if bat_id in state.special.bleeding_enemies:
                            bleed_reduction = state.special.bleeding_enemies[bat_id].get('armor_reduction', 1)
                            reduction = max(0, reduction - bleed_reduction)
                        damage = max(1, damage - reduction)  # Minimum 1 damage

            if bird_color == ORANGE:
                bat['hp'] = 0
            else:
                bat['hp'] -= damage
                award_xp(i, damage)

            # Check if diver bat in stunned/returning state (no scare)
            is_diver = bat.get('diver', False)
            diver_state = bat.get('diver_state', 'flying')
            diver_no_scare = is_diver and diver_state in ('stunned', 'returning')

            # Apply scared effect (unless stealth tangible or diver stunned/returning)
            is_stealth_tangible = bird_color == STEALTH and i in state.special.stealth_timers
            if not is_stealth_tangible and not diver_no_scare:
                bat_tier = bat.get('tier', 1)
                scared_duration = getattr(constants.combat, 'scared_duration', 2.0)
                state.special.scared_birds[i] = get_scared_frames(i, scared_duration)
                speed_boost_min_tier = getattr(constants.combat, 'speed_boost_min_tier', 3)
                if bat_tier >= speed_boost_min_tier:
                    speed_boost_duration = getattr(constants.combat, 'speed_boost_duration', 2.0)
                    state.special.speed_boosts[i] = int(speed_boost_duration / constants.timing.base_sleep)

                # Armored bats give additional scare speed boost
                if is_armored:
                    armored_cfg = getattr(constants.bat_enemy, 'armored', None)
                    if armored_cfg:
                        armor_scare_bonus = getattr(armored_cfg, 'scare_speed_bonus', 1)
                        armor_scare_duration = getattr(armored_cfg, 'scare_bonus_duration', 1.0)
                        armor_scare_frames = int(armor_scare_duration / constants.timing.base_sleep)
                        # Add to existing speed boost or create new one
                        current_boost = state.special.speed_boosts.get(i, 0)
                        state.special.speed_boosts[i] = max(current_boost, armor_scare_frames) + armor_scare_bonus

            # Diver bats in diving state give fall speed boost
            if is_diver and diver_state == 'diving':
                diver_cfg = getattr(constants.bat_enemy, 'diver', None)
                if diver_cfg:
                    dive_boost_speed = getattr(diver_cfg, 'dive_boost_speed', 1)
                    dive_boost_duration = getattr(diver_cfg, 'dive_boost_duration', 0.5)
                    dive_boost_frames = int(dive_boost_duration / constants.timing.base_sleep)
                    # Apply dive fall boost (separate from scared speed boost)
                    state.special.dive_fall_boosts[i] = {'frames': dive_boost_frames, 'speed': dive_boost_speed}

            # ROCK bird pushes enemies up
            if bird_color == ROCK:
                import time as time_module

                now = time_module.time()
                # Check if boosted (power active)
                is_boosted = i in state.special.rock_boosted and now < state.special.rock_boosted[i]
                if is_boosted:
                    push_rows = getattr(constants.rock, 'boosted_push_rows', 2)
                else:
                    push_rows = getattr(constants.rock, 'push_rows', 1)
                # Push bat up (decrease y_pos, but not above 0)
                bat['y_pos'] = max(0, bat['y_pos'] - push_rows)
                bat['target_y'] = max(0, bat['target_y'] - push_rows)

            # FROSTY bird applies FROZEN debuff to enemies
            if bird_color == FROSTY:
                import time as time_module

                now = time_module.time()
                # Check if boosted
                is_boosted = i in state.special.frosty_boosted and now < state.special.frosty_boosted[i]
                # Boss has lower chance
                is_boss = bat.get('is_boss', False)
                if is_boss:
                    chance = getattr(constants.frosty, 'boss_chance', 0.10)
                elif is_boosted:
                    chance = getattr(constants.frosty, 'boosted_chance', 0.60)
                else:
                    chance = getattr(constants.frosty, 'base_chance', 0.30)
                if random.random() < chance:
                    bat_id = id(bat)
                    freeze_duration = getattr(constants.frosty, 'freeze_duration', 3.0)
                    state.special.frozen_enemies[bat_id] = {
                        'end_time': now + freeze_duration,
                        'bat': bat,
                        'armor_reduction': getattr(constants.frosty, 'armor_reduction', 2),
                    }

            # POISON bird applies POISON debuff to bats/boss only
            if bird_color == POISON:
                import time as time_module

                now = time_module.time()
                # Check if boosted
                is_boosted = i in state.special.poison_boosted and now < state.special.poison_boosted[i]
                if is_boosted:
                    chance = getattr(constants.poison, 'boosted_chance', 0.60)
                else:
                    chance = getattr(constants.poison, 'base_chance', 0.30)
                if random.random() < chance:
                    bat_id = id(bat)
                    effect_duration = getattr(constants.poison, 'effect_duration', 5.0)
                    state.special.poisoned_enemies[bat_id] = {
                        'end_time': now + effect_duration,
                        'last_tick': now,
                        'bat': bat,
                        'damage_per_second': getattr(constants.poison, 'damage_per_second', 2),
                    }

            # BERSERK bird applies BLEED debuff
            if bird_color == BERSERK:
                import time as time_module

                now = time_module.time()
                # Check if boosted
                is_boosted = i in state.special.berserk_boosted and now < state.special.berserk_boosted[i]
                if is_boosted:
                    chance = getattr(constants.berserk, 'boosted_chance', 0.60)
                else:
                    chance = getattr(constants.berserk, 'base_chance', 0.30)
                if random.random() < chance:
                    bat_id = id(bat)
                    effect_duration = getattr(constants.berserk, 'effect_duration', 10.0)
                    state.special.bleeding_enemies[bat_id] = {
                        'end_time': now + effect_duration,
                        'last_tick': now,
                        'bat': bat,
                        'damage_per_second': getattr(constants.berserk, 'damage_per_second', 1),
                        'armor_reduction': getattr(constants.berserk, 'armor_reduction', 1),
                    }

            if bat['hp'] <= 0:
                _handle_bat_death(bat, i)
            else:
                set_ball_vy(i, 1)
                state.birds.y[i] = bat_bottom + 1
                if bird_color == BLUE:
                    reset_bird_power(i)
            break


def check_projectile_collision():
    """Check projectile-enemy collisions."""
    for proj in state.special.red_projectiles[:]:
        removed = False

        # Check bat collision
        for bat in state.enemies.bats[:]:
            bat_left = bat['x_pos']
            bat_right = bat['x_pos'] + 8
            bat_top = bat['y_pos']
            bat_bottom = bat['y_pos'] + 1

            if bat_left <= proj['x_pos'] <= bat_right and bat_top <= proj['y_pos'] <= bat_bottom:
                damage = proj.get('damage', 1)
                bat['hp'] -= damage

                owner = proj.get('owner')
                if owner is not None:
                    award_xp(owner, damage)

                if bat['hp'] <= 0:
                    _handle_bat_death(bat, owner if owner is not None else 0)

                if proj in state.special.red_projectiles:
                    state.special.red_projectiles.remove(proj)
                removed = True
                break

        if removed:
            continue

        # Check obstacle collision
        for obs in state.enemies.obstacles[:]:
            # Check if projectile lane is within obstacle's lanes
            obs_lanes = _get_obstacle_lanes(obs)
            if proj['lane'] not in obs_lanes:
                continue

            # Check vertical proximity (consider sprite height)
            obs_tier = obs.get('tier', 1)
            sprite_height = len(OBSTACLE_SPRITES.get(obs_tier, OBSTACLE_SPRITE_T1))
            if proj['y_pos'] < obs['y_pos'] - 1 or proj['y_pos'] > obs['y_pos'] + sprite_height:
                continue

            damage = proj.get('damage', 1)
            obs['hp'] -= damage

            owner = proj.get('owner')
            if owner is not None:
                award_xp(owner, damage)

            if obs['hp'] <= 0:
                tier = obs.get('tier', 1)
                if owner is not None:
                    xp_per_tier = getattr(constants.combat, 'obstacle_destroy_xp_per_tier', 5)
                    award_xp(owner, xp_per_tier * tier)
                score_per_tier = getattr(constants.combat, 'obstacle_destroy_score_per_tier', 50)
                add_score(tier * score_per_tier)
                state.enemies.obstacles.remove(obs)

            if proj in state.special.red_projectiles:
                state.special.red_projectiles.remove(proj)
            removed = True
            break

        if removed:
            continue

        # Check Tree Boss branch collision
        boss = state.enemies.boss
        if boss and boss.get('boss_type') == 'tree':
            branches = boss.get('branches', [])
            for branch in branches:
                if branch.get('destroyed'):
                    continue

                # Check if projectile is within branch bounds
                branch_left = branch['x_pos']
                branch_right = branch['x_pos'] + branch['sprite_width']
                branch_top = branch['y_pos']
                branch_bottom = branch['y_pos'] + branch['sprite_height']

                if branch_left <= proj['x_pos'] <= branch_right and branch_top <= proj['y_pos'] <= branch_bottom:
                    damage = proj.get('damage', 1)
                    owner = proj.get('owner')

                    # Damage flower first, then branch
                    flower = branch.get('flower')
                    if flower and flower.get('active') and flower.get('hp', 0) > 0:
                        flower['hp'] -= damage
                        if owner is not None:
                            award_xp(owner, damage)
                        if flower['hp'] <= 0:
                            flower['active'] = False
                            tree_boss_cfg = getattr(constants, 'tree_boss', None)
                            flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None
                            respawn_delay = getattr(flowers_cfg, 'respawn_delay', 3.0) if flowers_cfg else 3.0
                            flower['respawn_timer'] = time.time() + respawn_delay
                    else:
                        # Damage branch
                        branch['hp'] -= damage
                        if owner is not None:
                            award_xp(owner, damage)
                        if branch['hp'] <= 0:
                            branch['destroyed'] = True
                            add_score(100)

                    if proj in state.special.red_projectiles:
                        state.special.red_projectiles.remove(proj)
                    removed = True
                    break

            if removed:
                continue

        # Check OTHER boss collision (normal, wind, jelly, owl)
        if boss and boss.get('boss_type') != 'tree' and boss['state'] not in ('dying', 'dead'):
            boss_type = boss.get('boss_type', 'normal')

            # Get boss dimensions based on type
            if boss_type == 'owl':
                boss_width = 15
                boss_height = 6
            elif boss_type == 'wind':
                boss_width = 26
                boss_height = 5
            elif boss_type == 'jelly':
                boss_width = 23
                boss_height = 6
            else:  # normal
                boss_width = 19
                boss_height = 3

            boss_left = boss['x_pos']
            boss_right = boss['x_pos'] + boss_width
            boss_top = boss['y_pos']
            boss_bottom = boss['y_pos'] + boss_height

            # Check if projectile hits boss
            if boss_left <= proj['x_pos'] <= boss_right and boss_top <= proj['y_pos'] <= boss_bottom:
                damage = proj.get('damage', 1)
                owner = proj.get('owner')

                boss['hp'] -= damage
                if owner is not None:
                    award_xp(owner, damage)

                play_sfx('hit')

                if boss['hp'] <= 0:
                    boss['state'] = 'dying'
                    play_sfx('boss_death')

                if proj in state.special.red_projectiles:
                    state.special.red_projectiles.remove(proj)
                removed = True

        if removed:
            continue


def check_bat_obstacle_collision():
    """Check bat-obstacle collisions (bats destroy obstacles)."""
    for bat in state.enemies.bats:
        bat_left = bat['x_pos']
        bat_right = bat['x_pos'] + 8
        bat_top = bat['y_pos']
        bat_bottom = bat['y_pos'] + 1

        for obs in state.enemies.obstacles[:]:
            # Calcola l'area occupata dall'ostacolo (multi-lane)
            tier = obs.get('tier', 1)
            lane_width = OBSTACLE_LANE_WIDTH.get(tier, 1)
            sprite = OBSTACLE_SPRITES.get(tier, OBSTACLE_SPRITE_T1)
            sprite_width = max(len(line) for line in sprite)
            sprite_height = len(sprite)

            start_lane = obs['lane']
            end_lane = min(start_lane + lane_width - 1, constants.layout.num_lanes - 1)

            start_x = constants.layout.lane_positions[start_lane]
            end_x = constants.layout.lane_positions[end_lane]
            center_x = (start_x + end_x) // 2

            obs_left = center_x - sprite_width // 2
            obs_right = center_x + sprite_width // 2
            obs_top = obs['y_pos']
            obs_bottom = obs['y_pos'] + sprite_height

            horizontal_overlap = not (bat_right < obs_left or bat_left > obs_right)
            vertical_overlap = not (bat_bottom < obs_top or bat_top > obs_bottom)

            if horizontal_overlap and vertical_overlap:
                state.enemies.obstacles.remove(obs)
