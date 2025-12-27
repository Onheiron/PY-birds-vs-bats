#!/usr/bin/env python3
"""
8-bit Chiptune Audio Engine for BVB.
Dynamic music system where each bird type plays a different instrument.
6 unique themes for different level ranges with distinct musical modes.
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
MUSIC_VOLUME = 0.5   # Music volume relative to master

# Audio state
_audio_enabled = True
_music_playing = False
_current_level = 1
_current_theme = None
_theme_cache = {}

# Sound mixing state
_sfx_lock = threading.Lock()
_sfx_last_played = {}
_mixer_stream = None
_mixer_running = False
_active_sounds = []
_sounds_lock = threading.Lock()

# Dynamic music state - which instruments are active
_active_birds = set()  # Set of bird type names currently in flock
_birds_lock = threading.Lock()


# =============================================================================
# MUSICAL CONSTANTS
# =============================================================================

# Note frequencies (Hz)
NOTES = {
    'C2': 65.41, 'D2': 73.42, 'E2': 82.41, 'F2': 87.31, 'G2': 98.00, 'A2': 110.00, 'B2': 123.47,
    'C3': 130.81, 'D3': 146.83, 'E3': 164.81, 'F3': 174.61, 'G3': 196.00, 'A3': 220.00, 'B3': 246.94,
    'C4': 261.63, 'D4': 293.66, 'E4': 329.63, 'F4': 349.23, 'G4': 392.00, 'A4': 440.00, 'B4': 493.88,
    'C5': 523.25, 'D5': 587.33, 'E5': 659.25, 'F5': 698.46, 'G5': 783.99, 'A5': 880.00, 'B5': 987.77,
    'C6': 1046.50, 'D6': 1174.66, 'E6': 1318.51,
    # Sharps/Flats
    'Db2': 69.30, 'Eb2': 77.78, 'Gb2': 92.50, 'Ab2': 103.83, 'Bb2': 116.54,
    'Db3': 138.59, 'Eb3': 155.56, 'Gb3': 185.00, 'Ab3': 207.65, 'Bb3': 233.08,
    'Db4': 277.18, 'Eb4': 311.13, 'Gb4': 369.99, 'Ab4': 415.30, 'Bb4': 466.16,
    'Db5': 554.37, 'Eb5': 622.25, 'Gb5': 739.99, 'Ab5': 830.61, 'Bb5': 932.33,
    'Db6': 1108.73, 'Eb6': 1244.51,
    # Alternate notation
    'C#2': 69.30, 'D#2': 77.78, 'F#2': 92.50, 'G#2': 103.83, 'A#2': 116.54,
    'C#3': 138.59, 'D#3': 155.56, 'F#3': 185.00, 'G#3': 207.65, 'A#3': 233.08,
    'C#4': 277.18, 'D#4': 311.13, 'F#4': 369.99, 'G#4': 415.30, 'A#4': 466.16,
    'C#5': 554.37, 'D#5': 622.25, 'F#5': 739.99, 'G#5': 830.61, 'A#5': 932.33,
}

def n(note):
    """Get frequency for note name, 0 for rest."""
    if note == 0 or note == '-':
        return 0
    return NOTES.get(note, 0)


# =============================================================================
# WAVEFORM GENERATORS (NES-style instruments)
# =============================================================================

def square_wave(freq, duration, duty_cycle=0.5, volume=0.5):
    """Generate square wave (NES Pulse channel style) - YELLOW bird."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = np.where((t * freq) % 1 < duty_cycle, 1, -1)
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def triangle_wave(freq, duration, volume=0.5):
    """Generate triangle wave (NES Triangle channel) - BLUE bird."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = 2 * np.abs(2 * (t * freq % 1) - 1) - 1
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def sawtooth_wave(freq, duration, volume=0.5):
    """Generate sawtooth wave - RED bird (aggressive)."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = 2 * (t * freq % 1) - 1
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def sine_wave(freq, duration, volume=0.5):
    """Generate sine wave (smooth) - for bells and pads."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = np.sin(2 * np.pi * freq * t)
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def noise(duration, volume=0.3):
    """Generate noise (NES Noise channel) - drums."""
    samples = int(SAMPLE_RATE * duration)
    wave = np.random.randint(-8, 8, samples) / 8.0
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def pwm_wave(freq, duration, mod_freq=5, volume=0.5):
    """Pulse Width Modulation wave - PURPLE bird."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    duty = 0.25 + 0.25 * np.sin(2 * np.pi * mod_freq * t)  # Duty cycles from 0.0 to 0.5
    wave = np.where((t * freq) % 1 < duty, 1, -1)
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def bell_wave(freq, duration, volume=0.5):
    """Bell/metallic sound - WHITE bird (Templar)."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    # Bell = fundamental + inharmonic partials
    wave = (np.sin(2 * np.pi * freq * t) * 0.5 +
            np.sin(2 * np.pi * freq * 2.4 * t) * 0.3 +
            np.sin(2 * np.pi * freq * 5.95 * t) * 0.2)
    # Fast decay
    decay = np.exp(-t * 8)
    return (wave * decay * volume * MASTER_VOLUME).astype(np.float32)


def glockenspiel_wave(freq, duration, volume=0.5):
    """Sparkly glockenspiel - GOLD bird."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = (np.sin(2 * np.pi * freq * t) * 0.6 +
            np.sin(2 * np.pi * freq * 3 * t) * 0.3 +
            np.sin(2 * np.pi * freq * 5 * t) * 0.1)
    decay = np.exp(-t * 6)
    return (wave * decay * volume * MASTER_VOLUME).astype(np.float32)


