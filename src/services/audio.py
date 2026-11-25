"""Audio engine: sound effects (src/services/synth.py) and music (src/services/music/) through SDL.

Built on pygame-ce's mixer, i.e. SDL audio: CoreAudio on macOS, PipeWire /
PulseAudio / ALSA on Linux and the Steam Deck, WASAPI on Windows. Nothing to
install besides pygame-ce and numpy (both optional: without them the game is
silent, see src/services/sound.py).

- Sound effects play on their own channels, each one at most every
  SFX_COOLDOWN seconds, a few at a time.
- The music (src/services/music/: the world's theme and drums, a part per
  bird type by how many there are, the bats, at the gear's speed, played with
  real instrument samples) loops on one of two channels. When what plays
  changes, the new loop is made in a background thread and cross-faded in on
  the other channel, so there is never a gap or a click. The new loop starts
  where the old one was (the same bar and beat), so the music goes on.
- When a boss arrives, its loop is preceded by the corruption of the world's
  music (src/services/music/boss.py); as it loses health the world's melody
  comes back over it.
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
    _missing = None
except ImportError as error:
    _IMPORTED = False
    _missing = getattr(error, 'name', None) or str(error)

SFX_COOLDOWN = 0.05  # seconds between two plays of the same effect
SFX_CHANNELS = 6  # effects heard at once
MUSIC_VOLUME = 0.5
SFX_VOLUME = 1.0
CROSSFADE_MS = 600

_ready = None  # None: not tried yet; True / False once the mixer was opened (or failed)
_why = None  # why there is no audio (shown to the player)
_enabled = True
_lock = threading.Lock()
_sfx_sounds = {}
_sfx_last = {}
_music = {
    'playing': False,
    'biome': 1,
    'birds': {},  # bird type -> how many
    'bats': 0,
    'gear': 1,
    'boss': None,  # the boss type fought, or None
    'health': 0,  # its health step (boss.health_step)
    'bridge_until': 0.0,  # the corruption plays until then: the boss's loop waits for it
    'loop_start': 0.0,  # when the loop playing now was at its start (monotonic seconds)
    'loop_len': 0.0,  # its length in seconds (0: none)
    'playing_now': None,  # what the loop on the channel plays (see _signature)
    'paused': False,  # the game is paused: the music holds where it is
    'screen': None,  # 'title' or 'game_over' while a screen's music plays instead of the game's
    'channel': 0,  # which of the two music channels plays now
    'version': 0,  # bumped by every change: an older background render is dropped
}


def _open():
    """Open the audio device once; False if there is none."""
    global _ready
    if _ready is not None:
        return _ready
    global _why
    _ready = False
    if not _IMPORTED:
        package = 'pygame-ce' if _missing == 'pygame' else _missing
        _why = f'{package} missing: pip install -r requirements.txt'
        return False
    try:
        pygame.mixer.pre_init(synth.SAMPLE_RATE, -16, 2, 512)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(2 + SFX_CHANNELS)
        pygame.mixer.set_reserved(2)  # channels 0 and 1: the music
        _ready = True
        _prepare_sfx()
    except Exception as error:
        _why = f'no audio device ({error})'
        _ready = False
    return _ready


def unavailable_reason():
    """Why there is no audio, or None."""
    return None if _open() else _why


def _sound(wave):
    """A pygame Sound from a float wave (mono, or stereo (n, 2)), in the mixer's format."""
    pcm = (np.clip(wave, -1.0, 1.0) * 32767).astype(np.int16)
    _frequency, _size, channels = pygame.mixer.get_init()
    if pcm.ndim == 1 and channels > 1:
        pcm = np.repeat(pcm[:, None], channels, axis=1)
    elif pcm.ndim == 2 and channels == 1:
        pcm = pcm.mean(axis=1).astype(np.int16)
    return pygame.mixer.Sound(buffer=np.ascontiguousarray(pcm).tobytes())


# --------------------------------------------------------------------------- effects


def _make_sfx(name):
    """The Sound of an effect: played with the instruments (music/effects.py), or synthesized
    (synth.py) when there is no sample bank. None for an unknown or silent one."""
    from src.services.music import effects, sampler

    try:
        wave = effects.render(name) if sampler.available() else synth.sfx_wave(name)
    except Exception:
        wave = None
    if wave is None:
        return None
    sound = _sfx_sounds[name] = _sound(wave)
    sound.set_volume(SFX_VOLUME)
    return sound


