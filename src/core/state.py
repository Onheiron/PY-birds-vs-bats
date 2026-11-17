"""Mutable game state, organised in namespaces.

Import as ``from src.core import state`` and access ``state.birds.colors``,
``state.game.score`` and so on.

Every namespace is described once, by a ``_new_*`` factory holding its default
values. ``init()`` rebuilds the per-session namespaces from those factories, so
nothing can leak from one game into the next; ``settings`` and ``discovery``
deliberately survive across games.
"""

import random
import time
from types import SimpleNamespace

from src.core import constants
from src.entities.bird_types import BirdType, get_color_for_bird_type, get_default_speed

# Game seed for deterministic RNG (set on new game, saved/restored on load)
game_seed = None


# ============================================================================
# BIRDS STATE (organized as namespace)
# ============================================================================
def _new_birds():
    return SimpleNamespace(
        colors=[],
        cols=[],
        y=[],
        vy=[],
        speeds=[],
        lost=[],
        power_used=[],
        power_uses=[],
        random_lanes=[],  # Current physical lane
        home_lanes=[],  # "Home" lane - where bird would end up following portals down
        per_bird_xp=[],
        transformed=[],
        pending_transform=[],  # Bird wants to transform but can't (limit reached) - stores target color
        portal_cooldown={},  # {bird_idx: frame_until_can_teleport_again}
    )


# ============================================================================
# SPECIAL BIRDS STATE (organized as namespace)
# ============================================================================
def _new_special():
    return SimpleNamespace(
        # Red bird projectiles
        red_projectiles=[],
        # Speed boosts
        speed_boosts={},
        # Dive fall boosts (from diver bats in diving state)
        dive_fall_boosts={},
        # Dinosaur
        dinosaur_up_presses={},
        # Scared birds
        scared_birds={},
        # Stunned birds (from obstacle collision - short duration, no speed boost)
        stunned_birds={},
        # Frozen birds (from Tree Boss blue flower)
        # {bird_idx: {'thaw_attempts_needed': int, 'thaw_attempts_done': int}}
        frozen_birds={},
        # Poisoned birds (from Tree Boss green flower)
        # {bird_idx: {'death_time': float, 'cure_attempts_needed': int, 'cure_attempts_done': int}}
        poisoned_birds={},
        # Bleeding birds (from Tree Boss red flower)
        # {bird_idx: {'end_time': float}} - press UP = instant death
        bleeding_birds={},
        # Stealth
        stealth_timers={},
        stealth_prev_speeds={},
        # Clockwork
        clockwork_charge={},  # bird_idx -> current charge (0-3)
        clockwork_last_decay={},  # bird_idx -> timestamp of last decay
        # Cookie
        cookie_crumbs_made={},
        # Purple bird charging state
        purple_state=[],
        purple_primed_frame=[],
        purple_charge_started_frame=[],
        purple_saved_vy=[],
        purple_miss_count=[],
        purple_just_fired_frames=[],
        purple_hold_counter=[],
        # Global UP counters
        up_hold_counter=0,
        up_miss_counter=0,
        # Track last UP press time (for Purple hold-to-charge)
        last_up_time=0.0,
        # Rainbow bird state
        rainbow_charge={},  # bird_idx -> charge level (0-100)
        rainbow_last_decay={},  # bird_idx -> timestamp of last decay
        # Twister bird state
        twister_tailwind={},  # bird_idx -> {'end_time': float, 'lanes': [int]}
        # Status effect birds (power boost mode)
        frosty_boosted={},  # bird_idx -> end_time (60% freeze mode)
        poison_boosted={},  # bird_idx -> end_time (60% poison mode)
        berserk_boosted={},  # bird_idx -> end_time (60% bleed mode)
        rock_boosted={},  # bird_idx -> end_time (boosted push mode)
        rock_prev_speeds={},  # bird_idx -> original speed before ROCK boost
        # Enemy debuffs (NEW - applied by birds to enemies)
        frozen_enemies={},  # enemy_id -> {'end_time': float, 'type': 'bat'|'obstacle'}
        poisoned_enemies={},  # enemy_id -> {'end_time': float, 'last_tick': float}
        bleeding_enemies={},  # enemy_id -> {'end_time': float, 'last_tick': float}
    )