def pluck_wave(freq, duration, volume=0.5):
    """Plucked string sound - COOKIE bird."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    # Karplus-Strong-ish pluck
    wave = (np.sin(2 * np.pi * freq * t) +
            0.5 * np.sin(2 * np.pi * freq * 2 * t) +
            0.25 * np.sin(2 * np.pi * freq * 3 * t))
    decay = np.exp(-t * 10)
    return (wave * decay * volume * MASTER_VOLUME).astype(np.float32)


def tick_wave(freq, duration, volume=0.5):
    """Mechanical tick sound - CLOCKWORK bird."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, samples, False)
    # Short click + resonance
    click = np.zeros(samples, dtype=np.float32)
    click_len = min(int(SAMPLE_RATE * 0.01), samples)
    click[:click_len] = 1.0
    resonance = np.sin(2 * np.pi * freq * t) * np.exp(-t * 30)
    wave = click * 0.3 + resonance * 0.7
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def distorted_wave(freq, duration, volume=0.5):
    """Distorted lead - ORANGE/PHOENIX bird."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = np.sin(2 * np.pi * freq * t)
    # Hard clipping distortion
    wave = np.clip(wave * 3, -1, 1)
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def pad_wave(freq, duration, volume=0.5):
    """Soft pad with fade - STEALTH bird."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = (np.sin(2 * np.pi * freq * t) * 0.5 +
            np.sin(2 * np.pi * freq * 0.5 * t) * 0.3 +
            np.sin(2 * np.pi * freq * 1.5 * t) * 0.2)
    # Slow attack and release
    envelope = np.sin(np.pi * t / duration) ** 0.5
    return (wave * envelope * volume * MASTER_VOLUME).astype(np.float32)


def bass_wave(freq, duration, volume=0.6):
    """Deep bass - DINOSAUR bird."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    # Sub bass with harmonics
    wave = (np.sin(2 * np.pi * freq * t) * 0.6 +
            np.sin(2 * np.pi * freq * 2 * t) * 0.3 +
            np.sin(2 * np.pi * freq * 0.5 * t) * 0.4)  # Sub-octave
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def glitch_wave(freq, duration, volume=0.5):
    """Chaotic glitch sounds - GLITCH bird."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, samples, False)
    # Random frequency modulation
    freq_mod = freq * (1 + 0.5 * np.random.random(samples))
    phase = np.cumsum(freq_mod) / SAMPLE_RATE
    wave = np.sin(2 * np.pi * phase)
    # Random bit crushing
    wave = np.round(wave * 4) / 4
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def arpeggio_wave(freqs, duration, volume=0.5):
    """Quick arpeggio through notes - PATCHWORK bird."""
    samples = int(SAMPLE_RATE * duration)
    wave = np.zeros(samples, dtype=np.float32)
    notes_per_arp = len(freqs)
    samples_per_note = samples // notes_per_arp

    for i, freq in enumerate(freqs):
        if freq > 0:
            start = i * samples_per_note
            end = start + samples_per_note
            t = np.linspace(0, samples_per_note / SAMPLE_RATE, samples_per_note, False)
            wave[start:end] = np.sin(2 * np.pi * freq * t) * np.exp(-t * 8)

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
    if attack_samples > 0:
        envelope[idx:idx + attack_samples] = np.linspace(0, 1, attack_samples)
        idx += attack_samples
    if decay_samples > 0 and idx < length:
        end = min(idx + decay_samples, length)
        envelope[idx:end] = np.linspace(1, sustain, end - idx)
        idx = end
    if sustain_samples > 0 and idx < length:
        end = min(idx + sustain_samples, length)
        envelope[idx:end] = sustain
        idx = end
    if release_samples > 0 and idx < length:
        envelope[idx:] = np.linspace(sustain, 0, length - idx)

    return wave * envelope


