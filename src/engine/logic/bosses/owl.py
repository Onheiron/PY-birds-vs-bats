"""Owl Boss (Haunted Woods)."""

import math
import random

from src.core import constants, state
from src.engine import clock
from src.engine.logic.drops import drop_loot
from src.engine.loot_tables import adjust_rarity_weights, choose_loot_type
from src.engine.progression import add_score, award_xp, compute_prestige
from src.entities.sprites import METEOR_LEFT, METEOR_RIGHT, OWL_BOSS_SPELLS, PORTAL_FRAME_1, SWAMP_OBSTACLE_T2


def spawn_owl_boss():
    """Spawn the Owl Boss for level 5-3 (The Void Cave).

    The Owl Boss is a wizard owl that cycles through spell stages:
    - fly (4s): Normal flight, moving left/right
    - conjure (4s): Preparing a spell (eyes narrow)
    - cast (4s): Releasing the spell (eyes star)
    - recharge (4s): Recovering after spell (eyes drowsy)

    Spells cycle through:
    1. overgrowth - Conjures 5 tree obstacles with flowers
    2. terror - Swaps all birds to outer lanes
    3. ominous_wind - Headwind pushing birds down
    4. evocation - Summons 3 special bats
    5. bend_space - Creates portal pairs
    6. bend_time - Slows game time (boss continues at normal speed)
    7. meteor_shower - Summons falling meteors
    """
    owl_boss_cfg = getattr(constants, 'owl_boss', None)
    hp = getattr(owl_boss_cfg, 'hp', 500) if owl_boss_cfg else 500

    # Owl boss sprite is 5 lines tall, ~11 chars wide
    boss_sprite_height = 5
    boss_sprite_width = 11
    base_x = (constants.layout.width - boss_sprite_width) // 2

    # Target Y at 1/3 from top
    target_y_frac = getattr(owl_boss_cfg, 'target_y_fraction', 0.33) if owl_boss_cfg else 0.33
    target_y = int(constants.layout.starting_line * target_y_frac)

    # Stage duration from config
    stage_duration = getattr(owl_boss_cfg, 'stage_duration', 4.0) if owl_boss_cfg else 4.0
    stage_frames = int(stage_duration / constants.timing.base_sleep)

    state.enemies.boss = {
        'x_pos': base_x,
        'base_x_pos': base_x,
        'y_pos': -boss_sprite_height,
        'target_y': target_y,
        'hp': hp,
        'max_hp': hp,
        'state': 'descending',
        'boss_type': 'owl',
        'spawn_ts': clock.now(),
        # Animation
        'anim_frame': 0,  # 0 or 1 for wing animation
        'anim_timer': 0,
        # Spell cycle state
        'stage': 'fly',  # Current stage: fly, conjure, cast, recharge
        'stage_timer': stage_frames,  # Frames remaining in current stage
        'stage_frames': stage_frames,  # Total frames per stage
        'spell_index': 0,  # Current spell in cycle (0-6)
        'spell_cast': False,  # Whether spell was already cast this cycle
        # Oscillation
        'oscillation_dir': 1,
        'oscillation_timer': 0,
        # Spell-specific state
        'owl_portals': [],  # Active portals from bend_space
        'owl_meteors': [],  # Active meteors from meteor_shower
        'owl_wind_end_time': 0,  # When ominous_wind ends
        'bend_time_active': False,  # Whether bend_time slowdown is active
        'bend_time_end_time': 0,  # When bend_time ends
    }
    state.enemies.boss_spawned = True
    # Don't clear all bats - evocation spawns bats
    state.enemies.obstacles = []


