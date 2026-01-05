#!/usr/bin/env python3
"""
Save/Load system for BVB game.
Handles serialization of complete game state to JSON files.
"""

import json
import os
import random
import time
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace

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


def list_save_slots():
    """List all available save slots with metadata.

    Returns:
        dict: {slot_number: {exists, timestamp, score, level, ...}}
    """
    slots = {}
    for slot in range(0, MAX_SLOTS + 1):  # 0=autosave, 1-3=manual
        path = get_save_path(slot)
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                slots[slot] = {
                    'exists': True,
                    'path': str(path),
                    **data.get('metadata', {})
                }
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
    from src.core import state

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
    except (OSError, IOError) as e:
        print(f"Save failed: {e}")
        return False


def load_game(slot):
    """Load game state from a save slot.

    Args:
        slot: Save slot number

    Returns:
        bool: True if load succeeded
    """
    from src.core import state

    path = get_save_path(slot)
    if not path.exists():
        return False

    try:
        with open(path, 'r') as f:
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

        # Restore all namespaces
        _restore_birds(state.birds, data.get('birds', {}))
        _restore_special(state.special, data.get('special', {}))
        _restore_enemies(state.enemies, data.get('enemies', {}))
        _restore_items(state.items, data.get('items', {}))
        _restore_powerups(state.powerups, data.get('powerups', {}))
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
        state.player.last_up_state = False

        # Clear UI transient state
        state.ui.notifications = []
        state.ui.settings_menu = None
        state.ui.settings_index = 0
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
    from src.core import state

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
    from src.core import state
    return {
        'score': state.game.score,
        'level': state.game.level,
        'level_group': state.game.level_group,
        'level_sub': state.game.level_sub,
        'speed': state.game.speed,
        'miles': state.game.miles,
        'lives': state.game.lives,
        'swaps_used': state.game.swaps_used,
        'frame_count': state.game.frame_count,
    }


def _build_player_dict():
    """Build player state dict (excluding input state)."""
    from src.core import state
    return {
        'lane': state.player.lane,
        'selected_lane': state.player.selected_lane,
    }


def _build_ui_dict():
    """Build UI state dict (excluding transient notifications)."""
    from src.core import state
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
    for key in ['colors', 'cols', 'y', 'vy', 'speeds', 'lost', 'power_used',
                'power_uses', 'random_lanes', 'per_bird_xp', 'transformed',
                'original_indices']:
        if key in data:
            setattr(birds, key, data[key])


def _restore_special(special, data):
    """Restore special namespace from dict."""
    # Lists
    for key in ['purple_state', 'purple_primed_frame', 'purple_charge_started_frame',
                'purple_saved_vy', 'purple_miss_count', 'purple_just_fired_frames',
                'purple_hold_counter']:
        if key in data:
            setattr(special, key, data[key])

    # Simple values
    for key in ['up_hold_counter', 'up_miss_counter']:
        if key in data:
            setattr(special, key, data[key])

    # Dicts with int keys (convert string keys back to int)
    for key in ['speed_boosts', 'dinosaur_up_presses', 'scared_birds',
                'stunned_birds', 'stealth_timers', 'stealth_prev_speeds',
                'clockwork_charge', 'cookie_crumbs_made']:
        if key in data:
            setattr(special, key, {int(k): v for k, v in data[key].items()})

    # Lists of dicts
    if 'red_projectiles' in data:
        special.red_projectiles = data['red_projectiles']


def _restore_enemies(enemies, data):
    """Restore enemies namespace from dict."""
    enemies.obstacles = data.get('obstacles', [])
    enemies.obstacle_spawn_timer = data.get('obstacle_spawn_timer', 0)
    enemies.bats = data.get('bats', [])
    enemies.bat_spawn_timer = data.get('bat_spawn_timer', 0)
    enemies.spawn_queue = data.get('spawn_queue', [])
    enemies.right_panel_barriers = data.get('right_panel_barriers', [])
    enemies.right_panel_barrier_timer = data.get('right_panel_barrier_timer', 0)

    # Adjust spawn_ts for bats and loot to be relative to current time
    current_time = time.time()
    for bat in enemies.bats:
        if 'spawn_ts' in bat:
            # Keep the relative age of the bat
            bat['spawn_ts'] = current_time


def _restore_items(items, data):
    """Restore items namespace from dict."""
    items.loot_items = data.get('loot_items', [])

    # Adjust spawn_ts to current time
    current_time = time.time()
    for loot in items.loot_items:
        if 'spawn_ts' in loot:
            loot['spawn_ts'] = current_time


def _restore_powerups(powerups, data):
    """Restore powerups namespace from dict."""
    for key in ['wide_cursor_active', 'wide_cursor_frames', 'wide_cursor_lanes',
                'bounce_boost_active', 'bounce_boost_frames', 'bounce_boost_duration',
                'suction_active', 'suction_frames', 'suction_boost_duration',
                'tailwind_active', 'tailwind_frames', 'tailwind_up_bonus',
                'tailwind_down_penalty']:
        if key in data:
            setattr(powerups, key, data[key])


def _restore_game_state(data):
    """Restore game namespace from dict."""
    from src.core import state
    for key in ['score', 'level', 'level_group', 'level_sub', 'speed',
                'miles', 'lives', 'swaps_used', 'frame_count']:
        if key in data:
            setattr(state.game, key, data[key])


def _restore_player_state(data):
    """Restore player namespace from dict."""
    from src.core import state
    state.player.lane = data.get('lane', 4)
    state.player.selected_lane = data.get('selected_lane')


def _restore_ui_state(data):
    """Restore UI namespace from dict."""
    from src.core import state
    state.ui.bg_offset = data.get('bg_offset', 0)
    state.ui.bg_mid_offset = data.get('bg_mid_offset', 0)
    state.ui.show_xp_overlay = data.get('show_xp_overlay', False)
    state.ui.pause_menu_index = 0


def _restore_settings(data):
    """Restore settings namespace from dict."""
    from src.core import state
    for key, value in data.items():
        if hasattr(state.settings, key) and not key.startswith('_'):
            setattr(state.settings, key, value)