def apply_fade_out(wave, fade_duration=0.05):
    """Apply quick fade out to avoid clicks."""
    fade_samples = int(fade_duration * SAMPLE_RATE)
    if fade_samples > len(wave):
        fade_samples = len(wave)
    if fade_samples > 0:
        wave[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    return wave


# =============================================================================
# BIRD TYPE TO INSTRUMENT MAPPING
# =============================================================================

# Map bird types to their instrument generators and musical role
BIRD_INSTRUMENTS = {
    'YELLOW': {'gen': square_wave, 'role': 'lead', 'duty': 0.25},
    'RED': {'gen': sawtooth_wave, 'role': 'harmony'},
    'BLUE': {'gen': triangle_wave, 'role': 'melody'},
    'PATCHWORK': {'gen': 'arpeggio', 'role': 'arpeggio'},
    'PURPLE': {'gen': pwm_wave, 'role': 'pad'},
    'CLOCKWORK': {'gen': tick_wave, 'role': 'percussion'},
    'WHITE': {'gen': bell_wave, 'role': 'accent'},
    'ORANGE': {'gen': distorted_wave, 'role': 'lead2'},
    'GOLD': {'gen': glockenspiel_wave, 'role': 'sparkle'},
    'COOKIE': {'gen': pluck_wave, 'role': 'pluck'},
    'STEALTH': {'gen': pad_wave, 'role': 'atmosphere'},
    'DINOSAUR': {'gen': bass_wave, 'role': 'bass'},
    'GLITCH': {'gen': glitch_wave, 'role': 'chaos'},
}


# =============================================================================
# MUSICAL SCALES AND MODES
# =============================================================================

def get_scale_notes(root, mode, octave=4):
    """Get notes for a scale in the given mode."""
    # Semitone intervals for each mode
    MODE_INTERVALS = {
        'major': [0, 2, 4, 5, 7, 9, 11],          # Ionian (C major)
        'ionian': [0, 2, 4, 5, 7, 9, 11],
        'dorian': [0, 2, 3, 5, 7, 9, 10],          # Minor with raised 6th
        'phrygian': [0, 1, 3, 5, 7, 8, 10],        # Minor with flat 2nd - Spanish feel
        'lydian': [0, 2, 4, 6, 7, 9, 11],          # Major with raised 4th - dreamy
        'mixolydian': [0, 2, 4, 5, 7, 9, 10],      # Major with flat 7th
        'minor': [0, 2, 3, 5, 7, 8, 10],           # Aeolian (natural minor)
        'aeolian': [0, 2, 3, 5, 7, 8, 10],
        'locrian': [0, 1, 3, 5, 6, 8, 10],         # Diminished - dark, unstable
        'ionian_sharp5': [0, 2, 4, 5, 8, 9, 11],   # Augmented - eerie
    }

    # Root note frequencies
    ROOT_FREQS = {
        'C': 261.63, 'C#': 277.18, 'Db': 277.18,
        'D': 293.66, 'D#': 311.13, 'Eb': 311.13,
        'E': 329.63,
        'F': 349.23, 'F#': 369.99, 'Gb': 369.99,
        'G': 392.00, 'G#': 415.30, 'Ab': 415.30,
        'A': 440.00, 'A#': 466.16, 'Bb': 466.16,
        'B': 493.88,
    }

    root_freq = ROOT_FREQS.get(root, 261.63)
    # Adjust for octave (base is octave 4)
    root_freq *= 2 ** (octave - 4)

    intervals = MODE_INTERVALS.get(mode, MODE_INTERVALS['major'])

    # Generate 2 octaves of the scale
    notes = []
    for oct_offset in range(2):
        for interval in intervals:
            freq = root_freq * (2 ** oct_offset) * (2 ** (interval / 12))
            notes.append(freq)

    return notes


# =============================================================================
# THEME DEFINITIONS - 6 MUSICAL THEMES
# =============================================================================

def create_theme_1():
    """
    Theme 1: Soaring The Woods (Levels 1-5)
    Key: C Major (Ionian)
    Mood: Bright, hopeful, adventurous
    """
    scale = get_scale_notes('C', 'major', 4)
    bass_scale = get_scale_notes('C', 'major', 2)

    # BPM ~120, note = 0.125s (eighth note)
    note_dur = 0.125

    # Structure: Intro (memorable hook) -> Development -> Chorus (hook repeated)

    # === INTRO MOTIF (memorable hook) ===
    # C E G E | C E G C5 | (ascending hopeful)
    intro_melody = [scale[0], scale[2], scale[4], scale[2],
                    scale[0], scale[2], scale[4], scale[7],
                    scale[0], scale[2], scale[4], scale[2],
                    scale[4], scale[7], scale[4], scale[2]]

    intro_bass = [bass_scale[0], 0, bass_scale[4], 0,
                  bass_scale[2], 0, bass_scale[4], 0,
                  bass_scale[0], 0, bass_scale[4], 0,
                  bass_scale[5], 0, bass_scale[4], 0]

    # === DEVELOPMENT (scales wandering) ===
    dev_melody = [scale[4], scale[5], scale[6], scale[7],
                  scale[6], scale[5], scale[4], scale[2],
                  scale[2], scale[3], scale[4], scale[5],
                  scale[4], scale[2], scale[0], 0]

    dev_bass = [bass_scale[3], 0, bass_scale[5], 0,
                bass_scale[4], 0, bass_scale[2], 0,
                bass_scale[5], 0, bass_scale[4], 0,
                bass_scale[0], 0, 0, 0]

    # === CHORUS (hook emphasized and repeated) ===
    chorus_melody = [scale[0], scale[2], scale[4], scale[2],
                     scale[4], scale[7], scale[4], scale[7],
                     scale[0], scale[2], scale[4], scale[2],
                     scale[4], scale[7], scale[9], scale[7]]

    chorus_bass = [bass_scale[0], bass_scale[0], bass_scale[4], 0,
                   bass_scale[2], bass_scale[2], bass_scale[4], 0,
                   bass_scale[0], bass_scale[0], bass_scale[4], 0,
                   bass_scale[5], bass_scale[4], bass_scale[2], bass_scale[0]]

    # Drums: kick=1, snare=2, hihat=3
    intro_drums = [1, 3, 2, 3, 1, 3, 2, 3, 1, 3, 2, 3, 1, 3, 2, 3]
    dev_drums = [1, 3, 3, 3, 1, 3, 2, 3, 1, 3, 3, 3, 1, 2, 1, 2]
    chorus_drums = [1, 3, 2, 3, 1, 3, 2, 3, 1, 3, 2, 3, 1, 1, 2, 2]

    return {
        'name': 'Soaring The Woods',
        'tempo': note_dur,
        'sections': [
            {'melody': intro_melody, 'bass': intro_bass, 'drums': intro_drums, 'type': 'intro'},
            {'melody': dev_melody, 'bass': dev_bass, 'drums': dev_drums, 'type': 'development'},
            {'melody': chorus_melody, 'bass': chorus_bass, 'drums': chorus_drums, 'type': 'chorus'},
            {'melody': chorus_melody, 'bass': chorus_bass, 'drums': chorus_drums, 'type': 'chorus'},
        ],
        'scale': scale,
        'bass_scale': bass_scale,
    }


def create_theme_2():
    """
    Theme 2: Creeps (Levels 6-10)
    Key: C Ionian #5 (Augmented feel)
    Mood: Growing menace, unease, bats emerging
    """
    scale = get_scale_notes('C', 'ionian_sharp5', 4)
    bass_scale = get_scale_notes('C', 'ionian_sharp5', 2)

    note_dur = 0.14  # Slightly slower, more ominous

    # === INTRO (creeping chromatic) ===
    intro_melody = [scale[0], 0, scale[1], 0,
                    scale[2], 0, scale[4], 0,  # Augmented 5th!
                    scale[0], 0, scale[1], 0,
                    scale[4], scale[2], scale[1], scale[0]]

    intro_bass = [bass_scale[0], 0, 0, bass_scale[0],
                  bass_scale[4], 0, 0, bass_scale[4],
                  bass_scale[0], 0, 0, bass_scale[0],
                  bass_scale[4], bass_scale[2], 0, 0]

    # === DEVELOPMENT (tension building) ===
    dev_melody = [scale[4], scale[5], scale[4], scale[2],
                  scale[4], scale[5], scale[6], scale[4],
                  scale[2], scale[4], scale[2], scale[0],
                  scale[4], 0, scale[4], 0]

    dev_bass = [bass_scale[2], 0, bass_scale[4], 0,
                bass_scale[5], 0, bass_scale[4], 0,
                bass_scale[2], 0, bass_scale[0], 0,
                bass_scale[4], bass_scale[4], 0, 0]

    # === CHORUS (menace revealed) ===
    chorus_melody = [scale[0], scale[4], scale[0], scale[4],
                     scale[2], scale[5], scale[2], scale[5],
                     scale[0], scale[4], scale[7], scale[4],
                     scale[2], scale[0], scale[4], 0]

    chorus_bass = [bass_scale[0], 0, bass_scale[0], 0,
                   bass_scale[2], 0, bass_scale[2], 0,
                   bass_scale[0], 0, bass_scale[4], 0,
                   bass_scale[2], bass_scale[0], 0, 0]

    intro_drums = [1, 0, 3, 0, 1, 0, 3, 0, 1, 0, 3, 0, 1, 2, 0, 0]
    dev_drums = [1, 3, 0, 3, 1, 3, 2, 0, 1, 3, 0, 3, 1, 0, 2, 2]
    chorus_drums = [1, 3, 2, 3, 1, 3, 2, 3, 1, 3, 2, 3, 1, 1, 2, 2]

    return {
        'name': 'Creeps',
        'tempo': note_dur,
        'sections': [
            {'melody': intro_melody, 'bass': intro_bass, 'drums': intro_drums, 'type': 'intro'},
            {'melody': dev_melody, 'bass': dev_bass, 'drums': dev_drums, 'type': 'development'},
            {'melody': chorus_melody, 'bass': chorus_bass, 'drums': chorus_drums, 'type': 'chorus'},
            {'melody': chorus_melody, 'bass': chorus_bass, 'drums': chorus_drums, 'type': 'chorus'},
        ],
        'scale': scale,
        'bass_scale': bass_scale,
    }


def create_theme_3():
    """
    Theme 3: Entering The Wastes (Levels 11-15)
    Key: B Locrian
    Mood: Desolate, dark, unstable - arrival at rotten lands
    """
    scale = get_scale_notes('B', 'locrian', 4)
    bass_scale = get_scale_notes('B', 'locrian', 2)

    note_dur = 0.16  # Slower, heavier

    # === INTRO (descending into darkness) ===
    intro_melody = [scale[7], scale[6], scale[5], scale[4],
                    scale[3], scale[2], scale[1], scale[0],
                    scale[0], 0, scale[1], scale[0],
                    0, 0, scale[0], 0]

    intro_bass = [bass_scale[0], 0, 0, 0,
                  bass_scale[0], 0, bass_scale[4], 0,
                  bass_scale[0], 0, 0, 0,
                  bass_scale[0], bass_scale[0], 0, 0]

    # === DEVELOPMENT (wandering lost) ===
    dev_melody = [scale[0], scale[2], scale[0], scale[2],
                  scale[3], scale[4], scale[3], scale[2],
                  scale[0], scale[1], scale[0], 0,
                  scale[4], scale[3], scale[2], scale[0]]

    dev_bass = [bass_scale[0], 0, bass_scale[4], 0,
                bass_scale[3], 0, bass_scale[2], 0,
                bass_scale[0], 0, 0, 0,
                bass_scale[4], 0, bass_scale[0], 0]

    # === CHORUS (dread settles in) ===
    chorus_melody = [scale[0], 0, scale[4], 0,
                     scale[3], scale[2], scale[1], scale[0],
                     scale[0], 0, scale[4], scale[3],
                     scale[2], scale[1], scale[0], 0]

    chorus_bass = [bass_scale[0], bass_scale[0], 0, 0,
                   bass_scale[3], 0, bass_scale[0], 0,
                   bass_scale[0], bass_scale[0], 0, 0,
                   bass_scale[4], bass_scale[3], bass_scale[0], 0]

    intro_drums = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 2, 0, 1, 0, 0, 0]
    dev_drums = [1, 0, 0, 3, 1, 0, 2, 0, 1, 0, 0, 3, 1, 2, 0, 0]
    chorus_drums = [1, 0, 2, 0, 1, 0, 2, 0, 1, 0, 2, 0, 1, 1, 2, 0]

    return {
        'name': 'Entering The Wastes',
        'tempo': note_dur,
        'sections': [
            {'melody': intro_melody, 'bass': intro_bass, 'drums': intro_drums, 'type': 'intro'},
            {'melody': dev_melody, 'bass': dev_bass, 'drums': dev_drums, 'type': 'development'},
            {'melody': chorus_melody, 'bass': chorus_bass, 'drums': chorus_drums, 'type': 'chorus'},
            {'melody': chorus_melody, 'bass': chorus_bass, 'drums': chorus_drums, 'type': 'chorus'},
        ],
        'scale': scale,
        'bass_scale': bass_scale,
    }


