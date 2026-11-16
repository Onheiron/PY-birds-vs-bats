"""Sound facade: every call is a safe no-op when the audio backend is missing.

The real backend (src.services.audio) needs numpy and sounddevice, which are
optional. Game code talks to this module only, so it never has to check
whether audio is available.
"""

from src.core import constants, state
from src.entities.bird_types import get_bird_type_by_color

try:
    from src.services import audio as _backend

    if not _backend.is_audio_available():
        _backend = None
except ImportError:
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

    active_types = set()
    for color, lost in zip(state.birds.colors, state.birds.lost):
        if not lost:
            bird_type = get_bird_type_by_color(color)
            if bird_type:
                active_types.add(bird_type)

    # Only update if birds actually changed (or force)
    if force or active_types != _last_bird_set:
        _last_bird_set = active_types
        _backend.update_active_birds(active_types)
