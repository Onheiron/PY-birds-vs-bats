#!/usr/bin/env python3
"""
8-bit Chiptune Audio Engine for BVB.
Generates NES/Game Boy style sounds programmatically.
"""

import numpy as np
import threading
import time
from collections import deque

try:
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

# Audio settings
SAMPLE_RATE = 22050  # Lower sample rate for authentic 8-bit feel
MASTER_VOLUME = 0.3  # Global volume (0.0 - 1.0)
SFX_COOLDOWN = 0.05  # Minimum seconds between same sound effect

# Audio state
_audio_enabled = True
_music_thread = None
_music_playing = False
_current_music = None

# Sound mixing state
_sfx_queue = deque(maxlen=4)  # Limit concurrent sounds
_sfx_lock = threading.Lock()
_sfx_last_played = {}  # Track when each SFX was last played
_mixer_stream = None
_mixer_thread = None
_mixer_running = False
_active_sounds = []  # List of (wave, position) tuples
_sounds_lock = threading.Lock()


# =============================================================================
# WAVEFORM GENERATORS (NES-style)
# =============================================================================

def square_wave(freq, duration, duty_cycle=0.5, volume=0.5):
    """Generate square wave (NES Pulse channel style)."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = np.where((t * freq) % 1 < duty_cycle, 1, -1)
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def triangle_wave(freq, duration, volume=0.5):
    """Generate triangle wave (NES Triangle channel style)."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = 2 * np.abs(2 * (t * freq % 1) - 1) - 1
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def noise(duration, volume=0.3):
    """Generate noise (NES Noise channel style)."""
    samples = int(SAMPLE_RATE * duration)
    # Quantize to 4-bit for authentic sound
    wave = np.random.randint(-8, 8, samples) / 8.0
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def sawtooth_wave(freq, duration, volume=0.5):
    """Generate sawtooth wave."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = 2 * (t * freq % 1) - 1
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def sine_wave(freq, duration, volume=0.5):
    """Generate sine wave (for smoother sounds)."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = np.sin(2 * np.pi * freq * t)
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


# =============================================================================
# ENVELOPE GENERATORS
# =============================================================================

def apply_envelope(wave, attack=0.01, decay=0.1, sustain=0.7, release=0.1):
    """Apply ADSR envelope to a wave."""
    length = len(wave)
    envelope = np.ones(length)

    attack_samples = int(attack * SAMPLE_RATE)
    decay_samples = int(decay * SAMPLE_RATE)
    release_samples = int(release * SAMPLE_RATE)
    sustain_samples = length - attack_samples - decay_samples - release_samples

    if sustain_samples < 0:
        sustain_samples = 0

    idx = 0
    # Attack
    if attack_samples > 0:
        envelope[idx:idx + attack_samples] = np.linspace(0, 1, attack_samples)
        idx += attack_samples
    # Decay
    if decay_samples > 0 and idx < length:
        end = min(idx + decay_samples, length)
        envelope[idx:end] = np.linspace(1, sustain, end - idx)
        idx = end
    # Sustain
    if sustain_samples > 0 and idx < length:
        end = min(idx + sustain_samples, length)
        envelope[idx:end] = sustain
        idx = end
    # Release
    if release_samples > 0 and idx < length:
        envelope[idx:] = np.linspace(sustain, 0, length - idx)

    return wave * envelope