def create_theme_4():
    """
    Theme 4: The Circle (Levels 16-20)
    Key: E Phrygian
    Mood: Ancient evil, ritualistic, ominous power center
    """
    scale = get_scale_notes('E', 'phrygian', 4)
    bass_scale = get_scale_notes('E', 'phrygian', 2)

    note_dur = 0.13  # Faster, more urgent

    # === INTRO (ritual begins - Spanish/Arabic feel) ===
    intro_melody = [scale[0], scale[1], scale[0], 0,
                    scale[0], scale[1], scale[2], scale[1],
                    scale[0], scale[1], scale[0], 0,
                    scale[4], scale[3], scale[2], scale[0]]

    intro_bass = [bass_scale[0], 0, bass_scale[0], 0,
                  bass_scale[4], 0, bass_scale[0], 0,
                  bass_scale[0], 0, bass_scale[0], 0,
                  bass_scale[4], bass_scale[3], bass_scale[0], 0]

    # === DEVELOPMENT (circling the center) ===
    dev_melody = [scale[4], scale[5], scale[4], scale[3],
                  scale[2], scale[3], scale[4], scale[3],
                  scale[2], scale[1], scale[0], scale[1],
                  scale[2], scale[3], scale[4], 0]

    dev_bass = [bass_scale[4], 0, bass_scale[3], 0,
                bass_scale[2], 0, bass_scale[4], 0,
                bass_scale[0], 0, bass_scale[2], 0,
                bass_scale[4], 0, 0, 0]

    # === CHORUS (power revealed) ===
    chorus_melody = [scale[0], scale[4], scale[0], scale[4],
                     scale[0], scale[1], scale[4], scale[1],
                     scale[0], scale[4], scale[7], scale[4],
                     scale[1], scale[0], 0, 0]

    chorus_bass = [bass_scale[0], 0, bass_scale[4], 0,
                   bass_scale[0], 0, bass_scale[4], 0,
                   bass_scale[0], 0, bass_scale[4], 0,
                   bass_scale[0], bass_scale[0], bass_scale[0], 0]

    intro_drums = [1, 3, 3, 3, 1, 3, 2, 3, 1, 3, 3, 3, 1, 2, 2, 0]
    dev_drums = [1, 3, 2, 3, 1, 3, 2, 3, 1, 3, 2, 3, 1, 3, 2, 2]
    chorus_drums = [1, 1, 2, 3, 1, 1, 2, 3, 1, 1, 2, 3, 1, 2, 1, 2]

    return {
        'name': 'The Circle',
        'tempo': note_dur,
        'sections': [
            {'melody': intro_melody, 'bass': intro_bass, 'drums': intro_drums, 'type': 'intro'},
            {'melody': dev_melody, 'bass': dev_bass, 'drums': dev_drums, 'type': 'development'},
            {'melody': chorus_melody, 'bass': chorus_bass, 'drums': chorus_drums, 'type': 'chorus'},
            {'melody': chorus_melody, 'bass': chorus_bass, 'drums': chorus_drums, 'type': 'chorus'},
        ],
        'scale': scale,
        'bass_scale': bass_scale,
    }


