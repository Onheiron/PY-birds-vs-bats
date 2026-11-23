"""
Save/Load system for BVB game.
Handles serialization of complete game state to JSON files.
"""

import json
import random
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from src.core import state
from src.engine import clock

# Constants
SAVE_VERSION = "2.0"
MAX_SLOTS = 3
SAVE_DIR_NAME = ".bvb"
SAVES_SUBDIR = "saves"


def get_save_directory():
    """Get the save directory, creating it if needed."""
    home = Path.home()
    save_dir = home / SAVE_DIR_NAME / SAVES_SUBDIR

    try:
        save_dir.mkdir(parents=True, exist_ok=True)
        return save_dir
    except (OSError, PermissionError):
        # Fallback to project directory
        fallback = Path.cwd() / "saves"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def get_save_path(slot):
    """Get the full path for a save slot."""
    if slot == 0:
        filename = "autosave.json"
    else:
        filename = f"slot_{slot}.json"
    return get_save_directory() / filename


def get_default_settings_path():
    """Get the path for default settings file."""
    home = Path.home()
    settings_dir = home / SAVE_DIR_NAME
    try:
        settings_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError):
        settings_dir = Path.cwd()
    return settings_dir / "settings.json"


def get_discovery_path():
    """Get the path for discovery data file."""
    home = Path.home()
    discovery_dir = home / SAVE_DIR_NAME
    try:
        discovery_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError):
        discovery_dir = Path.cwd()
    return discovery_dir / "discovery.json"


def get_profile_path():
    """The meta-progression profile: gold, upgrades, global achievements."""
    home = Path.home()
    profile_dir = home / SAVE_DIR_NAME
    try:
        profile_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError):
        profile_dir = Path.cwd()
    return profile_dir / "profile.json"


def save_profile(profile):
    try:
        with open(get_profile_path(), 'w') as f:
            json.dump(profile, f, indent=2)
        return True
    except OSError:
        return False


def load_profile():
    """The saved profile, or a new one."""
    from src.engine.meta import new_profile

    path = get_profile_path()
    profile = new_profile()
    if path.exists():
        try:
            with open(path) as f:
                profile.update(json.load(f))
        except (OSError, ValueError):
            pass
    return profile


def save_discovery():
    """Save discovery data (persists across all saves)."""

    discovery_data = {
        'version': SAVE_VERSION,
        'birds': list(state.discovery.birds),
        'bats': list(state.discovery.bats),
        'obstacles': list(state.discovery.obstacles),
    }

    path = get_discovery_path()
    try:
        with open(path, 'w') as f:
            json.dump(discovery_data, f, indent=2)
        return True
    except OSError:
        return False


def load_discovery():
    """Load discovery data and apply to state.discovery."""

    path = get_discovery_path()
    if not path.exists():
        return False

    try:
        with open(path) as f:
            data = json.load(f)

        # Apply discovery data
        if 'birds' in data:
            state.discovery.birds = set(data['birds'])
        if 'bats' in data:
            state.discovery.bats = set(data['bats'])
        if 'obstacles' in data:
            state.discovery.obstacles = set(data['obstacles'])

        return True
    except (json.JSONDecodeError, OSError):
        return False


def discover_bird(bird_type_name):
    """Mark a bird type as discovered."""

    if bird_type_name not in state.discovery.birds:
        state.discovery.birds.add(bird_type_name)
        save_discovery()
        return True
    return False


def discover_bat(bat_type_name):
    """Mark a bat type as discovered."""

    if bat_type_name not in state.discovery.bats:
        state.discovery.bats.add(bat_type_name)
        save_discovery()
        return True
    return False


def discover_obstacle(obstacle_type_name):
    """Mark an obstacle type as discovered."""

    if obstacle_type_name not in state.discovery.obstacles:
        state.discovery.obstacles.add(obstacle_type_name)
        save_discovery()
        return True
    return False


def save_default_settings():
    """Save current settings as defaults for new games."""

    settings_data = {
        'version': SAVE_VERSION,
        'sfx_enabled': state.settings.sfx_enabled,
        'music_enabled': state.settings.music_enabled,
        'background_enabled': state.settings.background_enabled,
        'parallax_enabled': state.settings.parallax_enabled,
        'accessibility_enabled': state.settings.accessibility_enabled,
        'bounce_on_enter': state.settings.bounce_on_enter,
        'trigger_on_enter': state.settings.trigger_on_enter,
        'difficulty': state.settings.difficulty,
        'key_bindings': state.settings.key_bindings,
    }

    path = get_default_settings_path()
    try:
        with open(path, 'w') as f:
            json.dump(settings_data, f, indent=2)
        return True
    except OSError:
        return False