def _prepare_sfx():
    """Make every effect in the background once the mixer is open: the first play has no delay."""
    from src.services.music import effects

    def work():
        for name in effects.EFFECTS:
            if name not in _sfx_sounds:
                _make_sfx(name)

    threading.Thread(target=work, daemon=True).start()


def play_sfx(name):
    """Play a named effect (bounce, hit, destroy, powerup, egg, level_up, ...)."""
    if not _enabled or not _open():
        return
    now = time.monotonic()
    if now - _sfx_last.get(name, 0.0) < SFX_COOLDOWN:
        return
    _sfx_last[name] = now
    sound = _sfx_sounds.get(name) or _make_sfx(name)
    if sound is None:
        return
    channel = pygame.mixer.find_channel()  # None when every effect channel is busy
    if channel is not None:
        channel.play(sound)


# --------------------------------------------------------------------------- music


def _signature():
    """What the music plays, in steps: a change below a step changes nothing."""
    from src.services.music import arrangement

    birds = tuple(sorted((k, arrangement.quantity_step(n)) for k, n in _music['birds'].items() if n > 0))
    return (
        _music['biome'],
        birds,
        arrangement.quantity_step(_music['bats'], 'BATS'),
        arrangement.speed_step(_music['gear']),
        _music['boss'],
        _music['health'] if _music['boss'] else 0,
    )


def _render_and_play(version, fade=True):
    """Make the music loop for the current state and cross-fade it in (any thread).
    A boss that has just arrived first corrupts the world's music (a bridge, played once)."""
    from src.services.music import arrangement, sampler

    if not sampler.available():
        return
    with _lock:
        biome, birds, bats, gear = _music['biome'], dict(_music['birds']), _music['bats'], _music['gear']
        boss, health = _music['boss'], _music['health']
        signature = _signature()
        before = _music['playing_now']
    arriving = boss is not None and before is not None and before[4] is None
    try:
        bridge = arrangement.bridge(biome, birds, bats, gear, boss) if arriving else None
        wave = arrangement.loop(biome, birds, bats, gear, boss=boss, health=health)
    except Exception:
        return
    if bridge is not None:
        with _lock:
            if version != _music['version'] or not _music['playing']:
                return
            _swap_in(_sound(bridge), loops=0, fade=True)
            _music['loop_len'] = 0.0
            _music['bridge_until'] = time.monotonic() + len(bridge) / synth.SAMPLE_RATE - CROSSFADE_MS / 1000
            _music['playing_now'] = signature
    wait = _music['bridge_until'] - time.monotonic()
    if wait > 0:
        time.sleep(wait)  # the corruption plays to its end (a newer render waits the same)
    with _lock:
        if version != _music['version'] or not _music['playing']:
            return  # something changed meanwhile, or the music was stopped
        same_piece = before is not None and before[0] == signature[0] and before[4] == signature[4]
        if bridge is None and same_piece and _music['loop_len'] > 0:
            wave = _from_where_it_was(wave)
        else:
            _music['loop_start'] = time.monotonic()
        _music['loop_len'] = len(wave) / synth.SAMPLE_RATE
        _swap_in(_sound(wave), loops=-1, fade=fade)
        _music['playing_now'] = signature  # once it plays (readers may not hold the lock)


def _from_where_it_was(wave):
    """``wave`` turned so that it starts at the bar and beat the playing loop is at (lock held)."""
    played = (time.monotonic() - _music['loop_start']) % _music['loop_len']
    fraction = played / _music['loop_len']
    cut = int(fraction * len(wave)) % len(wave)
    _music['loop_start'] = time.monotonic() - fraction * len(wave) / synth.SAMPLE_RATE
    return np.concatenate([wave[cut:], wave[:cut]])


def _swap_in(sound, loops, fade):
    """Play ``sound`` on the other music channel, cross-faded with the one playing (lock held)."""
    old = pygame.mixer.Channel(_music['channel'])
    _music['channel'] = 1 - _music['channel']
    new = pygame.mixer.Channel(_music['channel'])
    sound.set_volume(MUSIC_VOLUME)
    if fade and old.get_busy() and not _music['paused']:
        old.fadeout(CROSSFADE_MS)
        new.play(sound, loops=loops, fade_ms=CROSSFADE_MS)
    else:
        old.stop()
        new.play(sound, loops=loops)
    if _music['paused']:
        new.pause()  # ready for when the game resumes