def create_theme_5():
    """
    Theme 5: The Leech (Levels 21-25)
    Key: D Dorian
    Mood: Epic battle, tension, heroic struggle against the giant bat
    """
    scale = get_scale_notes('D', 'dorian', 4)
    bass_scale = get_scale_notes('D', 'dorian', 2)

    note_dur = 0.11  # Fast, intense battle music

    # === INTRO (the beast appears) ===
    intro_melody = [scale[0], 0, scale[0], scale[2],
                    scale[4], scale[5], scale[4], 0,
                    scale[0], 0, scale[0], scale[2],
                    scale[4], scale[7], scale[4], scale[2]]

    intro_bass = [bass_scale[0], bass_scale[0], 0, bass_scale[0],
                  bass_scale[4], 0, bass_scale[4], 0,
                  bass_scale[0], bass_scale[0], 0, bass_scale[0],
                  bass_scale[5], 0, bass_scale[4], 0]

    # === DEVELOPMENT (the fight rages) ===
    dev_melody = [scale[7], scale[6], scale[5], scale[4],
                  scale[5], scale[6], scale[7], scale[9],
                  scale[7], scale[5], scale[4], scale[2],
                  scale[4], scale[5], scale[4], 0]

    dev_bass = [bass_scale[5], 0, bass_scale[4], 0,
                bass_scale[5], 0, bass_scale[6], 0,
                bass_scale[5], 0, bass_scale[4], 0,
                bass_scale[0], bass_scale[0], 0, 0]

    # === CHORUS (heroic stand) ===
    chorus_melody = [scale[0], scale[2], scale[4], scale[5],
                     scale[7], scale[5], scale[4], scale[2],
                     scale[0], scale[2], scale[4], scale[7],
                     scale[9], scale[7], scale[5], scale[4]]

    chorus_bass = [bass_scale[0], 0, bass_scale[4], 0,
                   bass_scale[5], 0, bass_scale[4], 0,
                   bass_scale[0], 0, bass_scale[4], 0,
                   bass_scale[5], bass_scale[4], bass_scale[2], bass_scale[0]]

    intro_drums = [1, 3, 2, 3, 1, 3, 2, 3, 1, 3, 2, 3, 1, 1, 2, 2]
    dev_drums = [1, 1, 2, 3, 1, 1, 2, 3, 1, 1, 2, 3, 1, 2, 1, 2]
    chorus_drums = [1, 3, 1, 2, 1, 3, 1, 2, 1, 3, 1, 2, 1, 1, 1, 2]

    return {
        'name': 'The Leech',
        'tempo': note_dur,
        'sections': [
            {'melody': intro_melody, 'bass': intro_bass, 'drums': intro_drums, 'type': 'intro'},
            {'melody': dev_melody, 'bass': dev_bass, 'drums': dev_drums, 'type': 'development'},
            {'melody': chorus_melody, 'bass': chorus_bass, 'drums': chorus_drums, 'type': 'chorus'},
            {'melody': chorus_melody, 'bass': chorus_bass, 'drums': chorus_drums, 'type': 'chorus'},
        ],
        'scale': scale,
        'bass_scale': bass_scale,
    }