def apply_fade_out(wave, fade_duration=0.05):
    """Apply quick fade out to avoid clicks."""
    fade_samples = int(fade_duration * SAMPLE_RATE)
    if fade_samples > len(wave):
        fade_samples = len(wave)
    wave[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    return wave


# =============================================================================
# SOUND EFFECTS
# =============================================================================

def sfx_bounce():
    """Bird bounce sound - quick ascending blip."""
    wave = square_wave(440, 0.05, duty_cycle=0.25, volume=0.4)
    wave = np.concatenate([wave, square_wave(880, 0.03, duty_cycle=0.25, volume=0.3)])
    return apply_fade_out(wave)


def sfx_hit():
    """Hit obstacle/bat sound - harsh noise burst."""
    wave = noise(0.08, volume=0.5)
    wave = np.concatenate([square_wave(150, 0.02, volume=0.4), wave])
    return apply_envelope(wave, attack=0.001, decay=0.05, sustain=0.3, release=0.02)


def sfx_destroy():
    """Destroy obstacle/bat sound - descending explosion."""
    wave = noise(0.15, volume=0.4)
    for i, freq in enumerate([200, 150, 100, 75]):
        wave = np.concatenate([wave, square_wave(freq, 0.04, volume=0.3 - i * 0.05)])
    return apply_envelope(wave, attack=0.001, decay=0.1, sustain=0.2, release=0.05)


def sfx_powerup():
    """Power-up collect sound - ascending arpeggio."""
    notes = [523, 659, 784, 1047]  # C5, E5, G5, C6
    wave = np.array([], dtype=np.float32)
    for note in notes:
        wave = np.concatenate([wave, square_wave(note, 0.08, duty_cycle=0.5, volume=0.4)])
    return apply_fade_out(wave)


def sfx_egg():
    """Egg collect sound - soft pleasant tone."""
    wave = triangle_wave(880, 0.1, volume=0.5)
    wave = np.concatenate([wave, triangle_wave(1100, 0.1, volume=0.4)])
    return apply_envelope(wave, attack=0.01, decay=0.1, sustain=0.5, release=0.1)


def sfx_level_up():
    """Level up sound - triumphant fanfare."""
    notes = [(523, 0.15), (659, 0.15), (784, 0.15), (1047, 0.3)]  # C E G C
    wave = np.array([], dtype=np.float32)
    for freq, dur in notes:
        w = square_wave(freq, dur, duty_cycle=0.5, volume=0.4)
        w = apply_envelope(w, attack=0.01, decay=0.05, sustain=0.8, release=0.05)
        wave = np.concatenate([wave, w])
    return wave


def sfx_game_over():
    """Game over sound - sad descending tones."""
    notes = [(392, 0.3), (349, 0.3), (330, 0.3), (262, 0.5)]  # G F E C
    wave = np.array([], dtype=np.float32)
    for freq, dur in notes:
        w = triangle_wave(freq, dur, volume=0.5)
        w = apply_envelope(w, attack=0.02, decay=0.1, sustain=0.6, release=0.1)
        wave = np.concatenate([wave, w])
    return wave


def sfx_bird_lost():
    """Bird lost sound - quick descending blip."""
    wave = square_wave(400, 0.05, volume=0.3)
    wave = np.concatenate([wave, square_wave(200, 0.08, volume=0.25)])
    wave = np.concatenate([wave, square_wave(100, 0.1, volume=0.2)])
    return apply_fade_out(wave)


# =============================================================================
# BACKGROUND MUSIC
# =============================================================================

def generate_bass_line(pattern, note_duration=0.25, volume=0.35):
    """Generate a bass line from note pattern."""
    wave = np.array([], dtype=np.float32)
    for note in pattern:
        if note == 0:
            # Rest
            wave = np.concatenate([wave, np.zeros(int(SAMPLE_RATE * note_duration), dtype=np.float32)])
        else:
            w = triangle_wave(note, note_duration, volume=volume)
            w = apply_envelope(w, attack=0.01, decay=0.05, sustain=0.7, release=0.05)
            wave = np.concatenate([wave, w])
    return wave


def generate_melody(pattern, note_duration=0.25, volume=0.3):
    """Generate melody from note pattern."""
    wave = np.array([], dtype=np.float32)
    for note in pattern:
        if note == 0:
            wave = np.concatenate([wave, np.zeros(int(SAMPLE_RATE * note_duration), dtype=np.float32)])
        else:
            w = square_wave(note, note_duration, duty_cycle=0.25, volume=volume)
            w = apply_envelope(w, attack=0.01, decay=0.1, sustain=0.5, release=0.05)
            wave = np.concatenate([wave, w])
    return wave


def generate_drums(pattern, note_duration=0.25, volume=0.25):
    """Generate drum pattern."""
    wave = np.array([], dtype=np.float32)
    for hit in pattern:
        if hit == 0:
            wave = np.concatenate([wave, np.zeros(int(SAMPLE_RATE * note_duration), dtype=np.float32)])
        elif hit == 1:  # Kick
            w = triangle_wave(80, note_duration * 0.3, volume=volume)
            w = apply_envelope(w, attack=0.001, decay=0.1, sustain=0.2, release=0.05)
            padding = np.zeros(int(SAMPLE_RATE * note_duration) - len(w), dtype=np.float32)
            wave = np.concatenate([wave, w, padding])
        elif hit == 2:  # Snare/noise
            w = noise(note_duration * 0.2, volume=volume * 0.7)
            padding = np.zeros(int(SAMPLE_RATE * note_duration) - len(w), dtype=np.float32)
            wave = np.concatenate([wave, w, padding])
        elif hit == 3:  # Hi-hat
            w = noise(note_duration * 0.1, volume=volume * 0.4)
            padding = np.zeros(int(SAMPLE_RATE * note_duration) - len(w), dtype=np.float32)
            wave = np.concatenate([wave, w, padding])
    return wave


def create_game_music():
    """Create the main game loop music (8-bit chiptune style)."""
    # Note frequencies (A minor pentatonic inspired)
    # A3=220, C4=262, D4=294, E4=330, G4=392, A4=440, C5=523, D5=587, E5=659

    # Bass line (4 bars, 16 notes) - simple driving bass
    bass_notes = [
        110, 110, 0, 110,  # Am
        147, 147, 0, 147,  # Dm
        131, 131, 0, 131,  # C
        165, 165, 0, 165,  # E
    ]

    # Melody (catchy and simple)
    melody_notes = [
        440, 0, 523, 440,
        392, 0, 330, 0,
        440, 523, 587, 523,
        440, 0, 0, 0,
    ]

    # Drums (kick=1, snare=2, hihat=3)
    drum_pattern = [
        1, 3, 2, 3,
        1, 3, 2, 3,
        1, 3, 2, 3,
        1, 2, 1, 2,
    ]

    note_dur = 0.18  # Tempo

    bass = generate_bass_line(bass_notes, note_dur, volume=0.3)
    melody = generate_melody(melody_notes, note_dur, volume=0.25)
    drums = generate_drums(drum_pattern, note_dur, volume=0.2)

    # Mix all tracks (ensure same length)
    min_len = min(len(bass), len(melody), len(drums))
    mixed = bass[:min_len] + melody[:min_len] + drums[:min_len]

    # Normalize
    max_val = np.max(np.abs(mixed))
    if max_val > 0:
        mixed = mixed / max_val * 0.8

    return mixed.astype(np.float32)


# =============================================================================
# SOUND EFFECT CACHE
# =============================================================================

_sfx_cache = {}

def _get_cached_sfx(name):
    """Get or generate cached sound effect."""
    if name not in _sfx_cache:
        sfx_map = {
            'bounce': sfx_bounce,
            'hit': sfx_hit,
            'destroy': sfx_destroy,
            'powerup': sfx_powerup,
            'egg': sfx_egg,
            'level_up': sfx_level_up,
            'game_over': sfx_game_over,
            'bird_lost': sfx_bird_lost,
        }
        if name in sfx_map:
            _sfx_cache[name] = sfx_map[name]()
    return _sfx_cache.get(name)


# =============================================================================
# AUDIO MIXER (Single Stream)
# =============================================================================

def _audio_callback(outdata, frames, time_info, status):
    """Audio callback for the output stream - mixes all active sounds."""
    global _active_sounds, _current_music

    output = np.zeros(frames, dtype=np.float32)

    # Mix music
    if _music_playing and _current_music is not None:
        music_pos = getattr(_audio_callback, 'music_pos', 0)
        music_len = len(_current_music)

        for i in range(frames):
            output[i] += _current_music[music_pos % music_len] * 0.6
            music_pos += 1

        _audio_callback.music_pos = music_pos % music_len

    # Mix active sound effects
    with _sounds_lock:
        still_active = []
        for wave, pos in _active_sounds:
            remaining = len(wave) - pos
            if remaining > 0:
                samples_to_copy = min(frames, remaining)
                output[:samples_to_copy] += wave[pos:pos + samples_to_copy]
                new_pos = pos + frames
                if new_pos < len(wave):
                    still_active.append((wave, new_pos))
        _active_sounds[:] = still_active

    # Clip to prevent distortion
    np.clip(output, -1.0, 1.0, out=output)
    outdata[:, 0] = output


def _start_mixer():
    """Start the audio mixer stream."""
    global _mixer_stream, _mixer_running

    if not AUDIO_AVAILABLE or _mixer_running:
        return

    try:
        _mixer_stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            callback=_audio_callback,
            blocksize=1024,
            dtype=np.float32
        )
        _mixer_stream.start()
        _mixer_running = True
        _audio_callback.music_pos = 0
    except Exception:
        _mixer_running = False