def update_owl_boss():
    """Update the Owl Boss state and behavior."""
    boss = state.enemies.boss
    if boss is None or boss.get('boss_type') != 'owl':
        return

    owl_boss_cfg = getattr(constants, 'owl_boss', None)
    current_time = clock.now()

    # Check if boss is dead
    if boss['hp'] <= 0:
        _owl_boss_defeated(boss)
        return

    boss_state = boss['state']

    # Update bend_time effect (affects game speed, not boss)
    if boss.get('bend_time_active') and current_time >= boss.get('bend_time_end_time', 0):
        boss['bend_time_active'] = False
        state.powerups.timelapse_active = False
        state.powerups.timelapse_slowdown = 1.0

    # Update ominous_wind effect
    if boss.get('owl_wind_end_time', 0) > 0 and current_time >= boss['owl_wind_end_time']:
        boss['owl_wind_end_time'] = 0
        state.powerups.wind_boss_up_bonus = 0
        state.powerups.wind_boss_down_penalty = 0

    # Update owl meteors
    _update_owl_meteors(boss)

    # Portals are now handled by update_portals() using state.enemies.portals

    if boss_state == 'descending':
        # Move boss down until at target Y
        descent_speed = getattr(owl_boss_cfg, 'descent_speed', 6) if owl_boss_cfg else 6
        if state.game.frame_count % descent_speed == 0:
            boss['y_pos'] += 1
            if boss['y_pos'] >= boss.get('target_y', 8):
                boss['state'] = 'fly'
                boss['y_pos'] = boss['target_y']

    elif boss_state in ('fly', 'conjure', 'cast', 'recharge'):
        # Animation frame cycling (wing flap)
        anim_speed = getattr(owl_boss_cfg, 'anim_frames_per_step', 8) if owl_boss_cfg else 8
        boss['anim_timer'] = boss.get('anim_timer', 0) + 1
        if boss['anim_timer'] >= anim_speed:
            boss['anim_timer'] = 0
            boss['anim_frame'] = (boss['anim_frame'] + 1) % 2

        # Oscillation movement
        oscillation_speed = getattr(owl_boss_cfg, 'oscillation_speed', 10) if owl_boss_cfg else 10
        oscillation_range = getattr(owl_boss_cfg, 'oscillation_range', 8) if owl_boss_cfg else 8
        boss['oscillation_timer'] = boss.get('oscillation_timer', 0) + 1
        if boss['oscillation_timer'] >= oscillation_speed:
            boss['oscillation_timer'] = 0
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

        # Stage timer
        boss['stage_timer'] = boss.get('stage_timer', 0) - 1

        # Cast spell during 'cast' stage (once per cycle)
        if boss_state == 'cast' and not boss.get('spell_cast', False):
            _owl_boss_cast_spell(boss)
            boss['spell_cast'] = True

        # Stage transition
        if boss['stage_timer'] <= 0:
            stage_cycle = ['fly', 'conjure', 'cast', 'recharge']
            current_idx = stage_cycle.index(boss_state) if boss_state in stage_cycle else 0
            next_idx = (current_idx + 1) % len(stage_cycle)
            boss['state'] = stage_cycle[next_idx]
            boss['stage_timer'] = boss.get('stage_frames', 80)

            # Reset spell_cast flag when entering 'fly' stage (new cycle)
            if boss['state'] == 'fly':
                boss['spell_cast'] = False
                # Advance to next spell
                spell_count = 7  # Total spells
                boss['spell_index'] = (boss.get('spell_index', 0) + 1) % spell_count

    elif boss_state == 'dying':
        _convert_owl_boss_to_obstacle(boss)
        state.enemies.boss = None
        state.enemies.boss_defeated = True


def _owl_boss_cast_spell(boss):
    """Cast the current spell in the Owl Boss cycle."""

    spell_index = boss.get('spell_index', 0)
    spells = OWL_BOSS_SPELLS
    spell_name = spells[spell_index % len(spells)]

    owl_boss_cfg = getattr(constants, 'owl_boss', None)
    spells_cfg = getattr(owl_boss_cfg, 'spells', None) if owl_boss_cfg else None

    if spell_name == 'overgrowth':
        _owl_cast_overgrowth(boss, spells_cfg)
    elif spell_name == 'terror':
        _owl_cast_terror(boss, spells_cfg)
    elif spell_name == 'ominous_wind':
        _owl_cast_ominous_wind(boss, spells_cfg)
    elif spell_name == 'evocation':
        _owl_cast_evocation(boss, spells_cfg)
    elif spell_name == 'bend_space':
        _owl_cast_bend_space(boss, spells_cfg)
    elif spell_name == 'bend_time':
        _owl_cast_bend_time(boss, spells_cfg)
    elif spell_name == 'meteor_shower':
        _owl_cast_meteor_shower(boss, spells_cfg)