def create_theme_6():
    """
    Theme 6: Homebound (Levels 26-30)
    Key: A Minor (Aeolian)
    Mood: Bittersweet victory, melancholic return, survivors scarred
    """
    scale = get_scale_notes('A', 'minor', 4)
    bass_scale = get_scale_notes('A', 'minor', 2)

    note_dur = 0.15  # Slower, reflective

    # === INTRO (the long walk home) ===
    intro_melody = [scale[0], scale[2], scale[4], scale[2],
                    scale[0], 0, 0, 0,
                    scale[4], scale[5], scale[4], scale[2],
                    scale[0], 0, 0, 0]

    intro_bass = [bass_scale[0], 0, 0, 0,
                  bass_scale[0], 0, bass_scale[4], 0,
                  bass_scale[5], 0, 0, 0,
                  bass_scale[0], 0, 0, 0]

    # === DEVELOPMENT (memories of fallen friends) ===
    dev_melody = [scale[7], 0, scale[6], scale[5],
                  scale[4], scale[5], scale[4], 0,
                  scale[2], 0, scale[4], scale[2],
                  scale[0], 0, 0, 0]

    dev_bass = [bass_scale[5], 0, bass_scale[4], 0,
                bass_scale[3], 0, bass_scale[2], 0,
                bass_scale[0], 0, bass_scale[4], 0,
                bass_scale[0], 0, 0, 0]

    # === CHORUS (home at last, but changed forever) ===
    chorus_melody = [scale[0], scale[2], scale[4], scale[7],
                     scale[4], scale[2], scale[0], 0,
                     scale[0], scale[2], scale[4], scale[5],
                     scale[4], scale[2], scale[0], 0]

    chorus_bass = [bass_scale[0], 0, bass_scale[4], 0,
                   bass_scale[3], 0, bass_scale[0], 0,
                   bass_scale[0], 0, bass_scale[4], 0,
                   bass_scale[5], bass_scale[4], bass_scale[0], 0]

    intro_drums = [1, 0, 0, 3, 0, 0, 2, 0, 1, 0, 0, 3, 0, 0, 2, 0]
    dev_drums = [1, 0, 3, 0, 1, 0, 2, 0, 1, 0, 3, 0, 1, 0, 0, 0]
    chorus_drums = [1, 3, 0, 2, 1, 3, 0, 2, 1, 3, 0, 2, 1, 0, 2, 0]

    return {
        'name': 'Homebound',
        'tempo': note_dur,
        'sections': [
            {'melody': intro_melody, 'bass': intro_bass, 'drums': intro_drums, 'type': 'intro'},
            {'melody': dev_melody, 'bass': dev_bass, 'drums': dev_drums, 'type': 'development'},
            {'melody': chorus_melody, 'bass': chorus_bass, 'drums': chorus_drums, 'type': 'chorus'},
            {'melody': chorus_melody, 'bass': chorus_bass, 'drums': chorus_drums, 'type': 'chorus'},
        ],
        'scale': scale,
        'bass_scale': bass_scale,
    }


# =============================================================================
# DYNAMIC MUSIC GENERATION
# =============================================================================

