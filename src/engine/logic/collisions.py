"""Bird, bat, obstacle and projectile collisions."""

import random

from src.core import constants, state
from src.engine import bird_kinds, clock, enemy_stats, events, hazards, stats
from src.engine.birds import check_pending_transforms, reset_bird_power, scare_bird, set_ball_vy, stun_bird
from src.engine.logic import afflictions, bat_abilities
from src.engine.logic.damage import calculate_bird_damage, handle_bat_death
from src.engine.logic.drops import drop_loot
from src.engine.logic.flowers import apply_flower_collision_effect
from src.engine.logic.helpers import get_obstacle_lanes
from src.engine.logic.mini_bats import handle_obstacle_destroyed, try_spawn_mini_bat_on_hit
from src.engine.progression import add_score, award_damage_xp, award_xp
from src.entities.sprites import (
    BLUE,
    CLOCKWORK,
    FLOWER_MATURE_FRAME,
    OBSTACLE_LANE_WIDTH,
    OBSTACLE_SPRITE_T1,
    OBSTACLE_SPRITES,
    ORANGE,
    RAINBOW,
    ROCK,
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
                drop_loot(
                    {
                        'x_pos': constants.layout.lane_positions[lane],
                        'y_pos': constants.layout.starting_line,
                        'type': 'orange_egg',
                        'rarity': 'epic',
                        'spawn_ts': clock.now(),
                    },
                    'orange',
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

        # Lucky birds (Glitch) bounce back from the floor
        floor_save = stats.bird(i, 'floor_save')
        if floor_save > 0 and random.random() < floor_save:
            state.birds.y[i] = constants.layout.starting_line
            set_ball_vy(i, -1)
            reset_bird_power(i)
            continue

        # Bird dies (a zombie a necromancer raised was never yours: no life lost)
        dead_color = state.birds.colors[i]
        state.birds.lost[i] = True
        state.birds.y[i] = constants.layout.height - 1
        state.birds.per_bird_xp[i] = 0
        if bat_abilities.lost_raised_zombie(i):
            events.emit('bird_lost', bird=i, color=dead_color, cause='zombie')
            continue
        state.game.lives -= 1
        events.emit('bird_lost', bird=i, color=dead_color, cause='floor')

        # Check if a pending bird can now transform

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
        if bird_kinds.is_intangible(i):
            continue

        for obs in state.enemies.obstacles[:]:
            if hazards.is_emerging(obs):
                continue  # still rising out of the ground: not solid yet
            # Check if bird lane is within obstacle's lanes
            obs_lanes = get_obstacle_lanes(obs)
            if bird_lane not in obs_lanes and not obs_lanes.intersection(bird_kinds.covered_lanes(i)):
                continue

            # Check vertical proximity (consider sprite height)
            obs_tier = obs.get('tier', 1)
            sprite_height = len(obs.get('sprite') or OBSTACLE_SPRITES.get(obs_tier, OBSTACLE_SPRITE_T1))
            if next_y < obs['y_pos'] - 1 or next_y > obs['y_pos'] + sprite_height:
                continue

            # Hit obstacle
            damage = calculate_bird_damage(i, 'obstacle')

            # Check if obstacle has a mature flower - apply effect before damage
            flower = obs.get('flower')

            if flower and flower.get('active') and flower.get('frame', 0) >= FLOWER_MATURE_FRAME:
                apply_flower_collision_effect(flower, i)

            if bird_color == ORANGE:
                obs['hp'] = 0
            else:
                obs['hp'] -= enemy_stats.mitigate(obs, damage, 'contact', bird=i)
                award_damage_xp(i, damage)
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
                if obs.get('blast'):
                    bat_abilities.stone_blast(obs, bird=i)
            else:
                set_ball_vy(i, 1)
                # Stunned (cannot bounce) for the obstacle's stun seconds; peaks also knock it down
                stun_bird(i, enemy_stats.get(obs, 'stun'))
                knock = enemy_stats.get(obs, 'knock')
                if knock:
                    state.special.dive_fall_boosts[i] = {
                        'frames': int(enemy_stats.get(obs, 'knock_time') / constants.timing.base_sleep),
                        'speed': knock,
                    }
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

        bird_color = state.birds.colors[i]
        next_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_kinds.is_intangible(i):
            continue

        bird_height = bird_kinds.height(i)

        for bat in state.enemies.bats[:]:
            bat_left = bat['x_pos']
            bat_right = bat['x_pos'] + 8
            bat_top = bat['y_pos']
            bat_bottom = bat['y_pos'] + 1

            lane_left, lane_right = bird_kinds.hit_span(i)

            horizontal_overlap = not (bat_right < lane_left or bat_left > lane_right)
            vertical_overlap = not (next_y + bird_height < bat_top or next_y > bat_bottom)

            if not (horizontal_overlap and vertical_overlap):
                continue

            # Hit bat
            damage = calculate_bird_damage(i, 'elite' if bat.get('elite') else 'bat')
            if state.special.speed_boosts.get(i, 0) > 0 and state.birds.colors[i] == BLUE:
                events.emit('power_effect', bird=i, kind='BLUE', effect='sprint hits', count=1)

            # Defences and armor (armor is lowered by FROZEN/BLEEDING debuffs)
            if bird_color != ORANGE:
                damage = enemy_stats.mitigate(bat, damage, 'contact', bird=i, armor_cut=afflictions.armor_cut(bat))

            if bird_color == ORANGE:
                bat['hp'] = 0
            else:
                bat['hp'] -= damage
                award_damage_xp(i, damage)

            # Check if diver bat in stunned/returning state (no scare)
            is_diver = bat.get('diver', False)
            diver_state = bat.get('diver_state', 'flying')
            diver_no_scare = is_diver and diver_state in ('stunned', 'returning')

            # Apply scared effect (unless stealth tangible or diver stunned/returning)
            is_stealth_tangible = bird_kinds.is_phased_in(i)
            if not is_stealth_tangible and not diver_no_scare:
                scared_duration = getattr(constants.combat, 'scared_duration', 2.0)
                fear = scared_duration * enemy_stats.get(bat, 'fear_strength')
                scare_bird(i, fear, enemy_stats.get(bat, 'fear_push'))
                _scare_neighbours(i, bat, scared_duration)
            # Plague bats infect the bird that touches them
            if 'plague' in enemy_stats.bat_kinds(bat):
                bat_abilities.infect(i, bat)
            # Elite armored bats knock the bird down hard
            knock = enemy_stats.get(bat, 'knock')
            if knock and bat['hp'] > 0:
                state.special.dive_fall_boosts[i] = {
                    'frames': int(enemy_stats.get(bat, 'knock_time') / constants.timing.base_sleep),
                    'speed': knock,
                }

            # A bird that hits a diver mid-dive is pushed down faster for a moment
            if is_diver and diver_state == 'diving':
                state.special.dive_fall_boosts[i] = {
                    'frames': int(enemy_stats.get(bat, 'dive_push_time') / constants.timing.base_sleep),
                    'speed': enemy_stats.get(bat, 'dive_push'),
                }

            # Knockback pushes the bat up (Rock: 2 rows while its power is active)
            push_rows = int(stats.bird(i, 'knockback'))
            if bird_color == ROCK:
                now = clock.now()
                if i in state.special.rock_boosted and now < state.special.rock_boosted[i]:
                    push_rows = max(push_rows, getattr(constants.rock, 'boosted_push_rows', 2))
            if push_rows > 0:
                # Push bat up (decrease y_pos, but not above 0)
                bat['y_pos'] = max(0, bat['y_pos'] - push_rows)
                bat['target_y'] = max(0, bat['target_y'] - push_rows)

            # Frosty / Poison / Berserk: maybe freeze, poison or make the bat bleed
            afflictions.try_afflict(i, bat)

            if bat['hp'] <= 0:
                handle_bat_death(bat, i)
            else:
                set_ball_vy(i, 1)
                state.birds.y[i] = bat_bottom + 1
                if bird_color == BLUE:
                    reset_bird_power(i)
            break


def _scare_neighbours(bird_idx, bat, seconds):
    """A bat with fear_radius also scares the birds in the lanes around the one it hit."""
    radius = int(enemy_stats.get(bat, 'fear_radius'))
    if radius <= 0:
        return
    lane = state.birds.random_lanes[bird_idx]
    for j in range(constants.layout.num_balls):
        if j == bird_idx or state.birds.lost[j]:
            continue
        if 0 < abs(state.birds.random_lanes[j] - lane) <= radius:
            scare_bird(j, seconds * enemy_stats.get(bat, 'fear_strength'), enemy_stats.get(bat, 'fear_push'))


def _afflict_from_shot(proj, target, is_boss=False):
    """Frosty / Poison next to the shooter: the shot freezes or poisons what it hits."""
    for j in proj.get('afflict', ()):
        if 0 <= j < len(state.birds.lost) and not state.birds.lost[j]:
            afflictions.try_afflict(j, target, is_boss=is_boss, always=True)


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
                damage = enemy_stats.mitigate(bat, proj.get('damage', 1), 'projectile')
                bat['hp'] -= damage

                owner = proj.get('owner')
                if owner is not None:
                    award_damage_xp(owner, damage, 'shot')

                if bat['hp'] <= 0:
                    handle_bat_death(bat, owner if owner is not None else 0)
                else:
                    _afflict_from_shot(proj, bat)

                events.emit('shot_hit', bird=proj.get('owner'), kind=proj.get('color'), damage=proj.get('damage', 0))

                if proj in state.special.red_projectiles:
                    state.special.red_projectiles.remove(proj)
                removed = True
                break

        if removed:
            continue

        # Check obstacle collision
        for obs in state.enemies.obstacles[:]:
            if hazards.is_emerging(obs):
                continue
            # Check if projectile lane is within obstacle's lanes
            obs_lanes = get_obstacle_lanes(obs)
            if proj['lane'] not in obs_lanes:
                continue

            # Check vertical proximity (consider sprite height)
            obs_tier = obs.get('tier', 1)
            sprite_height = len(obs.get('sprite') or OBSTACLE_SPRITES.get(obs_tier, OBSTACLE_SPRITE_T1))
            if proj['y_pos'] < obs['y_pos'] - 1 or proj['y_pos'] > obs['y_pos'] + sprite_height:
                continue

            damage = enemy_stats.mitigate(obs, proj.get('damage', 1), 'projectile')
            obs['hp'] -= damage

            owner = proj.get('owner')
            if owner is not None:
                award_damage_xp(owner, damage, 'shot')

            if obs['hp'] <= 0:
                tier = obs.get('tier', 1)
                if owner is not None:
                    xp_per_tier = getattr(constants.combat, 'obstacle_destroy_xp_per_tier', 5)
                    award_xp(owner, xp_per_tier * tier)
                score_per_tier = getattr(constants.combat, 'obstacle_destroy_score_per_tier', 50)
                add_score(tier * score_per_tier)
                state.enemies.obstacles.remove(obs)
                if obs.get('blast'):
                    bat_abilities.stone_blast(obs)

            events.emit('shot_hit', bird=proj.get('owner'), kind=proj.get('color'), damage=proj.get('damage', 0))

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
                            award_damage_xp(owner, damage, 'shot')
                        if flower['hp'] <= 0:
                            flower['active'] = False
                            tree_boss_cfg = getattr(constants, 'tree_boss', None)
                            flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None
                            respawn_delay = getattr(flowers_cfg, 'respawn_delay', 3.0) if flowers_cfg else 3.0
                            flower['respawn_timer'] = clock.now() + respawn_delay
                    else:
                        # Damage branch
                        branch['hp'] -= damage
                        if owner is not None:
                            award_damage_xp(owner, damage, 'shot')
                        if branch['hp'] <= 0:
                            branch['destroyed'] = True
                            add_score(100)

                    events.emit(
                        'shot_hit', bird=proj.get('owner'), kind=proj.get('color'), damage=proj.get('damage', 0)
                    )

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
                    award_damage_xp(owner, damage, 'shot')

                play_sfx('hit')

                if boss['hp'] <= 0:
                    boss['state'] = 'dying'
                    play_sfx('boss_death')
                else:
                    _afflict_from_shot(proj, boss, is_boss=True)

                events.emit('shot_hit', bird=proj.get('owner'), kind=proj.get('color'), damage=proj.get('damage', 0))

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
            if hazards.is_emerging(obs):
                continue
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