def _stop_mixer():
    """Stop the audio mixer stream."""
    global _mixer_stream, _mixer_running

    _mixer_running = False
    if _mixer_stream is not None:
        try:
            _mixer_stream.stop()
            _mixer_stream.close()
        except Exception:
            pass
        _mixer_stream = None


# =============================================================================
# PLAYBACK FUNCTIONS
# =============================================================================

def play_sound(wave):
    """Play a sound effect through the mixer."""
    if not AUDIO_AVAILABLE or not _audio_enabled or not _mixer_running:
        return

    with _sounds_lock:
        # Limit concurrent sounds
        if len(_active_sounds) < 4:
            _active_sounds.append((wave.copy(), 0))


def play_sfx(name):
    """Play a named sound effect with rate limiting."""
    if not AUDIO_AVAILABLE or not _audio_enabled:
        return

    # Rate limiting - don't spam the same sound
    current_time = time.time()
    with _sfx_lock:
        last_time = _sfx_last_played.get(name, 0)
        if current_time - last_time < SFX_COOLDOWN:
            return
        _sfx_last_played[name] = current_time

    wave = _get_cached_sfx(name)
    if wave is not None:
        play_sound(wave)


def _music_loop():
    """Background music loop thread (legacy - now handled by mixer)."""
    pass  # Music is now mixed in _audio_callback


def start_music():
    """Start background music loop."""
    global _music_playing, _current_music

    if not AUDIO_AVAILABLE or not _audio_enabled:
        return

    # Pre-generate music
    if _current_music is None:
        _current_music = create_game_music()

    # Start the mixer if not running
    if not _mixer_running:
        _start_mixer()

    _music_playing = True


def stop_music():
    """Stop background music."""
    global _music_playing
    _music_playing = False


def set_audio_enabled(enabled):
    """Enable or disable all audio."""
    global _audio_enabled
    _audio_enabled = enabled
    if not enabled:
        stop_music()
        _stop_mixer()


def is_audio_available():
    """Check if audio is available."""
    return AUDIO_AVAILABLE


def cleanup():
    """Cleanup audio resources."""
    global _active_sounds

    stop_music()

    with _sounds_lock:
        _active_sounds.clear()

    _stop_mixer()
