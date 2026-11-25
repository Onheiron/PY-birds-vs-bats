"""Audio engine: plays the synthesized sounds (src/services/synth.py) through SDL.

Built on pygame-ce's mixer, i.e. SDL audio: CoreAudio on macOS, PipeWire /
PulseAudio / ALSA on Linux and the Steam Deck, WASAPI on Windows. Nothing to
install besides pygame-ce and numpy (both optional: without them the game is
silent, see src/services/sound.py).

- Sound effects play on their own channels, each one at most every
  SFX_COOLDOWN seconds, a few at a time.
- The music loops on one of two channels. When it changes (biome, flock,
  gear) the new loop is made in a background thread and cross-faded in on
  the other channel, so there is never a gap or a click.
"""

import os
import threading
import time

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

try:
    import numpy as np
    import pygame

    from src.services import synth

    _IMPORTED = True
except ImportError:
    _IMPORTED = False

SFX_COOLDOWN = 0.05  # seconds between two plays of the same effect
SFX_CHANNELS = 6  # effects heard at once
MUSIC_VOLUME = 0.5
SFX_VOLUME = 1.0
CROSSFADE_MS = 600

_ready = None  # None: not tried yet; True / False once the mixer was opened (or failed)
_enabled = True
_lock = threading.Lock()
_sfx_sounds = {}
_sfx_last = {}
_music = {
    'playing': False,
    'biome': 1,
    'birds': frozenset(),
    'speed': 1.0,
    'channel': 0,  # which of the two music channels plays now
    'version': 0,  # bumped by every change: an older background render is dropped
}


def _open():
    """Open the audio device once; False if there is none."""
    global _ready
    if _ready is not None:
        return _ready
    _ready = False
    if not _IMPORTED:
        return False
    try:
        pygame.mixer.pre_init(synth.SAMPLE_RATE, -16, 2, 512)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(2 + SFX_CHANNELS)
        pygame.mixer.set_reserved(2)  # channels 0 and 1: the music
        _ready = True
    except Exception:
        _ready = False
    return _ready


def _sound(wave):
    """A pygame Sound from a mono float wave, in the mixer's format (16-bit stereo)."""
    pcm = (np.clip(wave, -1.0, 1.0) * 32767).astype(np.int16)
    _frequency, _size, channels = pygame.mixer.get_init()
    if channels > 1:
        pcm = np.repeat(pcm[:, None], channels, axis=1)
    return pygame.mixer.Sound(buffer=np.ascontiguousarray(pcm).tobytes())


# --------------------------------------------------------------------------- effects


def play_sfx(name):
    """Play a named effect (bounce, hit, destroy, powerup, egg, level_up, ...)."""
    if not _enabled or not _open():
        return
    now = time.monotonic()
    if now - _sfx_last.get(name, 0.0) < SFX_COOLDOWN:
        return
    _sfx_last[name] = now
    sound = _sfx_sounds.get(name)
    if sound is None:
        wave = synth.sfx_wave(name)
        if wave is None:
            return
        sound = _sfx_sounds[name] = _sound(wave)
        sound.set_volume(SFX_VOLUME)
    channel = pygame.mixer.find_channel()  # None when every effect channel is busy
    if channel is not None:
        channel.play(sound)


# --------------------------------------------------------------------------- music


def _render_and_play(version, fade=True):
    """Make the music loop for the current state and cross-fade it in (any thread)."""
    with _lock:
        biome, birds, speed = _music['biome'], set(_music['birds']), _music['speed']
    try:
        sound = _sound(synth.create_game_music(biome, birds, speed))
    except Exception:
        return
    with _lock:
        if version != _music['version'] or not _music['playing']:
            return  # something changed meanwhile, or the music was stopped
        old = pygame.mixer.Channel(_music['channel'])
        _music['channel'] = 1 - _music['channel']
        new = pygame.mixer.Channel(_music['channel'])
        sound.set_volume(MUSIC_VOLUME)
        if fade and old.get_busy():
            old.fadeout(CROSSFADE_MS)
            new.play(sound, loops=-1, fade_ms=CROSSFADE_MS)
        else:
            old.stop()
            new.play(sound, loops=-1)


def _changed():
    """The music must follow a change: render the new loop in the background."""
    with _lock:
        _music['version'] += 1
        version = _music['version']
        playing = _music['playing']
    if playing and _ready:
        threading.Thread(target=_render_and_play, args=(version,), daemon=True).start()


def start_music():
    if not _enabled or not _open():
        return
    with _lock:
        _music['playing'] = True
        _music['version'] += 1
        version = _music['version']
    _render_and_play(version, fade=False)  # the first loop at once


def stop_music():
    with _lock:
        _music['playing'] = False
        _music['version'] += 1
    if _ready:
        for index in (0, 1):
            pygame.mixer.Channel(index).fadeout(300)


def update_music_for_biome(biome):
    if _music['biome'] != biome:
        _music['biome'] = biome
        _changed()


def update_active_birds(bird_types):
    birds = frozenset(bird_types)
    if _music['birds'] != birds:
        _music['birds'] = birds
        _changed()


def update_tempo_for_gear(gear):
    """Gear 1-10 plays the music 1.0x-1.6x as fast."""
    speed = 1.0 + (max(1, min(10, gear)) - 1) / 9.0 * 0.6
    if abs(speed - _music['speed']) > 0.02:
        _music['speed'] = speed
        _changed()


# --------------------------------------------------------------------------- the rest


def set_audio_enabled(enabled):
    global _enabled
    _enabled = enabled
    if not enabled:
        stop_music()
        if _ready:
            pygame.mixer.stop()


def is_enabled():
    return _enabled


def is_audio_available():
    return _open()


def cleanup():
    global _ready
    stop_music()
    if _ready:
        pygame.mixer.quit()
    _ready = None
