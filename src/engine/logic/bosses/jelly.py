"""Jelly Boss (Rotten Marshes)."""

from src.core import constants, state
from src.engine import clock, enemy_stats
from src.engine.logic.bosses.common import get_boss_config, scaled_hp
from src.engine.logic.drops import drop_loot
from src.engine.loot_tables import choose_loot_type, roll_drop_rarity
from src.engine.progression import add_score, award_xp


def spawn_jelly_boss():
    """Spawn the Jelly Boss for level 3-3."""
    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)
    hp = getattr(jelly_boss_cfg, 'hp', 400) if jelly_boss_cfg else 400
    hp = scaled_hp(hp)

    # Jelly boss is 6 lines tall
    boss_sprite_height = 6
    boss_sprite_width = 23  # Width of jelly boss sprite
    base_x = (constants.layout.width - boss_sprite_width) // 2

    # Target Y at 1/4 from top
    target_y_frac = getattr(jelly_boss_cfg, 'target_y_fraction', 0.25) if jelly_boss_cfg else 0.25
    target_y = int(constants.layout.starting_line * target_y_frac)

    state.enemies.boss = {
        'x_pos': base_x,
        'base_x_pos': base_x,
        'y_pos': -boss_sprite_height,
        'target_y': target_y,
        'hp': hp,
        'max_hp': hp,
        'state': 'descending',
        'anim_frame': 0,  # Index into animation sequence (0-9)
        'anim_timer': 0,  # Timer for animation steps
        'oscillation_dir': 1,
        'spawn_ts': clock.now(),
        'boss_type': 'jelly',
        'spawned_bats': 0,  # Number of bats spawned
        'bat_spawn_anim': None,  # Active spawn animation
    }
    state.enemies.boss_spawned = True


def update_jelly_boss():
    """Update Jelly Boss state and behavior."""
    boss = state.enemies.boss
    if boss is None:
        return

    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)
    boss_state = boss['state']

    if boss_state == 'descending':
        descent_speed = getattr(jelly_boss_cfg, 'descent_speed', 8) if jelly_boss_cfg else 8
        target_y = boss.get('target_y', 5)
        if state.game.frame_count % descent_speed == 0:
            boss['y_pos'] += 1
            if boss['y_pos'] >= target_y:
                boss['state'] = 'active'
                boss['y_pos'] = target_y

    elif boss_state == 'active':
        # Animation cycling through 10 frames
        anim_speed = getattr(jelly_boss_cfg, 'anim_frames_per_step', 30) if jelly_boss_cfg else 30
        boss['anim_timer'] = boss.get('anim_timer', 0) + 1

        if boss['anim_timer'] >= anim_speed:
            boss['anim_timer'] = 0
            boss['anim_frame']
            boss['anim_frame'] = (boss['anim_frame'] + 1) % 10  # 10 frames in sequence

            # Check if we just reached frame 8 (spawn frame, 1-indexed = frame index 7)
            spawn_frame = getattr(jelly_boss_cfg, 'spawn_frame', 8) if jelly_boss_cfg else 8
            spawn_frame_idx = spawn_frame - 1  # Convert to 0-indexed
            max_concurrent = getattr(jelly_boss_cfg, 'max_spawned_bats', 5) if jelly_boss_cfg else 5

            # Count currently ALIVE bats spawned by this boss (not total ever spawned)
            alive_boss_bats = sum(1 for bat in state.enemies.bats if bat.get('from_boss'))

            if boss['anim_frame'] == spawn_frame_idx and alive_boss_bats < max_concurrent:
                # Start bat spawn animation (o -> O -> () -> bat)
                boss['bat_spawn_anim'] = {
                    'active': True,
                    'frame': 0,  # Animation frame (0=o, 1=O, 2=(), 3=spawn bat)
                    'timer': 0,
                    'x_pos': boss['x_pos'] + 11,  # Center of boss head
                    'y_pos': boss['y_pos'] - 1,  # One row ABOVE boss (not inside)
                    'char': 'o',  # Starting character
                }

        # Update bat spawn animation if active
        _update_jelly_bat_spawn_anim(boss)

        # Oscillation movement
        oscillation_speed = getattr(jelly_boss_cfg, 'oscillation_speed', 10) if jelly_boss_cfg else 10
        oscillation_range = getattr(jelly_boss_cfg, 'oscillation_range', 3) if jelly_boss_cfg else 3
        if state.game.frame_count % oscillation_speed == 0:
            base_x = boss['base_x_pos']
            current_offset = boss['x_pos'] - base_x
            direction = boss.get('oscillation_dir', 1)
            new_offset = current_offset + direction
            if new_offset >= oscillation_range:
                new_offset = oscillation_range
                boss['oscillation_dir'] = -1
            elif new_offset <= -oscillation_range:
                new_offset = -oscillation_range
                boss['oscillation_dir'] = 1
            boss['x_pos'] = base_x + new_offset

    elif boss_state == 'dying':
        _convert_jelly_boss_to_obstacle(boss)
        state.enemies.boss = None
        state.enemies.boss_defeated = True