# ============================================================================
# ENEMIES STATE (organized as namespace)
# ============================================================================
def _new_enemies():
    return SimpleNamespace(
        obstacles=[],
        obstacle_spawn_timer=0,
        obstacle_id_counter=0,  # Unique ID counter for obstacles
        bats=[],
        bat_spawn_timer=0,
        spawn_queue=[],
        # Mini bats that hide in tier 3+ obstacles
        mini_bats=[],  # Active mini bats on screen
        hidden_mini_bats={},  # Mini bats hidden in obstacles: {obstacle_id: [mini_bat, ...]}
        # Decorative barriers in right panel (no collision)
        right_panel_barriers=[],
        right_panel_barrier_timer=0,
        # Mountain Range cloud banks (foreground fog)
        cloud_banks=[],
        cloud_spawn_timer=0,
        # Boss state (end of biome bosses)
        boss=None,  # None or dict with boss data
        boss_spawned=False,  # True if boss has been spawned this level
        boss_defeated=False,  # True if boss was defeated
        # Cave portals (biome 5) - always spawn in pairs
        # Each portal: {'x_pos': int, 'y_pos': int, 'pair_id': int, 'portal_idx': 0 or 1}
        portals=[],
        portal_spawn_timer=0,
        portal_pair_counter=0,  # Unique ID for portal pairs
    )


# ============================================================================
# ITEMS STATE (organized as namespace)
# ============================================================================
def _new_items():
    return SimpleNamespace(loot_items=[])


# ============================================================================
# SPELL EFFECTS STATE (from spellcaster bats)
# ============================================================================
def _new_spells():
    return SimpleNamespace(
        # Silence spell - lanes where bird powers are disabled
        # {lane_index: {'end_time': float, 'caster_tier': int}}
        silenced_lanes={},
        # Repugnant wind spell - reverse tailwind effect on lanes
        # {lane_index: {'end_time': float, 'speed_boost': int, 'speed_nerf': int}}
        repugnant_wind_lanes={},
        # Exile spell - pending swaps
        # [{'swap_time': float, 'bird_a_idx': int, 'bird_b_idx': int or None}]
        pending_exiles=[],
    )


# ============================================================================
# POWER-UPS STATE (organized as namespace)
# ============================================================================
def _new_powerups():
    return SimpleNamespace(
        wide_cursor_active=False,
        wide_cursor_frames=0,
        wide_cursor_lanes=1,
        tailwind_active=False,
        tailwind_frames=0,
        tailwind_up_bonus=0,
        tailwind_down_penalty=0,
        # Timelapse effect (slows game tick)
        timelapse_active=False,
        timelapse_end_time=0.0,  # Unix timestamp when timelapse ends (real time)
        timelapse_slowdown=1.0,  # Multiplier: 2.0 = game runs at half speed
        # Wind Boss effects
        wind_boss_up_bonus=0,
        wind_boss_down_penalty=0,
    )


# ============================================================================
# GAME STATE (organized as namespace)
# ============================================================================
def _new_game():
    return SimpleNamespace(
        score=0,  # Total score (never decreases)
        momentum=getattr(constants.speed, 'starting_momentum', 100),  # Momentum (from config)
        level=1,  # Level as milestone (1-18, displayed as 1-1 to 6-3)
        level_group=1,  # Group number (1-6)
        level_sub=1,  # Sub-level within group (1-3)
        speed=1,  # Speed level (1-10) - controls game pace
        miles=0.0,  # Miles traveled (accumulated over time based on speed)
        lives=5,
        game_over=False,
        quit_requested=False,  # True quando l'utente esce con Q/CTRL+C
        swaps_used=0,
        paused=False,
        frame_count=0,
        start_time=None,
        clock_offset=0.0,  # wall-clock seconds spent paused (see src/engine/clock.py)
        last_mile_update=None,  # Timestamp for mile calculation
    )


# ============================================================================
# PLAYER STATE (organized as namespace)
# ============================================================================
def _new_player():
    return SimpleNamespace(lane=2, selected_lane=None, last_space_state=False)


# ============================================================================
# UI STATE (organized as namespace)
# ============================================================================
def _new_ui():
    return SimpleNamespace(
        show_xp_overlay=False,
        # Parallax background layers (3 layers with different speeds)
        bg_offset=0,  # Slowest layer (original tree pattern)
        bg_mid_offset=0,  # Middle layer (∧ symbols, intermediate speed)
        # Cave shimmer effect - particles that fade in/out from darkness
        # Dict of {(x, y): brightness} where brightness is 0.0 (dark) to 1.0 (bright)
        cave_shimmer={},
        # Notifications: list of dicts with {title, text, expire_frame}
        # New notifications insert at index 0 (top), old ones at end (bottom)
        notifications=[],
        # Menu navigation: [[screen_id, cursor], ...], root first ('title' or 'pause').
        # See src/engine/menus.py.
        menu_stack=[],
        # Control waiting for a new key on the CONTROLS screen (e.g. 'MOVE_LEFT')
        rebinding_control=None,
        show_title=True,  # True when on title screen
    )


