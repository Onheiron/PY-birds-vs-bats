"""Sound effect helpers and dynamic-music sync."""

from src.core import constants
from src.core import state
from src.entities.sprites import BERSERK, BLUE, CLOCKWORK, COOKIE, DINOSAUR, FROSTY, GLITCH, GOLD, ORANGE, PATCHWORK, POISON, PURPLE, RAINBOW, RED, ROCK, STEALTH, TWISTER, WHITE, YELLOW

# Audio module (optional)
try:
    from src.services import audio
    AUDIO_AVAILABLE = audio.is_audio_available()
except ImportError:
    audio = None
    AUDIO_AVAILABLE = False


def play_sfx(name):
    """Play sound effect if audio is available."""
    if AUDIO_AVAILABLE and audio:
        audio.play_sfx(name)

# Mapping from ANSI color codes to bird type names for audio
COLOR_TO_BIRD_TYPE = {
    YELLOW: 'YELLOW',
    RED: 'RED',
    BLUE: 'BLUE',
    PURPLE: 'PURPLE',
    WHITE: 'WHITE',
    ORANGE: 'ORANGE',
    GOLD: 'GOLD',
    PATCHWORK: 'PATCHWORK',
    COOKIE: 'COOKIE',
    CLOCKWORK: 'CLOCKWORK',
    STEALTH: 'STEALTH',
    DINOSAUR: 'DINOSAUR',
    GLITCH: 'GLITCH',
    RAINBOW: 'RAINBOW',
    TWISTER: 'TWISTER',
    FROSTY: 'FROSTY',
    POISON: 'POISON',
    BERSERK: 'BERSERK',
    ROCK: 'ROCK',
}

_last_bird_sync_frame = 0

_last_bird_set = None


def sync_active_birds_audio(force=False):
    """Sync the active bird types with the audio system for dynamic music."""
    global _last_bird_sync_frame, _last_bird_set

    if not AUDIO_AVAILABLE or not audio:
        return

    # Only sync periodically to avoid blocking
    # Unless force=True (used at game start)
    audio_sync_interval = getattr(constants.timing, 'audio_sync_interval', 60)
    if not force and state.game.frame_count - _last_bird_sync_frame < audio_sync_interval:
        return
    _last_bird_sync_frame = state.game.frame_count

    active_types = set()
    for i in range(len(state.birds.colors)):
        if not state.birds.lost[i]:
            color = state.birds.colors[i]
            bird_type = COLOR_TO_BIRD_TYPE.get(color)
            if bird_type:
                active_types.add(bird_type)

    # Only update if birds actually changed (or force)
    if force or active_types != _last_bird_set:
        _last_bird_set = active_types
        audio.update_active_birds(active_types)
