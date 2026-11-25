"""Sound facade: every call is a safe no-op when the audio backend is missing.

The real backend (src.services.audio) needs numpy and pygame-ce (SDL audio),
which are optional. Game code talks to this module only, so it never has to check
whether audio is available.
"""

from src.core import constants, state
from src.entities.bird_types import get_bird_type_by_color

try:
    from src.services import audio as _backend

    if not _backend.is_audio_available():
        _backend = None
except (ImportError, OSError):
    _backend = None

_last_bird_sync_frame = 0
_last_bird_set = None


def get_audio():
    """Return the audio backend module, or None when audio is unavailable."""
    return _backend


def play_sfx(name):
    """Play a sound effect if audio is available and SFX is enabled."""
    if _backend is not None and state.settings.sfx_enabled:
        _backend.play_sfx(name)


def apply_music_setting():
    """Start or stop the music according to the music setting."""
    if _backend is None:
        return
    if state.settings.music_enabled:
        _backend.start_music()
    else:
        _backend.stop_music()


def start_session_music():
    """Restart the music for a new session, in sync with biome, gear and flock."""
    if _backend is None:
        return
    _backend.stop_music()
    if state.settings.music_enabled:
        _backend.update_music_for_biome(state.game.level_group)
        # Higher gear = faster tempo
        _backend.update_tempo_for_gear(state.game.speed)
        # Sync the flock before starting so the first bars already match it
        sync_active_birds(force=True)
        _backend.start_music()


def stop_music():
    """Stop the music (the mixer keeps running for sound effects)."""
    if _backend is not None:
        _backend.stop_music()


def cleanup():
    """Shut the audio backend down."""
    if _backend is not None:
        _backend.cleanup()


def sync_active_birds(force=False):
    """Tell the dynamic music which bird types are alive.

    Runs at most once every ``timing.audio_sync_interval`` game frames unless
    ``force`` is set (used at game start).
    """
    global _last_bird_sync_frame, _last_bird_set

    if _backend is None:
        return

    audio_sync_interval = getattr(constants.timing, 'audio_sync_interval', 60)
    if not force and state.game.frame_count - _last_bird_sync_frame < audio_sync_interval:
        return
    _last_bird_sync_frame = state.game.frame_count

    # How many birds of each type, and the bats on screen: the music follows both
    counts = {}
    for color, lost in zip(state.birds.colors, state.birds.lost):
        if not lost:
            bird_type = get_bird_type_by_color(color)
            if bird_type:
                counts[bird_type] = counts.get(bird_type, 0) + 1
    bats = len(state.enemies.bats) + len(state.enemies.mini_bats)

    # Only update if something changed (or force)
    if force or (counts, bats) != _last_bird_set:
        _last_bird_set = (counts, bats)
        _backend.update_active_birds(counts)
        _backend.update_bats(bats)


# =============================================================================
# EVENT SUBSCRIPTIONS
# =============================================================================

_SOUND_FOR_EVENT = {
    'bat_killed': 'bat_death',
    'mini_bat_killed': 'bat_death',
    'bird_lost': 'bird_lost',
    'level_up': 'level_up',
}


def _sound_for(event):
    name = _SOUND_FOR_EVENT[event]
    return lambda **_fields: play_sfx(name)


def _on_loot_collected(loot, bird):
    play_sfx('egg' if '_egg' in loot['type'] else 'powerup')


def subscribe():
    """Play sound effects for game events."""
    from src.engine import events

    for event in _SOUND_FOR_EVENT:
        events.on(event, _sound_for(event))
    events.on('loot_collected', _on_loot_collected)