def _update_jelly_bat_spawn_anim(boss):
    """Update the bat spawn animation from jelly boss (o -> O -> () -> bat)."""
    anim = boss.get('bat_spawn_anim')
    if anim is None or not anim.get('active'):
        return

    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)
    anim_duration = getattr(jelly_boss_cfg, 'spawn_anim_duration', 0.5) if jelly_boss_cfg else 0.5
    # ~5 fps, so for 0.5s total with 4 frames = ~0.6 game frames per step
    # But let's use at least 1 frame per step
    frames_per_anim_step = max(1, int(anim_duration * 5 / 4))  # 5 fps, 4 animation steps

    anim['timer'] += 1
    if anim['timer'] >= frames_per_anim_step:
        anim['timer'] = 0
        anim['frame'] += 1

        # Update character based on frame: 0=o, 1=O, 2=(), 3=spawn bat
        if anim['frame'] == 1:
            anim['char'] = 'O'
        elif anim['frame'] == 2:
            anim['char'] = '()'
        elif anim['frame'] >= 3:
            # Animation complete, spawn the bat
            _spawn_bat_from_jelly_boss(boss, anim)
            boss['bat_spawn_anim'] = None
            boss['spawned_bats'] = boss.get('spawned_bats', 0) + 1


def _spawn_bat_from_jelly_boss(boss, anim):
    """Spawn a bat from the jelly boss animation: tier and kind as the world's bats (bat_enemy.worlds)."""
    from src.services.sound import play_sfx

    play_sfx('jelly_spawn')
    world = enemy_stats.world_table()
    tier = enemy_stats.roll_tier(world)
    table = constants.bat_enemy.hp_by_tier
    hp = table.get(tier, table.get(str(tier), 20)) if isinstance(table, dict) else getattr(table, str(tier), 20)
    kind = enemy_stats.roll_kind(tier, world)
    bat = enemy_stats.make_bat(
        tier,
        kind,
        anim['x_pos'] - 4,  # centre the bat sprite
        anim['y_pos'],
        boss['y_pos'] + 8,  # below the boss
        hp,
        from_boss=True,  # no loot
        descending_past_boss=True,  # still passing in front of the boss
    )
    state.enemies.spawn_queue.append({'type': 'bat', 'data': bat})


def _convert_jelly_boss_to_obstacle(boss):
    """Convert dead Jelly Boss to a falling obstacle."""
    boss_cfg = get_boss_config()
    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)

    corpse_cfg = getattr(jelly_boss_cfg, 'corpse', None) if jelly_boss_cfg else None
    hp = getattr(corpse_cfg, 'hp', 80) if corpse_cfg else 80

    boss_center_x = boss['x_pos'] + 11  # Jelly boss is ~23 chars wide
    closest_lane = min(
        range(constants.layout.num_lanes), key=lambda lane: abs(constants.layout.lane_positions[lane] - boss_center_x)
    )

    obstacle_id = state.enemies.obstacle_id_counter
    state.enemies.obstacle_id_counter += 1

    state.enemies.obstacles.append(
        {
            'id': obstacle_id,
            'lane': closest_lane,
            'x_pos': boss['x_pos'],
            'y_pos': boss['y_pos'],
            'tier': 5,
            'hp': hp,
            'max_hp': hp,
            'sprite_width': 23,
            'is_boss_corpse': True,
            'is_jelly_boss_corpse': True,
        }
    )

    # Award score and XP
    score = getattr(jelly_boss_cfg, 'score', 1500) if jelly_boss_cfg else 1500
    xp = getattr(jelly_boss_cfg, 'xp', 150) if jelly_boss_cfg else 150
    add_score(score)

    for i in range(constants.layout.num_balls):
        if not state.birds.lost[i]:
            award_xp(i, xp // max(1, sum(1 for j in range(constants.layout.num_balls) if not state.birds.lost[j])))

    # Drop loot
    loot_cfg = getattr(boss_cfg, 'loot', None)
    loot_count = getattr(loot_cfg, 'count', 3) if loot_cfg else 3

    for i in range(loot_count):
        rarity = roll_drop_rarity('boss')
        loot_type = choose_loot_type(rarity)

        lane_offset = i - loot_count // 2
        loot_lane = max(0, min(constants.layout.num_lanes - 1, closest_lane + lane_offset))

        drop_loot(
            {
                'x_pos': constants.layout.lane_positions[loot_lane],
                'y_pos': boss['y_pos'] + 3,
                'type': loot_type,
                'rarity': rarity,
                'spawn_ts': clock.now(),
            },
            'boss',
        )