def _owl_cast_overgrowth(boss, spells_cfg):
    """Conjure 5 STATIONARY tree obstacles in a circle around the boss, each with a bloomed flower."""
    cfg = getattr(spells_cfg, 'overgrowth', None) if spells_cfg else None
    tree_count = getattr(cfg, 'tree_count', 5) if cfg else 5
    tree_hp = getattr(cfg, 'tree_hp', 40) if cfg else 40

    boss_center_x = boss['x_pos'] + 5
    boss_y = boss['y_pos'] + 5  # Below the boss

    # Import swamp obstacles T2 (smaller, tree-like)

    # 5 positions in a circle around the boss
    # Angle offsets for 5 points: 0°, 72°, 144°, 216°, 288°
    radius_x = 12  # Horizontal radius in characters
    radius_y = 6  # Vertical radius in rows

    flower_types = ['red', 'yellow', 'blue', 'green']

    for i in range(tree_count):
        # Calculate position in circle
        angle = (2 * math.pi * i / tree_count) - math.pi / 2  # Start from top
        offset_x = int(radius_x * math.cos(angle))
        offset_y = int(radius_y * math.sin(angle))

        x_pos = boss_center_x + offset_x
        y_pos = boss_y + offset_y

        # Clamp to screen
        x_pos = max(2, min(constants.layout.width - 8, x_pos))
        y_pos = max(2, min(constants.layout.starting_line - 4, y_pos))

        # Find closest lane
        closest_lane = min(
            range(constants.layout.num_lanes), key=lambda lane: abs(constants.layout.lane_positions[lane] - x_pos)
        )

        obstacle_id = state.enemies.obstacle_id_counter
        state.enemies.obstacle_id_counter += 1

        obstacle = {
            'id': obstacle_id,
            'lane': closest_lane,
            'x_pos': constants.layout.lane_positions[closest_lane],
            'y_pos': y_pos,
            'tier': 2,  # TIER 2
            'hp': tree_hp,
            'max_hp': tree_hp,
            'sprite': SWAMP_OBSTACLE_T2,
            'sprite_width': max(len(line) for line in SWAMP_OBSTACLE_T2),
            'from_owl_boss': True,
            'stationary': True,  # Does NOT move down!
        }

        # ALWAYS add a fully bloomed flower
        obstacle['flower'] = {
            'type': flower_types[i % len(flower_types)],  # Cycle through colors
            'active': True,
            'frame': 5,  # Fully mature (frame 5 = bloomed)
            'hp': 20,
            'rel_x': 5,  # Position on sprite
            'rel_y': 0,
        }

        state.enemies.obstacles.append(obstacle)


def _owl_cast_terror(boss, spells_cfg):
    """Swap all birds to random UNIQUE lanes."""
    # Get living birds
    living_birds = [i for i in range(constants.layout.num_balls) if not state.birds.lost[i]]
    if len(living_birds) <= 1:
        return

    num_lanes = constants.layout.num_lanes

    # Create list of available lanes (0 to num_lanes-1)
    available_lanes = list(range(num_lanes))
    random.shuffle(available_lanes)

    # Assign each living bird a UNIQUE lane from the shuffled list
    for i, bird_idx in enumerate(living_birds):
        if i < len(available_lanes):
            new_lane = available_lanes[i]
            state.birds.random_lanes[bird_idx] = new_lane
            state.birds.home_lanes[bird_idx] = new_lane  # ALSO update home lane!
            state.birds.cols[bird_idx] = constants.layout.lane_positions[new_lane]