def get_theme_for_level(level):
    """Get the appropriate theme for the current level."""
    # TEMP: Change theme every level for testing (normally every 5 levels)
    theme_idx = ((level - 1) % 6) + 1
    if theme_idx == 1:
        return create_theme_1()
    elif theme_idx == 2:
        return create_theme_2()
    elif theme_idx == 3:
        return create_theme_3()
    elif theme_idx == 4:
        return create_theme_4()
    elif theme_idx == 5:
        return create_theme_5()
    else:
        return create_theme_6()
    # ORIGINAL CODE (restore when done testing):
    # if level <= 5:
    #     return create_theme_1()
    # elif level <= 10:
    #     return create_theme_2()
    # elif level <= 15:
    #     return create_theme_3()
    # elif level <= 20:
    #     return create_theme_4()
    # elif level <= 25:
    #     return create_theme_5()
    # else:
    #     return create_theme_6()


def generate_track_for_bird(bird_type, notes, note_dur, scale, volume=0.25):
    """Generate a musical track for a specific bird's instrument."""
    instrument = BIRD_INSTRUMENTS.get(bird_type)
    if not instrument:
        return np.zeros(int(SAMPLE_RATE * note_dur * len(notes)), dtype=np.float32)

    wave = np.array([], dtype=np.float32)
    gen = instrument['gen']

    for note_freq in notes:
        if note_freq == 0:
            wave = np.concatenate([wave, np.zeros(int(SAMPLE_RATE * note_dur), dtype=np.float32)])
        else:
            if gen == 'arpeggio':
                # Patchwork plays arpeggios
                arp_freqs = [note_freq, note_freq * 1.25, note_freq * 1.5, note_freq * 2]
                w = arpeggio_wave(arp_freqs, note_dur, volume=volume)
            elif bird_type == 'YELLOW':
                w = square_wave(note_freq, note_dur, duty_cycle=0.25, volume=volume)
            elif bird_type == 'PURPLE':
                w = pwm_wave(note_freq, note_dur, mod_freq=3, volume=volume)
            else:
                w = gen(note_freq, note_dur, volume=volume)

            w = apply_envelope(w, attack=0.01, decay=0.05, sustain=0.7, release=0.05)
            wave = np.concatenate([wave, w])

    return wave


def generate_drums(pattern, note_dur, volume=0.2):
    """Generate drum pattern."""
    wave = np.array([], dtype=np.float32)
    for hit in pattern:
        if hit == 0:
            wave = np.concatenate([wave, np.zeros(int(SAMPLE_RATE * note_dur), dtype=np.float32)])
        elif hit == 1:  # Kick
            w = triangle_wave(60, note_dur * 0.3, volume=volume)
            w = apply_envelope(w, attack=0.001, decay=0.1, sustain=0.2, release=0.05)
            padding = np.zeros(int(SAMPLE_RATE * note_dur) - len(w), dtype=np.float32)
            wave = np.concatenate([wave, w, padding])
        elif hit == 2:  # Snare
            w = noise(note_dur * 0.15, volume=volume * 0.6)
            padding = np.zeros(int(SAMPLE_RATE * note_dur) - len(w), dtype=np.float32)
            wave = np.concatenate([wave, w, padding])
        elif hit == 3:  # Hi-hat
            w = noise(note_dur * 0.08, volume=volume * 0.3)
            padding = np.zeros(int(SAMPLE_RATE * note_dur) - len(w), dtype=np.float32)
            wave = np.concatenate([wave, w, padding])
    return wave


def create_dynamic_music(theme, active_birds):
    """
    Create music with instruments based on active birds.

    The music always has drums as base.
    Each bird type present adds its instrument playing a part:
    - DINOSAUR/bass birds: play bass line
    - YELLOW/BLUE/lead birds: play melody
    - Others: play harmonies or accents
    """
    sections = theme['sections']
    tempo = theme['tempo']
    scale = theme['scale']

    all_waves = []

    for section in sections:
        melody = section['melody']
        bass = section['bass']
        drums = section['drums']

        section_len = int(SAMPLE_RATE * tempo * len(melody))
        section_wave = np.zeros(section_len, dtype=np.float32)

        # Always add drums (base rhythm)
        drum_wave = generate_drums(drums, tempo, volume=0.15)
        if len(drum_wave) <= section_len:
            section_wave[:len(drum_wave)] += drum_wave
        else:
            section_wave += drum_wave[:section_len]

        # Add instruments based on active birds
        for bird_type in active_birds:
            instrument = BIRD_INSTRUMENTS.get(bird_type)
            if not instrument:
                continue

            role = instrument['role']

            # Determine which notes this bird plays
            if role == 'bass':
                notes = bass
                vol = 0.3
            elif role in ['lead', 'melody', 'lead2']:
                notes = melody
                vol = 0.2
            elif role == 'harmony':
                # Play melody transposed down
                notes = [n * 0.5 if n > 0 else 0 for n in melody]
                vol = 0.15
            elif role == 'pad':
                # Long notes from bass
                notes = [bass[i] if i % 4 == 0 else 0 for i in range(len(bass))]
                vol = 0.1
            elif role == 'arpeggio':
                # Fast arpeggios on melody notes
                notes = melody
                vol = 0.15
            elif role == 'accent':
                # Sparse accents
                notes = [melody[i] * 2 if i % 8 == 0 else 0 for i in range(len(melody))]
                vol = 0.2
            elif role == 'sparkle':
                # High sparkles
                notes = [melody[i] * 2 if i % 4 == 0 else 0 for i in range(len(melody))]
                vol = 0.15
            elif role == 'pluck':
                # Plucked bass notes
                notes = [bass[i] if i % 2 == 0 else 0 for i in range(len(bass))]
                vol = 0.2
            elif role == 'percussion':
                # Rhythmic ticks
                notes = [200 if drums[i] == 1 else 0 for i in range(len(drums))]
                vol = 0.1
            elif role == 'atmosphere':
                # Very sparse pad
                notes = [bass[0] if i == 0 else 0 for i in range(len(bass))]
                vol = 0.1
            elif role == 'chaos':
                # Random chaos
                notes = [np.random.choice(melody) if np.random.random() > 0.7 else 0 for _ in melody]
                vol = 0.1
            else:
                notes = melody
                vol = 0.15

            bird_wave = generate_track_for_bird(bird_type, notes, tempo, scale, vol)
            if len(bird_wave) <= section_len:
                section_wave[:len(bird_wave)] += bird_wave
            else:
                section_wave += bird_wave[:section_len]

        all_waves.append(section_wave)

    # Concatenate all sections
    full_wave = np.concatenate(all_waves)

    # Normalize
    max_val = np.max(np.abs(full_wave))
    if max_val > 0:
        full_wave = full_wave / max_val * 0.7

    return full_wave.astype(np.float32)