def load_default_settings():
    """Load default settings and apply to state.settings."""

    path = get_default_settings_path()
    if not path.exists():
        return False

    try:
        with open(path) as f:
            data = json.load(f)

        # Apply settings
        if 'sfx_enabled' in data:
            state.settings.sfx_enabled = data['sfx_enabled']
        if 'music_enabled' in data:
            state.settings.music_enabled = data['music_enabled']
        if 'background_enabled' in data:
            state.settings.background_enabled = data['background_enabled']
        if 'parallax_enabled' in data:
            state.settings.parallax_enabled = data['parallax_enabled']
        if 'accessibility_enabled' in data:
            state.settings.accessibility_enabled = data['accessibility_enabled']
        for assist in ('bounce_on_enter', 'trigger_on_enter'):
            if assist in data:
                setattr(state.settings, assist, bool(data[assist]))
        if 'difficulty' in data:
            state.settings.difficulty = data['difficulty']
        if 'key_bindings' in data:
            state.settings.key_bindings = data['key_bindings']

        return True
    except (json.JSONDecodeError, OSError):
        return False


def list_save_slots():
    """List all available save slots with metadata.

    Returns:
        dict: {slot_number: {exists, timestamp, score, level, ...}}
    """
    slots = {}
    for slot in range(MAX_SLOTS + 1):  # 0=autosave, 1-3=manual
        path = get_save_path(slot)
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                slots[slot] = {'exists': True, 'path': str(path), **data.get('metadata', {})}
            except (json.JSONDecodeError, KeyError):
                slots[slot] = {'exists': False, 'corrupted': True}
        else:
            slots[slot] = {'exists': False}
    return slots


def get_most_recent_save():
    """Find the most recent save slot by timestamp.

    Returns:
        int or None: Slot number of most recent save, or None if no saves exist
    """
    slots = list_save_slots()
    most_recent_slot = None
    most_recent_time = None

    for slot, info in slots.items():
        if info.get('exists') and 'timestamp' in info:
            try:
                ts = datetime.fromisoformat(info['timestamp'])
                if most_recent_time is None or ts > most_recent_time:
                    most_recent_time = ts
                    most_recent_slot = slot
            except (ValueError, TypeError):
                continue

    return most_recent_slot