def _owl_cast_ominous_wind(boss, spells_cfg):
    """Create headwind pushing birds down."""
    cfg = getattr(spells_cfg, 'ominous_wind', None) if spells_cfg else None
    duration = getattr(cfg, 'duration', 4.0) if cfg else 4.0
    down_bonus = getattr(cfg, 'down_bonus', 3) if cfg else 3
    up_penalty = getattr(cfg, 'up_penalty', 2) if cfg else 2

    boss['owl_wind_end_time'] = clock.now() + duration
    # Use wind_boss effects (negative = headwind)
    state.powerups.wind_boss_up_bonus = -up_penalty
    state.powerups.wind_boss_down_penalty = -down_bonus


def _owl_cast_evocation(boss, spells_cfg):
    """Summon special bats (armored, diver, spellcaster) - ALWAYS special, never normal!"""
    cfg = getattr(spells_cfg, 'evocation', None) if spells_cfg else None
    bat_count = getattr(cfg, 'bat_count', 3) if cfg else 3
    tier_min = getattr(cfg, 'bat_tier_min', 2) if cfg else 2
    tier_max = getattr(cfg, 'bat_tier_max', 4) if cfg else 4

    for _ in range(bat_count):
        tier = random.randint(tier_min, tier_max)

        # Random X position
        x_pos = random.randint(5, constants.layout.width - 10)
        target_y = random.randint(5, 12)

        # Get HP for tier
        hp_by_tier = getattr(constants.bat_enemy, 'hp_by_tier', {})
        hp = hp_by_tier.get(tier, tier * 24) if isinstance(hp_by_tier, dict) else tier * 24

        # Always spawn special bats - pick type (no normal bats!)
        special_type = random.choice(['armored', 'diver', 'spellcaster'])

        # Adjust tier requirements
        if special_type == 'armored' and tier < 2:
            special_type = 'diver'  # Diver works at any tier
        if special_type == 'spellcaster' and tier < 2:
            special_type = 'diver'

        bat = {
            'x_pos': x_pos,
            'y_pos': -2,  # Start above screen like normal bats
            'direction': random.choice([-1, 1]),
            'tier': tier,
            'hp': hp,
            'max_hp': hp,
            'target_y': target_y,
            'spawn_ts': clock.now(),
            'from_owl_boss': True,
            'armored': False,
            'diver': False,
            'spellcaster': False,
        }

        # Set special type with correct field names (same as spawn_bat)
        if special_type == 'armored':
            bat['armored'] = True
        elif special_type == 'diver':
            bat['diver'] = True
            bat['diver_state'] = 'flying'
            bat['diver_home_y'] = target_y
            bat['dive_start_y'] = None
            bat['stun_end_time'] = None
        elif special_type == 'spellcaster':
            bat['spellcaster'] = True
            bat['spell_state'] = 'idle'
            bat['spell_cooldown'] = 0
            bat['casting_end_time'] = None
            # Determine known spells based on tier
            spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
            spells_by_tier = getattr(spellcaster_cfg, 'spells_by_tier', None) if spellcaster_cfg else None
            if spells_by_tier:
                if isinstance(spells_by_tier, dict):
                    num_spells = spells_by_tier.get(tier, spells_by_tier.get(str(tier), 1))
                else:
                    num_spells = getattr(spells_by_tier, str(tier), 1)
            else:
                num_spells = min(tier - 1, 3)
            all_spells = ['silence', 'repugnant_wind', 'exile']
            bat['known_spells'] = all_spells[:num_spells]

        state.enemies.bats.append(bat)