def create_game_music():
    """Create music for current level and bird composition."""
    global _current_level, _active_birds

    theme = get_theme_for_level(_current_level)

    with _birds_lock:
        birds = set(_active_birds) if _active_birds else {'YELLOW', 'RED', 'BLUE'}

    # If no birds, use default set
    if not birds:
        birds = {'YELLOW', 'RED', 'BLUE'}

    return create_dynamic_music(theme, birds)


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
    notes = [(523, 0.15), (659, 0.15), (784, 0.15), (1047, 0.3)]
    wave = np.array([], dtype=np.float32)
    for freq, dur in notes:
        w = square_wave(freq, dur, duty_cycle=0.5, volume=0.4)
        w = apply_envelope(w, attack=0.01, decay=0.05, sustain=0.8, release=0.05)
        wave = np.concatenate([wave, w])
    return wave


def sfx_game_over():
    """Game over sound - sad descending tones."""
    notes = [(392, 0.3), (349, 0.3), (330, 0.3), (262, 0.5)]
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

_current_music = None
_music_pos = 0


def _audio_callback(outdata, frames, time_info, status):
    """Audio callback for the output stream - mixes all active sounds."""
    global _music_pos, _current_music

    output = np.zeros(frames, dtype=np.float32)

    # Mix music
    if _music_playing and _current_music is not None:
        music_len = len(_current_music)

        for i in range(frames):
            output[i] += _current_music[_music_pos % music_len] * MUSIC_VOLUME
            _music_pos = (_music_pos + 1) % music_len

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
    global _mixer_stream, _mixer_running, _music_pos

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
        _music_pos = 0
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
        if len(_active_sounds) < 4:
            _active_sounds.append((wave.copy(), 0))


def play_sfx(name):
    """Play a named sound effect with rate limiting."""
    if not AUDIO_AVAILABLE or not _audio_enabled:
        return

    current_time = time.time()
    with _sfx_lock:
        last_time = _sfx_last_played.get(name, 0)
        if current_time - last_time < SFX_COOLDOWN:
            return
        _sfx_last_played[name] = current_time

    wave = _get_cached_sfx(name)
    if wave is not None:
        play_sound(wave)


def start_music():
    """Start background music loop."""
    global _music_playing, _current_music, _music_pos

    if not AUDIO_AVAILABLE or not _audio_enabled:
        return

    # Generate music for current state
    _current_music = create_game_music()
    _music_pos = 0

    # Start the mixer if not running
    if not _mixer_running:
        _start_mixer()

    _music_playing = True


def stop_music():
    """Stop background music."""
    global _music_playing
    _music_playing = False


_music_regen_lock = threading.Lock()
_music_regen_pending = False


def _regenerate_music_async():
    """Regenerate music in background thread."""
    global _current_music, _music_regen_pending

    try:
        new_music = create_game_music()
        with _music_regen_lock:
            _current_music = new_music
            _music_regen_pending = False
    except Exception:
        _music_regen_pending = False


def _schedule_music_regen():
    """Schedule music regeneration if not already pending."""
    global _music_regen_pending

    with _music_regen_lock:
        if _music_regen_pending:
            return  # Already pending
        _music_regen_pending = True

    thread = threading.Thread(target=_regenerate_music_async, daemon=True)
    thread.start()


def update_music_for_level(level):
    """Update music when level changes."""
    global _current_level

    # TEMP: Change every level for testing (normally every 5)
    old_level = _current_level
    _current_level = level

    # Regenerate if level changed
    if old_level != level and _music_playing:
        _schedule_music_regen()

    # ORIGINAL CODE (restore when done testing):
    # old_theme_range = (_current_level - 1) // 5
    # new_theme_range = (level - 1) // 5
    # _current_level = level
    # if old_theme_range != new_theme_range and _music_playing:
    #     _schedule_music_regen()


def update_active_birds(bird_types):
    """Update which bird types are currently active in the flock."""
    global _active_birds

    with _birds_lock:
        new_birds = set(bird_types)
        if new_birds != _active_birds:
            _active_birds = new_birds
            # Regenerate music with new bird composition (async)
            if _music_playing:
                _schedule_music_regen()


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