# ============================================================================
# SETTINGS STATE (runtime settings that can be toggled)
# ============================================================================
def _new_settings():
    return SimpleNamespace(
        # Sound settings
        sfx_enabled=True,
        music_enabled=True,
        # Graphics settings
        background_enabled=True,
        parallax_enabled=True,
        accessibility_enabled=False,
        # Difficulty: 0=EASY, 1=NORMAL, 2=HARD, 3=HELL
        difficulty=1,
        # Key bindings (can be remapped)
        key_bindings={
            'MOVE_LEFT': 'LEFT',
            'MOVE_RIGHT': 'RIGHT',
            'BOUNCE': 'UP',
            'SWAP': 'SPACE',
        },
        # Flag to track if settings have been initialized from config
        _initialized=False,
    )


# ============================================================================
# DISCOVERY STATE (tracks what the player has discovered)
# ============================================================================
def _new_discovery():
    return SimpleNamespace(
        # Bird types discovered (set of bird type names)
        birds=set(),
        # Bat types discovered (set of bat type names)
        bats=set(),
        # Obstacle types discovered (set of obstacle type names)
        obstacles=set(),
    )


# ============================================================================
# NAMESPACES
# ============================================================================
birds = _new_birds()
special = _new_special()
enemies = _new_enemies()
items = _new_items()
spells = _new_spells()
powerups = _new_powerups()
game = _new_game()
player = _new_player()
ui = _new_ui()
settings = _new_settings()
discovery = _new_discovery()

# Rebuilt from their defaults at the start of every game
_SESSION_FACTORIES = (
    (birds, _new_birds),
    (special, _new_special),
    (enemies, _new_enemies),
    (items, _new_items),
    (spells, _new_spells),
    (powerups, _new_powerups),
    (game, _new_game),
    (player, _new_player),
)

# UI fields owned by the application rather than by a game: a new game keeps them
_UI_KEPT_ACROSS_GAMES = ('show_title', 'menu_stack')

# Per-bird lists in ``special`` (one slot per bird) and their initial value
_PURPLE_BIRD_LISTS = {
    'purple_state': 0,
    'purple_primed_frame': 0,
    'purple_charge_started_frame': 0,
    'purple_saved_vy': None,
    'purple_miss_count': 0,
    'purple_just_fired_frames': 0,
    'purple_hold_counter': 0,
}


def _reset(namespace, factory, keep=()):
    """Restore a namespace to its defaults in place (references stay valid)."""
    defaults = vars(factory())
    for name in keep:
        defaults.pop(name, None)
    vars(namespace).update(defaults)


def init(seed=None):
    """Start a new game: reset every per-session namespace and deal the flock.

    Args:
        seed: Optional seed for RNG. If None, generates a new one based on current time.
    """
    global game_seed

    # Generate or use provided seed for deterministic gameplay
    if seed is None:
        game_seed = int(time.time() * 1000) % (2**32)
    else:
        game_seed = seed
    random.seed(game_seed)

    for namespace, factory in _SESSION_FACTORIES:
        _reset(namespace, factory)
    _reset(ui, _new_ui, keep=_UI_KEPT_ACROSS_GAMES)
    game.start_time = time.time()

    layout = constants.layout
    num_birds = layout.num_balls
    formation = list(constants.birds.default_formation[:num_birds])
    # Pad with YELLOW if the formation is shorter than the number of birds
    formation += [BirdType.YELLOW] * (num_birds - len(formation))

    birds.colors = [get_color_for_bird_type(bird_type) for bird_type in formation]
    birds.speeds = [int(get_default_speed(bird_type)) for bird_type in formation]

    # Randomize which bird goes to which lane
    birds.random_lanes = list(range(layout.num_lanes))
    if constants.birds.randomize_lanes:
        random.shuffle(birds.random_lanes)
    # Home lanes start same as random_lanes (where bird would go following portals down)
    birds.home_lanes = birds.random_lanes.copy()

    # Positions and velocities: everyone starts on the starting line, rising
    layout.starting_line = layout.height - 4
    birds.cols = [layout.lane_positions[birds.random_lanes[i]] for i in range(num_birds)]
    birds.y = [layout.starting_line] * num_birds
    birds.vy = [-1] * num_birds
    birds.lost = [False] * num_birds
    birds.power_used = [False] * num_birds
    birds.power_uses = [0] * num_birds
    birds.per_bird_xp = [0] * num_birds
    birds.transformed = [False] * num_birds
    birds.pending_transform = [None] * num_birds  # None or target color

    for name, initial in _PURPLE_BIRD_LISTS.items():
        setattr(special, name, [initial] * num_birds)

    # Runtime settings start from the config, once: later changes are the player's
    if not settings._initialized:
        settings.background_enabled = getattr(constants.background, 'enabled', True)
        settings.parallax_enabled = getattr(constants.background, 'parallax', True)
        settings._initialized = True