def _owl_cast_bend_space(boss, spells_cfg):
    """Create portal pairs using the SAME portal system as biome 5 (state.enemies.portals)."""
    # Don't create more portals if there are already owl boss portals active!
    owl_portals = [p for p in state.enemies.portals if p.get('from_owl_boss')]
    if owl_portals:
        return  # Already have portals, don't spawn more

    # Clear any existing non-owl portals first
    state.enemies.portals = []

    cfg = getattr(spells_cfg, 'bend_space', None) if spells_cfg else None
    portal_pairs_count = getattr(cfg, 'portal_pairs', 2) if cfg else 2  # Read from config
    portal_duration_sec = getattr(cfg, 'portal_duration', 15.0) if cfg else 15.0  # Read from config

    # Use same portal structure as spawn_portal_pair() in biome 5

    portal_width = max(len(line) for line in PORTAL_FRAME_1)
    portal_height = len(PORTAL_FRAME_1)

    lane_positions = constants.layout.lane_positions
    num_lanes = constants.layout.num_lanes
    game_height = constants.layout.starting_line

    # Convert duration to frames
    duration_frames = int(portal_duration_sec / constants.timing.base_sleep)
    expire_frame = state.game.frame_count + duration_frames

    # Create portal pairs across different lanes
    used_lanes = set()
    for _ in range(portal_pairs_count):
        # Pick two different lanes
        available = [lane for lane in range(num_lanes) if lane not in used_lanes]
        if len(available) < 2:
            available = list(range(num_lanes))  # Reuse if needed

        lane1 = random.choice(available)
        available.remove(lane1)
        lane2 = random.choice(available)

        used_lanes.add(lane1)
        used_lanes.add(lane2)

        # Positions
        x1 = lane_positions[lane1] - portal_width // 2
        x2 = lane_positions[lane2] - portal_width // 2

        # Y positions - one in upper half, one in lower half
        y1 = random.randint(3, game_height // 2)
        y2 = random.randint(game_height // 2, (game_height * 2) // 3)

        pair_id = state.enemies.portal_pair_counter
        state.enemies.portal_pair_counter += 1

        portal_a = {
            'x_pos': x1,
            'y_pos': y1,
            'pair_id': pair_id,
            'portal_idx': 0,
            'lane': lane1,
            'width': portal_width,
            'height': portal_height,
            'expire_frame': expire_frame,
            'from_owl_boss': True,  # Mark as owl boss portal
        }

        portal_b = {
            'x_pos': x2,
            'y_pos': y2,
            'pair_id': pair_id,
            'portal_idx': 1,
            'lane': lane2,
            'width': portal_width,
            'height': portal_height,
            'expire_frame': expire_frame,
            'from_owl_boss': True,
        }

        state.enemies.portals.append(portal_a)
        state.enemies.portals.append(portal_b)


def _owl_cast_bend_time(boss, spells_cfg):
    """Slow game time while boss continues at normal speed."""
    cfg = getattr(spells_cfg, 'bend_time', None) if spells_cfg else None
    duration = getattr(cfg, 'duration', 4.0) if cfg else 4.0
    slowdown = getattr(cfg, 'slowdown_factor', 2.0) if cfg else 2.0

    boss['bend_time_active'] = True
    boss['bend_time_end_time'] = clock.now() + duration

    # Use timelapse system for slowdown
    state.powerups.timelapse_active = True
    state.powerups.timelapse_end_time = clock.now() + duration
    state.powerups.timelapse_slowdown = slowdown


def _owl_cast_meteor_shower(boss, spells_cfg):
    """Summon 2 large meteors - one on left, one on right."""

    cfg = getattr(spells_cfg, 'meteor_shower', None) if spells_cfg else None
    meteor_hp = getattr(cfg, 'meteor_hp', 80) if cfg else 80
    speed_mult = getattr(cfg, 'speed_multiplier', 1.5) if cfg else 1.5

    # Warp boss to center lane
    center_x = (constants.layout.width - 11) // 2
    boss['x_pos'] = center_x
    boss['base_x_pos'] = center_x

    # Calculate meteor widths from sprites
    left_width = max(len(line) for line in METEOR_LEFT)
    right_width = max(len(line) for line in METEOR_RIGHT)

    # Spawn LEFT meteor (left side of screen)
    left_x = 2  # Near left edge
    boss['owl_meteors'].append(
        {
            'x_pos': left_x,
            'y_pos': -len(METEOR_LEFT),  # Start above screen
            'hp': meteor_hp,
            'max_hp': meteor_hp,
            'width': left_width,
            'height': len(METEOR_LEFT),
            'speed_mult': speed_mult,
            'move_timer': 0,
            'side': 'left',
        }
    )

    # Spawn RIGHT meteor (right side of screen)
    right_x = constants.layout.width - right_width - 2  # Near right edge
    boss['owl_meteors'].append(
        {
            'x_pos': right_x,
            'y_pos': -len(METEOR_RIGHT),  # Start above screen
            'hp': meteor_hp,
            'max_hp': meteor_hp,
            'width': right_width,
            'height': len(METEOR_RIGHT),
            'speed_mult': speed_mult,
            'move_timer': 0,
            'side': 'right',
        }
    )


def _update_owl_meteors(boss):
    """Update owl boss meteors."""
    meteors = boss.get('owl_meteors', [])
    if not meteors:
        return

    surviving = []
    for meteor in meteors:
        # Move meteor down
        meteor['move_timer'] = meteor.get('move_timer', 0) + 1
        move_interval = max(1, int(6 / meteor.get('speed_mult', 1.5)))

        if meteor['move_timer'] >= move_interval:
            meteor['move_timer'] = 0
            meteor['y_pos'] += 1

        # Check if off screen or destroyed
        if meteor['y_pos'] > constants.layout.starting_line:
            continue  # Remove meteor
        if meteor.get('hp', 1) <= 0:
            continue  # Destroyed

        surviving.append(meteor)

    boss['owl_meteors'] = surviving


def _owl_boss_defeated(boss):
    """Handle Owl Boss defeat."""
    if boss.get('state') == 'dying':
        return

    owl_boss_cfg = getattr(constants, 'owl_boss', None)

    # Award score and XP
    score = getattr(owl_boss_cfg, 'score', 2500) if owl_boss_cfg else 2500
    xp = getattr(owl_boss_cfg, 'xp', 250) if owl_boss_cfg else 250
    add_score(score)

    for i in range(constants.layout.num_balls):
        if not state.birds.lost[i]:
            living_count = sum(1 for j in range(constants.layout.num_balls) if not state.birds.lost[j])
            award_xp(i, xp // max(1, living_count))

    # Clear owl-specific effects
    boss['owl_portals'] = []
    boss['owl_meteors'] = []
    boss['owl_wind_end_time'] = 0
    state.powerups.wind_boss_up_bonus = 0
    state.powerups.wind_boss_down_penalty = 0

    if boss.get('bend_time_active'):
        boss['bend_time_active'] = False
        state.powerups.timelapse_active = False
        state.powerups.timelapse_slowdown = 1.0

    # Drop loot
    prestige = compute_prestige()
    base_weights = getattr(constants.loot, 'base_rarity_weights', [1, 0.1, 0.01, 0.001, 0.0001, 0.00001])
    if not isinstance(base_weights, list):
        base_weights = [1, 0.1, 0.01, 0.001, 0.0001, 0.00001]
    adj_weights = adjust_rarity_weights(base_weights, prestige)

    for i in range(4):  # 4 loot drops
        rarity = random.choices(['common', 'uncommon', 'rare', 'epic', 'legendary', 'mythical'], weights=adj_weights)[0]
        loot_type = choose_loot_type(rarity)

        lane = (i * 2) % constants.layout.num_lanes
        drop_loot(
            {
                'x_pos': constants.layout.lane_positions[lane],
                'y_pos': boss['y_pos'] + 2 + i,
                'type': loot_type,
                'rarity': rarity,
                'spawn_ts': clock.now(),
            },
            'boss',
        )

    boss['state'] = 'dying'


def _convert_owl_boss_to_obstacle(boss):
    """Convert dead Owl Boss to a falling obstacle."""
    owl_boss_cfg = getattr(constants, 'owl_boss', None)
    corpse_cfg = getattr(owl_boss_cfg, 'corpse', None) if owl_boss_cfg else None
    hp = getattr(corpse_cfg, 'hp', 100) if corpse_cfg else 100

    boss_center_x = boss['x_pos'] + 5
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
            'tier': 5,  # Special tier for boss corpse
            'hp': hp,
            'max_hp': hp,
            'sprite_width': 11,
            'is_owl_boss_corpse': True,
        }
    )