def _changed():
    """The music must follow a change: render the new loop in the background."""
    with _lock:
        if _signature() == _music['playing_now']:
            _music['version'] += 1  # back to what already plays: drop any render on its way
            return
        _music['version'] += 1
        version = _music['version']
        playing = _music['playing']
    if playing and _ready:
        threading.Thread(target=_render_and_play, args=(version,), daemon=True).start()


def start_music():
    """Start the music for the current state (it comes in as soon as its loop is ready)."""
    if not _enabled or not _open():
        return
    with _lock:
        fade = _music['screen'] is not None  # from the title's music into the game's
        _music['screen'] = None
        _music['playing'] = True
        _music['playing_now'] = None
        _music['bridge_until'] = 0.0
        _music['loop_len'] = 0.0
        _music['version'] += 1
        version = _music['version']
    threading.Thread(target=_render_and_play, args=(version, fade), daemon=True).start()


GAME_OVER_DELAY = 2.6  # seconds: the sad trombone first


def play_screen(name):
    """The music of a screen: 'title' (a loop), or 'game_over' (a phrase, then a loop)."""
    if not _enabled or not _open():
        return
    from src.services.music import sampler

    if not sampler.available():
        return
    with _lock:
        if _music['screen'] == name:
            return
        _music['screen'] = name
        _music['playing'] = False  # the game's music gives way
        _music['playing_now'] = None
        _release_pause()  # left the game while paused: the screen's music must be heard
        _music['version'] += 1
        version = _music['version']
    threading.Thread(target=_screen_music, args=(name, version), daemon=True).start()


def _screen_music(name, version):
    from src.services.music import screens

    def still():
        return version == _music['version']

    try:
        if name == 'title':
            sound = _sound(screens.render('title'))
            with _lock:
                if still():
                    _swap_in(sound, loops=-1, fade=True)
            return
        phrase = _sound(screens.render('game_over_phrase'))
        with _lock:
            if still():
                for index in (0, 1):
                    pygame.mixer.Channel(index).fadeout(400)
        time.sleep(GAME_OVER_DELAY)
        with _lock:
            if not still():
                return
            _swap_in(phrase, loops=0, fade=False)
        calm = _sound(screens.render('game_over_loop'))
        time.sleep(max(0.0, phrase.get_length() - 1.0))
        with _lock:
            if still():
                _swap_in(calm, loops=-1, fade=True)
    except Exception:
        return


def stop_music():
    with _lock:
        _music['playing'] = False
        _music['playing_now'] = None
        _music['screen'] = None
        _music['version'] += 1
        _release_pause()
    if _ready:
        for index in (0, 1):
            pygame.mixer.Channel(index).fadeout(300)


def _release_pause():
    """The music channels are no longer held by a pause (lock held). A paused channel would keep
    the next music silent, and the game no longer says when it resumes once it is left."""
    if _music['paused'] and _ready:
        for index in (0, 1):
            pygame.mixer.Channel(index).unpause()
    _music['paused'] = False


def pause_music(paused):
    """Hold the music while the game is paused, and go on from there when it resumes.
    Only the game's music: a screen's music (title, game over) is never held."""
    with _lock:
        if _music['paused'] == paused or (paused and _music['screen'] is not None):
            return
        _music['paused'] = paused
        if paused:
            _music['paused_at'] = time.monotonic()
        else:  # the loop and the corruption were held: they are that much later
            held = time.monotonic() - _music.get('paused_at', time.monotonic())
            _music['loop_start'] += held
            if _music['bridge_until']:
                _music['bridge_until'] += held
        if not _ready:
            return
        for index in (0, 1):
            channel = pygame.mixer.Channel(index)
            if paused:
                channel.pause()
            else:
                channel.unpause()


def update_music_for_biome(biome):
    _music['biome'] = biome
    _changed()


def update_active_birds(birds):
    """``birds``: bird type -> how many (a set or list counts one of each)."""
    _music['birds'] = dict(birds) if isinstance(birds, dict) else dict.fromkeys(birds, 1)
    _changed()


def update_bats(count):
    _music['bats'] = count
    _changed()


def update_boss(boss_type, health=0):
    """The boss fought now (None when there is none) and its health step 0-3."""
    if (_music['boss'], _music['health']) == (boss_type, health if boss_type else 0):
        return
    _music['boss'] = boss_type
    _music['health'] = health if boss_type else 0
    if boss_type is None:
        _music['bridge_until'] = 0.0
    _changed()


def update_tempo_for_gear(gear):
    """The gear sets the speed step of the music: gears 1-3, 4-6, 7-10."""
    _music['gear'] = gear
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