def format_timestamp_display(iso_timestamp):
    """Format an ISO timestamp for display in menus.

    Args:
        iso_timestamp: ISO format timestamp string

    Returns:
        str: Formatted like "Jan 5, 14:30"
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%b %d, %H:%M")
    except (ValueError, TypeError):
        return "???"


def save_game(slot=0):
    """Save the current game state to a slot.

    Args:
        slot: Save slot number (0=autosave, 1-3=manual)

    Returns:
        bool: True if save succeeded
    """

    # Build save data
    save_data = {
        'version': SAVE_VERSION,
        'timestamp': datetime.now().isoformat(),
        'metadata': _build_metadata(),
        'random_state': random.getstate(),
        'game_seed': getattr(state, 'game_seed', None),
        'birds': _namespace_to_dict(state.birds),
        'special': _special_to_dict(state.special),
        'enemies': _enemies_to_dict(state.enemies),
        'items': _namespace_to_dict(state.items),
        'powerups': _namespace_to_dict(state.powerups),
        'stat_modifiers': list(state.stats.modifiers),
        'enemy_layers': list(state.stats.enemy_layers),
        'pacts': list(state.stats.pacts),
        'choice': {
            'active': state.choice.active,
            'queue': list(state.choice.queue),
            'rerolls': state.choice.rerolls,
            'skips': state.choice.skips,
        },
        'game': _build_game_dict(),
        'player': _build_player_dict(),
        'ui': _build_ui_dict(),
        'settings': _settings_to_dict(state.settings),
    }

    # Write to file
    path = get_save_path(slot)
    try:
        with open(path, 'w') as f:
            json.dump(save_data, f, indent=2, default=_json_serializer)
        return True
    except OSError as e:
        print(f"Save failed: {e}")
        return False


def load_game(slot):
    """Load game state from a save slot.

    Args:
        slot: Save slot number

    Returns:
        bool: True if load succeeded
    """

    path = get_save_path(slot)
    if not path.exists():
        return False

    try:
        with open(path) as f:
            data = json.load(f)

        # Verify version compatibility
        version = data.get('version', '1.0')
        if not _is_version_compatible(version):
            return False

        # Restore random state first
        if 'random_state' in data:
            random.setstate(_deserialize_random_state(data['random_state']))

        # Restore game seed
        if 'game_seed' in data:
            state.game_seed = data['game_seed']

        # Game clock first: every saved timer is expressed in game time.
        # Saves made before the game clock existed hold wall-clock times.
        game_time = data.get('game', {}).get('game_time')
        if game_time is None:
            state.game.clock_offset = 0.0
        else:
            clock.resume_at(game_time)

        # Restore all namespaces
        _restore_birds(state.birds, data.get('birds', {}))
        _restore_special(state.special, data.get('special', {}))
        _restore_enemies(state.enemies, data.get('enemies', {}), keep_ages=game_time is not None)
        _restore_items(state.items, data.get('items', {}), keep_ages=game_time is not None)
        _restore_powerups(state.powerups, data.get('powerups', {}))
        state.stats.modifiers[:] = [
            {**m, 'target': m['target'] if m['target'] == 'flock' else int(m['target'])}
            for m in data.get('stat_modifiers', [])
        ]
        state.stats.version += 1
        state.stats.enemy_layers[:] = data.get('enemy_layers', [])
        state.stats.pacts[:] = data.get('pacts', [])
        saved_choice = data.get('choice') or {}
        state.choice.active = saved_choice.get('active')
        state.choice.queue[:] = saved_choice.get('queue', [])
        state.choice.rerolls = saved_choice.get('rerolls')
        state.choice.skips = saved_choice.get('skips')
        _restore_game_state(data.get('game', {}))
        _restore_player_state(data.get('player', {}))
        _restore_ui_state(data.get('ui', {}))
        _restore_settings(data.get('settings', {}))

        # Reset transient state
        state.game.paused = False
        state.game.game_over = False
        state.game.quit_requested = False
        state.game.start_time = time.time()
        state.game.last_mile_update = time.time()
        state.player.last_space_state = False

        # Clear UI transient state
        state.ui.notifications = []
        state.ui.rebinding_control = None

        return True

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Load failed: {e}")
        return False


def delete_save(slot):
    """Delete a save file."""
    path = get_save_path(slot)
    if path.exists():
        path.unlink()
        return True
    return False


# ============================================================================
# SERIALIZATION HELPERS
# ============================================================================


def _namespace_to_dict(ns):
    """Convert a SimpleNamespace to a dict, handling nested structures."""
    result = {}
    for key, value in vars(ns).items():
        if key.startswith('_'):
            continue
        if isinstance(value, SimpleNamespace):
            result[key] = _namespace_to_dict(value)
        else:
            result[key] = value
    return result


def _special_to_dict(special):
    """Convert special namespace, handling dict keys that are integers."""
    result = {}
    for key, value in vars(special).items():
        if key.startswith('_'):
            continue
        if isinstance(value, dict):
            # Convert int keys to strings for JSON
            result[key] = {str(k): v for k, v in value.items()}
        elif isinstance(value, list):
            result[key] = value
        else:
            result[key] = value
    return result


def _enemies_to_dict(enemies):
    """Convert enemies namespace."""
    return {
        'obstacles': list(enemies.obstacles),
        'obstacle_spawn_timer': enemies.obstacle_spawn_timer,
        'bats': list(enemies.bats),
        'bat_spawn_timer': enemies.bat_spawn_timer,
        'spawn_queue': list(enemies.spawn_queue),
        'right_panel_barriers': list(enemies.right_panel_barriers),
        'right_panel_barrier_timer': enemies.right_panel_barrier_timer,
    }


def _settings_to_dict(settings):
    """Convert settings namespace."""
    result = {}
    for key, value in vars(settings).items():
        if key.startswith('_'):
            continue
        result[key] = value
    return result


def _build_metadata():
    """Build save metadata for display in load menu."""

    level_display = f"{state.game.level_group}-{state.game.level_sub}"

    return {
        'score': int(state.game.score),
        'level': state.game.level,
        'level_display': level_display,
        'miles': round(state.game.miles, 1),
        'lives': state.game.lives,
        'timestamp': datetime.now().isoformat(),
    }


def _build_game_dict():
    """Build game state dict (excluding transient fields)."""

    return {
        'score': state.game.score,
        'momentum': state.game.momentum,
        'level': state.game.level,
        'level_group': state.game.level_group,
        'level_sub': state.game.level_sub,
        'speed': state.game.speed,
        'miles': state.game.miles,
        'lives': state.game.lives,
        'swaps_used': state.game.swaps_used,
        'frame_count': state.game.frame_count,
        'meta_applied': getattr(state.game, 'meta_applied', False),
        'game_time': clock.now(),
    }


def _build_player_dict():
    """Build player state dict (excluding input state)."""

    return {
        'lane': state.player.lane,
        'selected_lane': state.player.selected_lane,
    }


def _build_ui_dict():
    """Build UI state dict (excluding transient notifications)."""

    return {
        'bg_offset': state.ui.bg_offset,
        'bg_mid_offset': state.ui.bg_mid_offset,
        'show_xp_overlay': state.ui.show_xp_overlay,
    }


def _json_serializer(obj):
    """Custom JSON serializer for special types."""
    if isinstance(obj, SimpleNamespace):
        return _namespace_to_dict(obj)
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _deserialize_random_state(state_data):
    """Convert JSON-serialized random state back to proper format."""
    # random.getstate() returns (version, state_tuple, gauss_next)
    # The state tuple needs to be converted back from list
    if isinstance(state_data, list) and len(state_data) == 3:
        return (state_data[0], tuple(state_data[1]), state_data[2])
    return state_data


def _is_version_compatible(version):
    """Check if save version is compatible with current game."""
    return version.startswith('2.')


# ============================================================================
# RESTORATION HELPERS
# ============================================================================


def _restore_birds(birds, data):
    """Restore birds namespace from dict."""
    for key in [
        'colors',
        'cols',
        'y',
        'vy',
        'speeds',
        'lost',
        'power_used',
        'power_uses',
        'random_lanes',
        'per_bird_xp',
        'transformed',
    ]:
        if key in data:
            setattr(birds, key, data[key])


def _restore_special(special, data):
    """Restore special namespace from dict."""
    # Lists
    for key in [
        'purple_state',
        'purple_primed_frame',
        'purple_charge_started_frame',
        'purple_saved_vy',
        'purple_miss_count',
        'purple_just_fired_frames',
        'purple_hold_counter',
    ]:
        if key in data:
            setattr(special, key, data[key])

    # Simple values
    for key in ['up_hold_counter', 'up_miss_counter']:
        if key in data:
            setattr(special, key, data[key])

    # Dicts with int keys (convert string keys back to int)
    for key in [
        'speed_boosts',
        'scared_push',
        'zombies',
        'dinosaur_up_presses',
        'scared_birds',
        'stunned_birds',
        'stealth_timers',
        'stealth_prev_speeds',
        'clockwork_charge',
        'cookie_crumbs_made',
    ]:
        if key in data:
            setattr(special, key, {int(k): v for k, v in data[key].items()})

    # Lists of dicts
    if 'red_projectiles' in data:
        special.red_projectiles = data['red_projectiles']


def _restore_enemies(enemies, data, keep_ages=False):
    """Restore enemies namespace from dict."""
    enemies.obstacles = data.get('obstacles', [])
    enemies.obstacle_spawn_timer = data.get('obstacle_spawn_timer', 0)
    enemies.bats = data.get('bats', [])
    enemies.bat_spawn_timer = data.get('bat_spawn_timer', 0)
    enemies.spawn_queue = data.get('spawn_queue', [])
    enemies.right_panel_barriers = data.get('right_panel_barriers', [])
    enemies.right_panel_barrier_timer = data.get('right_panel_barrier_timer', 0)

    if keep_ages:
        return
    # Old saves: wall-clock spawn times are meaningless now, restart their age
    current_time = clock.now()
    for bat in enemies.bats:
        if 'spawn_ts' in bat:
            # Keep the relative age of the bat
            bat['spawn_ts'] = current_time


def _restore_items(items, data, keep_ages=False):
    """Restore items namespace from dict."""
    items.loot_items = data.get('loot_items', [])

    if keep_ages:
        return
    # Old saves: wall-clock spawn times are meaningless now, restart their age
    current_time = clock.now()
    for loot in items.loot_items:
        if 'spawn_ts' in loot:
            loot['spawn_ts'] = current_time


def _restore_powerups(powerups, data):
    """Restore powerups namespace from dict."""
    for key in [
        'wide_cursor_active',
        'wide_cursor_until',
        'wide_cursor_lanes',
        'tailwind_active',
        'tailwind_until',
        'tailwind_up_bonus',
        'tailwind_down_penalty',
    ]:
        if key in data:
            setattr(powerups, key, data[key])


def _restore_game_state(data):
    """Restore game namespace from dict."""

    for key in [
        'score',
        'momentum',
        'level',
        'level_group',
        'level_sub',
        'speed',
        'miles',
        'lives',
        'swaps_used',
        'frame_count',
        'meta_applied',
    ]:
        if key in data:
            setattr(state.game, key, data[key])
    if 'meta_applied' not in data:
        # Saves from before the meta progression: do not stack upgrades on them
        state.game.meta_applied = True
    # For old saves without momentum, initialize it to score value
    if 'momentum' not in data and 'score' in data:
        state.game.momentum = data['score']


def _restore_player_state(data):
    """Restore player namespace from dict."""

    state.player.lane = data.get('lane', 4)
    state.player.selected_lane = data.get('selected_lane')


def _restore_ui_state(data):
    """Restore UI namespace from dict."""

    state.ui.bg_offset = data.get('bg_offset', 0)
    state.ui.bg_mid_offset = data.get('bg_mid_offset', 0)
    state.ui.show_xp_overlay = data.get('show_xp_overlay', False)


def _restore_settings(data):
    """Restore settings namespace from dict."""

    for key, value in data.items():
        if hasattr(state.settings, key) and not key.startswith('_'):
            setattr(state.settings, key, value)
