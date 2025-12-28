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
_audio_enabled = False
_music_playing = False
_current_level = 1
_current_theme = None
_theme_cache = {}
_game_speed_multiplier = 1.0  # 1.0 = base speed, higher = faster game

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
    """Generate triangle wave (NES Triangle channel) - BLUE bird. Soft, flute-like."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    # Basic triangle
    wave = 2 * np.abs(2 * (t * freq % 1) - 1) - 1
    # Add subtle vibrato for warmth
    vibrato = 1 + 0.003 * np.sin(2 * np.pi * 5 * t)
    wave = 2 * np.abs(2 * (t * freq * vibrato % 1) - 1) - 1
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def sawtooth_wave(freq, duration, volume=0.5):
    """Generate sawtooth wave - RED bird. Aggressive, buzzy, mid-range."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    # Main sawtooth with slight detune for thickness
    wave1 = 2 * (t * freq % 1) - 1
    wave2 = 2 * (t * freq * 1.005 % 1) - 1  # Slightly detuned
    wave = (wave1 * 0.6 + wave2 * 0.4)
    # Add some grit
    wave = np.clip(wave * 1.2, -1, 1)
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


def pwm_wave(freq, duration, mod_freq=3, volume=0.5):
    """Pulse Width Modulation wave - PURPLE bird. Synthy, evolving, mid-low."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    # Slower modulation for pad-like feel
    duty = 0.15 + 0.35 * np.sin(2 * np.pi * mod_freq * t)
    wave = np.where((t * freq) % 1 < duty, 1, -1)
    # Add sub layer for depth
    sub = np.sin(2 * np.pi * freq * 0.5 * t) * 0.3
    wave = wave * 0.7 + sub
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
    """Distorted lead - ORANGE/PHOENIX bird. Heavy, crunchy, power chords."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    # Power chord: root + fifth
    wave = np.sin(2 * np.pi * freq * t) + 0.7 * np.sin(2 * np.pi * freq * 1.5 * t)
    # Heavy clipping distortion
    wave = np.tanh(wave * 2.5)  # Softer distortion than hard clip
    wave = np.clip(wave * 1.5, -1, 1)  # Then hard clip for extra grit
    return (wave * volume * MASTER_VOLUME).astype(np.float32)


def pad_wave(freq, duration, volume=0.5):
    """Soft ambient pad - STEALTH bird. Low, dark, atmospheric."""
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    # Dark pad with sub emphasis
    wave = (np.sin(2 * np.pi * freq * t) * 0.3 +
            np.sin(2 * np.pi * freq * 0.5 * t) * 0.5 +   # Sub octave dominant
            np.sin(2 * np.pi * freq * 0.25 * t) * 0.2)   # Double sub
    # Slow attack and release
    envelope = np.sin(np.pi * t / duration) ** 0.3  # Slower attack
    return (wave * envelope * volume * MASTER_VOLUME).astype(np.float32)


def bass_wave(freq, duration, volume=1.0):
    """
    DINOSAUR ROAR - Primordial, earth-shaking, SPEAKER-DESTROYING bass!
    This is a LEGENDARY bird - it must SHAKE THE FUCKING ROOM!
    """
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)

    # EARTHQUAKE sub bass layers - destroy your speakers
    sub1 = np.sin(2 * np.pi * freq * t)                    # Fundamental - LOUD
    sub2 = np.sin(2 * np.pi * freq * 0.5 * t)              # Octave below - LOUDER
    sub3 = np.sin(2 * np.pi * freq * 0.25 * t)             # 2 octaves below - MASSIVE

    # Add HEAVY growl with more distortion
    growl = np.sin(2 * np.pi * freq * 2 * t) * 0.5
    growl = np.tanh(growl * 3)  # More distortion for ANGRY growl

    # Add INTENSE rumble - prehistoric earthquake
    rumble = 1 + 0.25 * np.sin(2 * np.pi * 2.5 * t)  # Slower, deeper wobble

    # Combine all layers - SUB HEAVY MIX
    wave = (sub1 * 0.5 + sub2 * 0.7 + sub3 * 0.6 + growl * 0.4) * rumble

    # PUNCHY attack - STOMP that shakes the earth
    attack = np.minimum(t * 100, 1.0)  # Even faster attack
    # Long sustain - dinosaurs are MASSIVE
    decay = np.exp(-t * 1.8)  # Even slower decay - more sustain
    envelope = attack * (0.5 + 0.5 * decay)

    # HEAVY compression to make it PHAT AS FUCK
    wave = np.tanh(wave * 1.8) * envelope

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


def bat_dissonant_wave(freq, duration, volume=0.5):
    """
    BAT - Dissonant distorted chord pad.
    Creates eerie, unsettling harmonies with tritones and minor 2nds.
    Follows the mode but adds dissonant intervals (b9, #11, b13).
    """
    if freq == 0:
        return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)

    # Root note with distortion
    root = np.sin(2 * np.pi * freq * t)

    # DISSONANT intervals relative to root:
    # Minor 2nd (1 semitone up) - very dissonant
    minor_2nd = np.sin(2 * np.pi * freq * (2 ** (1/12)) * t) * 0.4
    # Tritone (#4/b5) - the devil's interval
    tritone = np.sin(2 * np.pi * freq * (2 ** (6/12)) * t) * 0.5
    # Minor 6th (b13) - eerie
    minor_6th = np.sin(2 * np.pi * freq * (2 ** (8/12)) * t) * 0.35
    # Major 7th - tension
    major_7th = np.sin(2 * np.pi * freq * (2 ** (11/12)) * t) * 0.3

    # Combine into dissonant cluster
    wave = root + minor_2nd + tritone + minor_6th + major_7th

    # Heavy distortion - bats are creepy!
    wave = np.tanh(wave * 2.0)

    # Add subtle LFO wobble for unease
    wobble = 1 + 0.08 * np.sin(2 * np.pi * 3.5 * t)
    wave = wave * wobble

    # Creepy attack/decay envelope
    attack = np.minimum(t * 15, 1.0)  # Medium attack
    decay = np.exp(-t * 2.5)  # Medium decay
    envelope = attack * (0.3 + 0.7 * decay)

    wave = wave * envelope

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
    'BAT': {'gen': bat_dissonant_wave, 'role': 'dissonance'},  # Creepy dissonant chords!
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
# Each theme has 14 unique tracks (one per bird/bat type) + drums
# BAT track adds DISSONANT chords that follow the mode but with alterations!
# =============================================================================

def create_theme_1():
    """
    Theme 1: Soaring The Woods (Levels 1-5)
    Key: C Major - Bright, hopeful, adventurous
    """
    s = get_scale_notes('C', 'major', 4)   # Melody octave (YELLOW, RED - high)
    b = get_scale_notes('C', 'major', 2)   # Bass octave (DINOSAUR, STEALTH - very low)
    l = get_scale_notes('C', 'major', 3)   # Low-mid octave (BLUE, PURPLE, COOKIE - warm)
    h = get_scale_notes('C', 'major', 5)   # High octave (WHITE, GOLD)
    hh = get_scale_notes('C', 'major', 6)  # Very high (CLOCKWORK clicks)

    tempo = 0.35  # Very slow and chill at start!

    # 16 notes per section, 4 sections = 64 notes total loop
    # Each bird has UNIQUE notes that complement each other!

    tracks = {
        # YELLOW - Square wave lead melody (main theme)
        'YELLOW': [s[0], s[2], s[4], s[2], s[0], s[2], s[4], s[7],
                   s[4], s[5], s[6], s[7], s[6], s[5], s[4], s[2],
                   s[0], s[2], s[4], s[2], s[4], s[7], s[4], s[7],
                   s[0], s[2], s[4], s[2], s[4], s[7], s[9], s[7]],

        # RED - Sawtooth harmony (thirds above melody)
        'RED': [s[2], s[4], s[6], s[4], s[2], s[4], s[6], s[9],
                s[6], s[7], 0, s[9], 0, s[7], s[6], s[4],
                s[2], s[4], s[6], s[4], s[6], s[9], s[6], s[9],
                s[2], s[4], s[6], s[4], s[6], s[9], s[11], s[9]],

        # BLUE - Triangle wave countermelody (LOW-MID octave for warmth!)
        'BLUE': [l[7], l[4], l[2], l[4], l[7], l[4], l[2], 0,
                 l[2], 0, l[4], 0, l[2], 0, l[7], l[4],
                 l[7], l[4], l[2], l[4], l[2], 0, l[2], 0,
                 l[7], l[4], l[2], l[4], l[2], 0, 0, 0],

        # DINOSAUR - Deep bass (root notes, octaves)
        'DINOSAUR': [b[0], 0, b[0], 0, b[4], 0, b[4], 0,
                     b[3], 0, b[5], 0, b[4], 0, b[2], 0,
                     b[0], b[0], b[4], 0, b[2], b[2], b[4], 0,
                     b[0], b[0], b[4], 0, b[5], b[4], b[2], b[0]],

        # PURPLE - PWM pad (sustained chords, LOW-MID octave)
        'PURPLE': [l[0], 0, 0, 0, l[4], 0, 0, 0,
                   l[3], 0, 0, 0, l[4], 0, 0, 0,
                   l[0], 0, 0, 0, l[2], 0, 0, 0,
                   l[0], 0, 0, 0, l[5], 0, l[4], 0],

        # WHITE - Bell accents (sparse, HIGH octave)
        'WHITE': [h[0], 0, 0, 0, 0, 0, 0, h[4],
                  0, 0, 0, 0, h[7], 0, 0, 0,
                  h[0], 0, 0, 0, 0, 0, 0, h[4],
                  0, 0, 0, 0, h[9], 0, h[7], 0],

        # ORANGE - Distorted power notes (fifths)
        'ORANGE': [s[0], 0, s[4], 0, s[0], 0, s[4], 0,
                   s[3], 0, s[7], 0, s[4], 0, 0, 0,
                   s[0], 0, s[4], 0, s[2], 0, s[6], 0,
                   s[0], 0, s[4], 0, s[5], 0, s[4], 0],

        # GOLD - Glockenspiel sparkles (arpeggiated high)
        'GOLD': [h[0], h[2], h[4], 0, h[0], h[2], h[4], h[7],
                 h[4], 0, h[6], 0, h[7], 0, h[4], 0,
                 h[0], h[2], h[4], 0, h[4], h[7], h[4], 0,
                 h[0], h[2], h[4], h[7], h[4], 0, h[9], h[7]],

        # PATCHWORK - Arpeggio (fast cycling through chord)
        'PATCHWORK': [s[0], s[2], s[4], s[7], s[4], s[2], s[0], s[2],
                      s[3], s[5], s[7], s[5], s[4], s[6], s[4], s[2],
                      s[0], s[2], s[4], s[2], s[2], s[4], s[6], s[4],
                      s[0], s[2], s[4], s[7], s[5], s[4], s[2], s[0]],

        # COOKIE - Pluck (rhythmic, offbeat, LOW-MID)
        'COOKIE': [0, l[0], 0, l[2], 0, l[4], 0, l[2],
                   0, l[3], 0, l[5], 0, l[4], 0, l[2],
                   0, l[0], 0, l[2], 0, l[4], 0, l[2],
                   0, l[0], 0, l[4], 0, l[5], 0, l[4]],

        # CLOCKWORK - Mechanical tick (rhythmic, VERY HIGH clicks)
        'CLOCKWORK': [hh[0], 0, hh[4], 0, hh[0], 0, hh[4], 0,
                      hh[0], 0, hh[4], 0, hh[0], hh[4], 0, 0,
                      hh[0], 0, hh[4], 0, hh[0], 0, hh[4], 0,
                      hh[0], 0, hh[4], 0, hh[0], hh[0], hh[4], hh[4]],

        # STEALTH - Atmospheric pad (very long notes, VERY LOW)
        'STEALTH': [b[0], 0, 0, 0, 0, 0, 0, 0,
                    b[3], 0, 0, 0, 0, 0, 0, 0,
                    b[0], 0, 0, 0, 0, 0, 0, 0,
                    b[5], 0, 0, 0, b[4], 0, 0, 0],

        # GLITCH - Chaos (random from scale)
        'GLITCH': [s[0], 0, s[7], 0, s[2], s[9], 0, s[4],
                   s[6], 0, s[1], 0, s[5], 0, s[3], 0,
                   0, s[4], 0, s[0], 0, s[7], s[2], 0,
                   s[5], 0, 0, s[9], 0, s[4], 0, s[0]],

        # BAT - Dissonant chord pad (follows root chords but ALTERED!)
        # In C Major: plays altered tensions that clash with the happy key
        # Uses b (octave 2) for dark, eerie dissonance
        'BAT': [b[0], 0, 0, 0, b[1], 0, 0, 0,   # C then Db (b9 dissonance!)
                b[3], 0, 0, b[6], 0, 0, 0, 0,   # F then B (tritone!)
                b[0], 0, b[1], 0, 0, 0, b[6], 0,  # C, Db, B - maximum tension
                b[0], 0, 0, 0, b[1], b[6], 0, 0],  # Cluster of doom
    }

    drums = [1, 3, 2, 3, 1, 3, 2, 3, 1, 3, 2, 3, 1, 3, 2, 3,
             1, 3, 3, 3, 1, 3, 2, 3, 1, 3, 3, 3, 1, 2, 1, 2]

    return {'name': 'Soaring The Woods', 'tempo': tempo, 'tracks': tracks, 'drums': drums, 'scale': s}


def create_theme_2():
    """
    Theme 2: Creeps (Levels 6-10)
    Key: C Ionian #5 - Growing menace, unease
    """
    s = get_scale_notes('C', 'ionian_sharp5', 4)   # Melody (YELLOW, RED - high)
    b = get_scale_notes('C', 'ionian_sharp5', 2)   # Bass (DINOSAUR, STEALTH)
    l = get_scale_notes('C', 'ionian_sharp5', 3)   # Low-mid (BLUE, PURPLE, COOKIE)
    h = get_scale_notes('C', 'ionian_sharp5', 5)   # High (WHITE, GOLD)
    hh = get_scale_notes('C', 'ionian_sharp5', 6)  # Very high (CLOCKWORK)

    tempo = 0.38  # Building tension, still relaxed

    tracks = {
        'YELLOW': [s[0], 0, s[1], 0, s[2], 0, s[4], 0,
                   s[4], s[5], s[4], s[2], s[4], 0, s[4], 0,
                   s[0], s[4], s[0], s[4], s[2], s[5], s[2], s[5],
                   s[0], s[4], s[0], s[4], s[2], s[0], s[4], 0],

        'RED': [s[2], 0, s[3], 0, s[4], 0, s[6], 0,
                s[6], 0, s[6], s[4], s[6], 0, s[6], 0,
                s[2], s[6], s[2], s[6], s[4], 0, s[4], 0,
                s[2], s[6], s[2], s[6], s[4], s[2], s[6], 0],

        'BLUE': [l[4], 0, 0, 0, l[6], 0, 0, l[4],
                 l[2], 0, l[2], 0, 0, 0, l[2], 0,
                 l[4], 0, l[4], 0, 0, l[2], 0, l[2],
                 l[4], 0, l[4], 0, 0, l[4], 0, 0],

        'DINOSAUR': [b[0], 0, 0, b[0], b[4], 0, 0, b[4],
                     b[2], 0, b[4], 0, b[4], b[4], 0, 0,
                     b[0], 0, b[0], 0, b[2], 0, b[2], 0,
                     b[0], 0, b[4], 0, b[2], b[0], 0, 0],

        'PURPLE': [l[4], 0, 0, 0, 0, 0, 0, 0,
                   l[6], 0, 0, 0, 0, 0, 0, 0,
                   l[4], 0, 0, 0, l[2], 0, 0, 0,
                   l[4], 0, 0, 0, 0, 0, 0, 0],

        'WHITE': [0, 0, 0, 0, h[4], 0, 0, 0,
                  0, 0, 0, 0, 0, 0, h[6], 0,
                  h[0], 0, 0, 0, 0, 0, 0, 0,
                  0, 0, h[4], 0, 0, 0, 0, 0],

        'ORANGE': [s[0], 0, 0, s[4], 0, 0, s[4], 0,
                   s[4], 0, 0, s[4], s[6], 0, 0, 0,
                   s[0], 0, s[4], 0, s[2], 0, s[5], 0,
                   s[0], 0, s[4], 0, s[2], 0, 0, 0],

        'GOLD': [h[0], 0, h[1], 0, h[2], 0, h[4], 0,
                 h[4], 0, 0, h[4], 0, 0, h[4], 0,
                 h[0], 0, h[4], 0, h[2], 0, h[5], 0,
                 h[0], 0, h[4], 0, 0, h[0], h[4], 0],

        'PATCHWORK': [s[0], s[4], s[6], s[4], s[0], s[4], s[6], s[4],
                      s[2], s[4], s[6], s[4], s[4], s[6], 0, s[4],
                      s[0], s[4], s[0], s[4], s[2], s[5], s[2], s[5],
                      s[0], s[4], s[0], s[4], s[2], s[0], 0, 0],

        'COOKIE': [0, l[0], 0, 0, 0, l[4], 0, 0,
                   0, l[2], 0, l[4], 0, 0, 0, 0,
                   0, l[0], 0, l[4], 0, l[2], 0, l[5],
                   0, l[0], 0, l[4], 0, l[2], 0, 0],

        'CLOCKWORK': [hh[0], 0, 0, hh[4], hh[0], 0, 0, hh[4],
                      hh[0], 0, 0, hh[4], hh[0], hh[4], 0, 0,
                      hh[0], 0, hh[4], 0, hh[0], 0, hh[4], 0,
                      hh[0], 0, hh[4], 0, hh[0], hh[4], 0, 0],

        'STEALTH': [b[0], 0, 0, 0, 0, 0, 0, 0,
                    b[4], 0, 0, 0, 0, 0, 0, 0,
                    b[0], 0, 0, 0, b[2], 0, 0, 0,
                    b[0], 0, 0, 0, 0, 0, 0, 0],

        'GLITCH': [s[4], 0, 0, s[0], 0, s[6], 0, 0,
                   0, s[2], s[4], 0, 0, 0, s[6], 0,
                   s[0], 0, s[4], 0, 0, s[2], 0, s[5],
                   0, s[0], 0, s[4], s[6], 0, 0, 0],

        # BAT - Dissonant pad (Ionian #5 already eerie, add MORE tension!)
        # Tritones and b9s to amplify the creeping unease
        'BAT': [b[0], 0, b[1], 0, 0, 0, b[4], 0,   # C, Db, then augmented G#
                b[4], 0, 0, 0, b[1], 0, b[6], 0,   # G#, Db, B - dissonant cluster
                b[0], 0, 0, b[4], 0, b[1], 0, 0,   # Root with #5 and b9
                b[0], b[1], 0, 0, b[4], 0, b[6], 0],  # Maximum creep
    }

    drums = [1, 0, 3, 0, 1, 0, 3, 0, 1, 3, 0, 3, 1, 2, 0, 0,
             1, 3, 2, 3, 1, 3, 2, 3, 1, 3, 2, 3, 1, 1, 2, 2]

    return {'name': 'Creeps', 'tempo': tempo, 'tracks': tracks, 'drums': drums, 'scale': s}


def create_theme_3():
    """
    Theme 3: Entering The Wastes (Levels 11-15)
    Key: B Locrian - Desolate, dark, unstable
    """
    s = get_scale_notes('B', 'locrian', 4)   # Melody (YELLOW, RED - high)
    b = get_scale_notes('B', 'locrian', 2)   # Bass (DINOSAUR, STEALTH)
    l = get_scale_notes('B', 'locrian', 3)   # Low-mid (BLUE, PURPLE, COOKIE)
    h = get_scale_notes('B', 'locrian', 5)   # High (WHITE, GOLD)
    hh = get_scale_notes('B', 'locrian', 6)  # Very high (CLOCKWORK)

    tempo = 0.40  # Slow, desolate, heavy

    tracks = {
        'YELLOW': [s[0], 0, s[1], s[0], 0, 0, s[0], 0,
                   s[0], s[2], s[0], s[2], s[0], s[1], s[0], 0,
                   s[0], 0, s[4], 0, s[3], s[2], s[1], s[0],
                   s[0], 0, s[4], s[3], s[2], s[1], s[0], 0],

        'RED': [s[4], 0, 0, s[4], 0, 0, s[4], 0,
                s[3], 0, s[3], 0, s[2], 0, 0, 0,
                s[4], 0, 0, 0, 0, s[4], s[3], s[2],
                s[4], 0, 0, 0, s[4], s[3], s[2], 0],

        'BLUE': [0, l[0], 0, 0, l[4], 0, 0, l[2],
                 l[3], 0, 0, l[3], 0, 0, l[2], 0,
                 0, l[0], 0, l[4], 0, 0, 0, 0,
                 0, l[0], 0, 0, 0, 0, 0, 0],

        'DINOSAUR': [b[0], 0, 0, 0, b[0], 0, b[4], 0,
                     b[0], 0, b[4], 0, b[3], 0, b[2], 0,
                     b[0], b[0], 0, 0, b[3], 0, b[0], 0,
                     b[0], b[0], 0, 0, b[4], b[3], b[0], 0],

        'PURPLE': [l[0], 0, 0, 0, 0, 0, 0, 0,
                   l[3], 0, 0, 0, 0, 0, 0, 0,
                   l[0], 0, 0, 0, 0, 0, 0, 0,
                   l[4], 0, 0, 0, l[0], 0, 0, 0],

        'WHITE': [0, 0, 0, 0, 0, 0, 0, h[0],
                  0, 0, 0, 0, 0, 0, 0, 0,
                  h[0], 0, 0, 0, 0, 0, 0, 0,
                  0, 0, 0, 0, h[4], 0, 0, 0],

        'ORANGE': [s[0], 0, 0, 0, s[0], 0, s[4], 0,
                   s[3], 0, 0, 0, s[2], 0, 0, 0,
                   s[0], 0, s[4], 0, 0, 0, s[0], 0,
                   s[0], 0, s[4], 0, 0, 0, 0, 0],

        'GOLD': [0, 0, h[0], 0, 0, 0, h[1], 0,
                 0, 0, h[0], 0, 0, 0, 0, 0,
                 h[0], 0, 0, h[4], 0, 0, 0, 0,
                 0, 0, h[0], 0, h[4], 0, h[0], 0],

        'PATCHWORK': [s[0], s[1], s[0], 0, s[0], s[4], s[0], 0,
                      s[0], s[3], s[2], s[3], s[2], s[1], s[0], 0,
                      s[0], s[1], 0, s[4], s[3], s[2], s[1], s[0],
                      s[0], s[1], 0, s[4], s[3], s[2], s[1], 0],

        'COOKIE': [0, l[0], 0, 0, 0, 0, 0, l[4],
                   0, l[0], 0, l[3], 0, 0, 0, l[2],
                   0, l[0], 0, 0, 0, l[3], 0, 0,
                   0, l[0], 0, 0, 0, l[4], 0, 0],

        'CLOCKWORK': [hh[0], 0, 0, 0, hh[0], 0, 0, 0,
                      hh[0], 0, 0, 0, hh[0], 0, hh[4], 0,
                      hh[0], 0, hh[4], 0, hh[0], 0, hh[4], 0,
                      hh[0], 0, hh[4], 0, hh[0], hh[0], hh[4], 0],

        'STEALTH': [b[0], 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0,
                    b[0], 0, 0, 0, 0, 0, 0, 0,
                    b[4], 0, 0, 0, 0, 0, 0, 0],

        'GLITCH': [s[0], 0, 0, s[4], 0, 0, s[1], 0,
                   0, s[3], 0, 0, s[0], 0, 0, 0,
                   s[4], 0, 0, 0, 0, s[3], 0, s[0],
                   0, 0, s[1], 0, 0, 0, s[0], 0],

        # BAT - Locrian is already diminished, pile on MORE dissonance!
        # Tritone (b5) is native to Locrian, add chromatic tensions
        'BAT': [b[0], 0, 0, b[4], 0, 0, 0, 0,   # B then F (natural tritone)
                b[1], 0, 0, 0, b[4], 0, b[0], 0,   # C, F, B - cluster
                b[0], b[1], 0, 0, 0, b[4], 0, 0,   # Semitone clash + tritone
                b[0], 0, b[4], b[1], 0, 0, b[0], 0],  # Desolate chord stabs
    }

    drums = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 2, 0, 1, 0, 0, 0,
             1, 0, 2, 0, 1, 0, 2, 0, 1, 0, 2, 0, 1, 1, 2, 0]

    return {'name': 'Entering The Wastes', 'tempo': tempo, 'tracks': tracks, 'drums': drums, 'scale': s}


def create_theme_4():
    """
    Theme 4: The Circle (Levels 16-20)
    Key: E Phrygian - Ancient evil, ritualistic
    """
    s = get_scale_notes('E', 'phrygian', 4)   # Melody (YELLOW, RED - high)
    b = get_scale_notes('E', 'phrygian', 2)   # Bass (DINOSAUR, STEALTH)
    l = get_scale_notes('E', 'phrygian', 3)   # Low-mid (BLUE, PURPLE, COOKIE)
    h = get_scale_notes('E', 'phrygian', 5)   # High (WHITE, GOLD)
    hh = get_scale_notes('E', 'phrygian', 6)  # Very high (CLOCKWORK)

    tempo = 0.34  # Ritualistic, steady pulse

    tracks = {
        'YELLOW': [s[0], s[1], s[0], 0, s[0], s[1], s[2], s[1],
                   s[4], s[5], s[4], s[3], s[2], s[1], s[0], s[1],
                   s[0], s[4], s[0], s[4], s[0], s[1], s[4], s[1],
                   s[0], s[4], s[0], s[4], s[1], s[0], 0, 0],

        'RED': [s[4], 0, s[4], 0, s[4], 0, s[5], 0,
                s[7], 0, s[7], s[5], s[4], 0, s[4], 0,
                s[4], 0, s[4], 0, s[4], 0, s[7], 0,
                s[4], 0, s[4], 0, s[4], s[3], s[1], 0],

        'BLUE': [0, l[0], 0, l[1], 0, l[0], 0, 0,
                 0, l[4], 0, 0, 0, l[3], 0, l[0],
                 l[0], 0, l[4], 0, l[0], 0, 0, l[4],
                 l[0], 0, l[4], 0, 0, l[0], 0, 0],

        'DINOSAUR': [b[0], 0, b[0], 0, b[4], 0, b[0], 0,
                     b[4], 0, b[3], 0, b[2], 0, b[4], 0,
                     b[0], 0, b[4], 0, b[0], 0, b[4], 0,
                     b[0], 0, b[4], 0, b[0], b[0], b[0], 0],

        'PURPLE': [l[0], 0, 0, 0, l[4], 0, 0, 0,
                   l[4], 0, 0, 0, l[3], 0, 0, 0,
                   l[0], 0, 0, 0, l[0], 0, 0, 0,
                   l[0], 0, 0, 0, l[1], 0, 0, 0],

        'WHITE': [h[0], 0, 0, 0, 0, 0, 0, h[1],
                  0, 0, 0, h[4], 0, 0, 0, 0,
                  h[0], 0, 0, 0, 0, 0, 0, h[4],
                  0, 0, 0, 0, h[1], 0, 0, 0],

        'ORANGE': [s[0], 0, s[4], 0, s[0], 0, s[4], 0,
                   s[4], 0, s[7], 0, s[4], 0, 0, 0,
                   s[0], 0, s[4], 0, s[0], 0, s[4], 0,
                   s[0], 0, s[4], 0, s[1], 0, 0, 0],

        'GOLD': [h[0], h[1], h[0], 0, h[0], h[1], h[2], h[1],
                 h[4], 0, h[4], 0, h[3], 0, h[0], h[1],
                 h[0], 0, h[4], 0, h[0], h[1], 0, h[4],
                 h[0], 0, h[4], 0, h[1], h[0], 0, 0],

        'PATCHWORK': [s[0], s[1], s[4], s[1], s[0], s[1], s[4], s[1],
                      s[4], s[5], s[7], s[5], s[4], s[3], s[1], s[0],
                      s[0], s[4], s[0], s[4], s[0], s[1], s[4], s[1],
                      s[0], s[4], s[0], s[4], s[1], s[0], 0, 0],

        'COOKIE': [0, l[0], 0, l[1], 0, l[0], 0, l[1],
                   0, l[4], 0, l[3], 0, l[2], 0, l[0],
                   0, l[0], 0, l[4], 0, l[0], 0, l[4],
                   0, l[0], 0, l[4], 0, l[1], 0, 0],

        'CLOCKWORK': [hh[0], hh[4], hh[4], hh[4], hh[0], hh[4], hh[4], hh[4],
                      hh[0], hh[4], hh[4], hh[4], hh[0], hh[4], hh[4], 0,
                      hh[0], hh[0], hh[4], hh[4], hh[0], hh[0], hh[4], hh[4],
                      hh[0], hh[0], hh[4], hh[4], hh[0], hh[4], hh[0], hh[4]],

        'STEALTH': [b[0], 0, 0, 0, 0, 0, 0, 0,
                    b[4], 0, 0, 0, 0, 0, 0, 0,
                    b[0], 0, 0, 0, 0, 0, 0, 0,
                    b[0], 0, 0, 0, b[1], 0, 0, 0],

        'GLITCH': [s[0], s[1], 0, 0, s[4], 0, s[1], 0,
                   0, s[4], s[7], 0, 0, s[3], 0, s[0],
                   s[0], 0, s[4], 0, s[1], 0, 0, s[4],
                   0, s[0], 0, s[4], 0, s[1], 0, 0],

        # BAT - Phrygian b2 is already dark, add tritones for EVIL ritual vibes
        # E Phrygian: E-F-G-A-B-C-D, BAT adds Bb (tritone) for satanic flavor
        'BAT': [b[0], 0, b[1], 0, 0, 0, 0, b[1],   # E, F, F - ritual drone
                0, 0, b[4], 0, b[1], 0, 0, 0,      # A, F - tension
                b[0], 0, 0, b[1], 0, 0, b[4], 0,   # E, F, A - dark chord
                b[0], b[1], b[4], 0, b[0], 0, b[1], 0],  # Ritualistic pulse
    }

    drums = [1, 3, 3, 3, 1, 3, 2, 3, 1, 3, 2, 3, 1, 2, 2, 0,
             1, 1, 2, 3, 1, 1, 2, 3, 1, 1, 2, 3, 1, 2, 1, 2]

    return {'name': 'The Circle', 'tempo': tempo, 'tracks': tracks, 'drums': drums, 'scale': s}


def create_theme_5():
    """
    Theme 5: The Leech (Levels 21-25)
    Key: D Dorian - Epic battle, heroic
    """
    s = get_scale_notes('D', 'dorian', 4)   # Melody (YELLOW, RED - high)
    b = get_scale_notes('D', 'dorian', 2)   # Bass (DINOSAUR, STEALTH)
    l = get_scale_notes('D', 'dorian', 3)   # Low-mid (BLUE, PURPLE, COOKIE)
    h = get_scale_notes('D', 'dorian', 5)   # High (WHITE, GOLD)
    hh = get_scale_notes('D', 'dorian', 6)  # Very high (CLOCKWORK)

    tempo = 0.30  # Epic battle, building intensity

    tracks = {
        'YELLOW': [s[0], 0, s[0], s[2], s[4], s[5], s[4], 0,
                   s[7], s[6], s[5], s[4], s[5], s[6], s[7], s[9],
                   s[0], s[2], s[4], s[5], s[7], s[5], s[4], s[2],
                   s[0], s[2], s[4], s[7], s[9], s[7], s[5], s[4]],

        'RED': [s[4], 0, s[4], s[5], s[7], 0, s[7], 0,
                s[9], 0, s[7], s[6], s[7], 0, s[9], 0,
                s[4], s[5], s[7], 0, s[9], s[7], s[7], s[5],
                s[4], s[5], s[7], s[9], 0, s[9], s[7], s[6]],

        'BLUE': [0, l[0], 0, 0, l[2], 0, l[2], l[4],
                 l[5], 0, 0, l[2], 0, l[4], 0, 0,
                 0, 0, l[2], l[4], l[5], 0, l[2], 0,
                 0, 0, l[2], 0, l[7], 0, l[4], l[2]],

        'DINOSAUR': [b[0], b[0], 0, b[0], b[4], 0, b[4], 0,
                     b[5], 0, b[4], 0, b[5], 0, b[6], 0,
                     b[0], 0, b[4], 0, b[5], 0, b[4], 0,
                     b[0], 0, b[4], 0, b[5], b[4], b[2], b[0]],

        'PURPLE': [l[0], 0, 0, 0, l[4], 0, 0, 0,
                   l[5], 0, 0, 0, l[6], 0, 0, 0,
                   l[0], 0, 0, 0, l[5], 0, 0, 0,
                   l[0], 0, 0, 0, l[5], 0, l[4], 0],

        'WHITE': [h[0], 0, 0, 0, 0, h[5], 0, 0,
                  h[7], 0, 0, 0, 0, 0, h[9], 0,
                  h[0], 0, 0, h[4], 0, h[7], 0, 0,
                  h[0], 0, 0, h[7], h[9], 0, h[5], h[4]],

        'ORANGE': [s[0], 0, s[4], 0, s[0], 0, s[4], 0,
                   s[5], 0, s[9], 0, s[5], 0, s[9], 0,
                   s[0], 0, s[4], 0, s[5], 0, s[4], 0,
                   s[0], 0, s[4], 0, s[5], s[4], s[2], 0],

        'GOLD': [h[0], 0, h[0], h[2], h[4], h[5], h[4], 0,
                 h[7], h[6], h[5], h[4], h[5], h[6], h[7], h[9],
                 h[0], h[2], h[4], h[5], h[7], h[5], h[4], h[2],
                 h[0], h[2], h[4], h[7], h[9], h[7], h[5], h[4]],

        'PATCHWORK': [s[0], s[2], s[4], s[5], s[4], s[2], s[0], s[2],
                      s[5], s[6], s[7], s[6], s[5], s[4], s[7], s[9],
                      s[0], s[2], s[4], s[5], s[7], s[5], s[4], s[2],
                      s[0], s[2], s[4], s[7], s[9], s[7], s[5], s[4]],

        'COOKIE': [0, l[0], 0, l[2], 0, l[4], 0, l[5],
                   0, l[7], 0, l[5], 0, l[6], 0, l[9],
                   0, l[0], 0, l[4], 0, l[5], 0, l[2],
                   0, l[0], 0, l[4], 0, l[7], 0, l[4]],

        'CLOCKWORK': [hh[0], hh[4], hh[0], hh[4], hh[0], hh[4], hh[0], hh[4],
                      hh[0], hh[0], hh[4], hh[4], hh[0], hh[0], hh[4], hh[4],
                      hh[0], hh[4], hh[0], hh[4], hh[0], hh[4], hh[0], hh[4],
                      hh[0], hh[0], hh[0], hh[4], hh[0], hh[0], hh[0], hh[4]],

        'STEALTH': [b[0], 0, 0, 0, b[4], 0, 0, 0,
                    b[5], 0, 0, 0, b[4], 0, 0, 0,
                    b[0], 0, 0, 0, b[5], 0, 0, 0,
                    b[0], 0, 0, 0, b[5], 0, b[4], 0],

        'GLITCH': [s[0], 0, s[4], s[2], 0, s[5], s[7], 0,
                   s[9], 0, 0, s[4], s[6], 0, s[7], 0,
                   0, s[2], 0, s[5], s[7], 0, 0, s[2],
                   s[0], 0, s[4], 0, s[9], s[7], 0, s[4]],

        # BAT - Dorian is heroic, BAT corrupts it with chromatic evil!
        # D Dorian: D-E-F-G-A-B-C, BAT adds Eb and Ab for sinister tension
        'BAT': [b[0], 0, 0, b[1], 0, 0, b[4], 0,   # D, Eb (b9), G
                b[5], 0, b[1], 0, 0, 0, b[0], 0,   # A, Eb, D - tension
                b[0], 0, b[4], 0, b[1], 0, 0, b[5],  # Power with dissonance
                b[0], b[1], 0, b[4], 0, b[1], b[0], 0],  # Corrupted heroic chords
    }

    drums = [1, 3, 2, 3, 1, 3, 2, 3, 1, 1, 2, 3, 1, 2, 1, 2,
             1, 3, 1, 2, 1, 3, 1, 2, 1, 3, 1, 2, 1, 1, 1, 2]

    return {'name': 'The Leech', 'tempo': tempo, 'tracks': tracks, 'drums': drums, 'scale': s}


def create_theme_6():
    """
    Theme 6: Homebound (Levels 26-30)
    Key: A Minor - Bittersweet, melancholic
    """
    s = get_scale_notes('A', 'minor', 4)   # Melody (YELLOW, RED - high)
    b = get_scale_notes('A', 'minor', 2)   # Bass (DINOSAUR, STEALTH)
    l = get_scale_notes('A', 'minor', 3)   # Low-mid (BLUE, PURPLE, COOKIE)
    h = get_scale_notes('A', 'minor', 5)   # High (WHITE, GOLD)
    hh = get_scale_notes('A', 'minor', 6)  # Very high (CLOCKWORK)

    tempo = 0.38  # Bittersweet, reflective, peaceful

    tracks = {
        'YELLOW': [s[0], s[2], s[4], s[2], s[0], 0, 0, 0,
                   s[7], 0, s[6], s[5], s[4], s[5], s[4], 0,
                   s[0], s[2], s[4], s[7], s[4], s[2], s[0], 0,
                   s[0], s[2], s[4], s[5], s[4], s[2], s[0], 0],

        'RED': [s[4], s[6], s[7], s[6], s[4], 0, 0, 0,
                s[9], 0, 0, s[7], s[6], 0, s[6], 0,
                s[4], s[6], 0, s[9], s[7], s[6], s[4], 0,
                s[4], s[6], 0, s[7], s[6], s[4], s[4], 0],

        'BLUE': [0, l[0], 0, l[0], 0, l[4], 0, l[2],
                 l[5], 0, l[4], 0, 0, l[2], 0, 0,
                 0, l[0], 0, l[4], 0, 0, 0, l[0],
                 0, l[0], 0, l[2], 0, 0, 0, 0],

        'DINOSAUR': [b[0], 0, 0, 0, b[0], 0, b[4], 0,
                     b[5], 0, b[4], 0, b[3], 0, b[2], 0,
                     b[0], 0, b[4], 0, b[3], 0, b[0], 0,
                     b[0], 0, b[4], 0, b[5], b[4], b[0], 0],

        'PURPLE': [l[0], 0, 0, 0, 0, 0, 0, 0,
                   l[5], 0, 0, 0, l[4], 0, 0, 0,
                   l[0], 0, 0, 0, l[3], 0, 0, 0,
                   l[0], 0, 0, 0, l[5], 0, l[4], 0],

        'WHITE': [h[0], 0, 0, 0, 0, 0, 0, 0,
                  0, 0, 0, h[5], 0, 0, 0, 0,
                  h[0], 0, 0, h[7], 0, 0, 0, 0,
                  0, 0, 0, 0, h[5], 0, h[4], 0],

        'ORANGE': [s[0], 0, s[4], 0, s[0], 0, 0, 0,
                   s[5], 0, 0, s[4], 0, 0, s[4], 0,
                   s[0], 0, s[4], 0, s[3], 0, s[0], 0,
                   s[0], 0, s[4], 0, s[5], 0, 0, 0],

        'GOLD': [h[0], h[2], h[4], h[2], h[0], 0, 0, 0,
                 h[7], 0, h[6], h[5], h[4], h[5], h[4], 0,
                 h[0], h[2], h[4], h[7], h[4], h[2], h[0], 0,
                 h[0], h[2], h[4], h[5], h[4], h[2], h[0], 0],

        'PATCHWORK': [s[0], s[2], s[4], s[2], s[0], s[2], s[0], 0,
                      s[5], s[6], s[5], s[4], s[2], s[4], s[2], 0,
                      s[0], s[2], s[4], s[7], s[4], s[2], s[0], 0,
                      s[0], s[2], s[4], s[5], s[4], s[2], s[0], 0],

        'COOKIE': [0, l[0], 0, l[2], 0, 0, 0, 0,
                   0, l[5], 0, l[4], 0, l[2], 0, 0,
                   0, l[0], 0, l[4], 0, 0, 0, 0,
                   0, l[0], 0, l[2], 0, l[4], 0, 0],

        'CLOCKWORK': [hh[0], 0, 0, hh[4], 0, 0, hh[4], 0,
                      hh[0], 0, hh[4], 0, hh[0], 0, hh[4], 0,
                      hh[0], hh[4], 0, hh[4], hh[0], hh[4], 0, hh[4],
                      hh[0], 0, 0, hh[4], hh[0], 0, hh[4], 0],

        'STEALTH': [b[0], 0, 0, 0, 0, 0, 0, 0,
                    b[5], 0, 0, 0, 0, 0, 0, 0,
                    b[0], 0, 0, 0, b[3], 0, 0, 0,
                    b[0], 0, 0, 0, 0, 0, 0, 0],

        'GLITCH': [s[0], 0, 0, s[2], 0, s[4], 0, 0,
                   s[5], 0, s[6], 0, 0, s[4], 0, 0,
                   0, s[0], 0, s[7], 0, 0, s[0], 0,
                   0, s[0], 0, s[4], s[5], 0, 0, 0],

        # BAT - A Minor is melancholic, BAT makes it haunted and ghostly
        # A Minor: A-B-C-D-E-F-G, BAT adds Bb and Eb for spectral dissonance
        'BAT': [b[0], 0, 0, 0, b[1], 0, 0, 0,   # A, Bb (b9) - haunting
                b[3], 0, 0, b[1], 0, 0, 0, 0,   # D, Bb - ghostly
                b[0], 0, b[1], 0, 0, 0, b[3], 0,  # Spectral chord motion
                b[0], 0, 0, b[1], 0, b[3], 0, 0],  # Bittersweet darkness
    }

    drums = [1, 0, 0, 3, 0, 0, 2, 0, 1, 0, 3, 0, 1, 0, 0, 0,
             1, 3, 0, 2, 1, 3, 0, 2, 1, 3, 0, 2, 1, 0, 2, 0]

    return {'name': 'Homebound', 'tempo': tempo, 'tracks': tracks, 'drums': drums, 'scale': s}


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
    Each bird type has its own unique pre-composed track in the theme.
    Drums always play as base.
    Tempo scales with game speed!
    """
    global _game_speed_multiplier

    tracks = theme['tracks']
    drums = theme['drums']
    base_tempo = theme['tempo']

    # Scale tempo with game speed (faster game = faster music)
    # Speed multiplier > 1 means game is faster, so we divide tempo
    tempo = base_tempo / _game_speed_multiplier

    # Calculate total length (all tracks should have same length)
    track_len = len(drums)
    total_samples = int(SAMPLE_RATE * tempo * track_len)

    music_wave = np.zeros(total_samples, dtype=np.float32)

    # Always add drums (base rhythm)
    drum_wave = generate_drums(drums, tempo, volume=0.25)
    if len(drum_wave) <= total_samples:
        music_wave[:len(drum_wave)] += drum_wave
    else:
        music_wave += drum_wave[:total_samples]

    # Volume levels per instrument type for good mix
    # Organized by frequency range for balanced sound
    VOLUMES = {
        # HIGH (bright, cutting through)
        'YELLOW': 0.18,    # Lead melody - square wave
        'GOLD': 0.14,      # Sparkles - glockenspiel
        'WHITE': 0.16,     # Bell accents
        'CLOCKWORK': 0.08, # Ticks - very high, subtle
        # MID (body of the sound)
        'RED': 0.20,       # Harmony - thick sawtooth
        'BLUE': 0.16,      # Countermelody - warm triangle
        'ORANGE': 0.18,    # Distorted power chords
        'PATCHWORK': 0.12, # Arpeggio - mid
        # LOW-MID (warmth)
        'PURPLE': 0.18,    # PWM pad - fills the space
        'COOKIE': 0.14,    # Pluck - rhythmic low-mid
        # LEGENDARY BASS - DINOSAUR DESTROYS SPEAKERS!!!
        'DINOSAUR': 0.90,  # PRIMORDIAL ROAR - SHAKE THE FUCKING ROOM!
        'STEALTH': 0.22,   # Atmospheric low pad
        # CHAOS & DISSONANCE
        'GLITCH': 0.06,    # Chaos - subtle
        'BAT': 0.35,       # Dissonant chord pad - eerie, unsettling, should be heard!
    }

    # Add each active bird's track
    for bird_type in active_birds:
        if bird_type not in tracks:
            continue

        notes = tracks[bird_type]
        vol = VOLUMES.get(bird_type, 0.15)

        bird_wave = generate_track_for_bird(bird_type, notes, tempo, None, vol)
        if len(bird_wave) <= total_samples:
            music_wave[:len(bird_wave)] += bird_wave
        else:
            music_wave += bird_wave[:total_samples]

    # Normalize to prevent clipping
    max_val = np.max(np.abs(music_wave))
    if max_val > 0:
        music_wave = music_wave / max_val * 0.75

    return music_wave.astype(np.float32)


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


def sfx_bat_death():
    """
    Bat death screech - high-pitched ultrasonic shriek!
    Like a bat's dying cry - starts very high, wobbles, descends rapidly.
    """
    samples = int(SAMPLE_RATE * 0.25)
    t = np.linspace(0, 0.25, samples, False)

    # Start at ultrasonic-ish frequency (2500Hz), descend to 800Hz
    # Bats echolocate at 20-120kHz, but we use audible range that "feels" batty
    freq_start = 2500
    freq_end = 800
    freq = freq_start * np.exp(-t * 4.5)  # Exponential descent
    freq = np.maximum(freq, freq_end)

    # Add rapid vibrato/wobble like a dying shriek
    wobble = 1 + 0.15 * np.sin(2 * np.pi * 35 * t)  # Fast tremolo
    freq = freq * wobble

    # Generate the shriek with phase accumulation
    phase = np.cumsum(freq) / SAMPLE_RATE
    wave = np.sin(2 * np.pi * phase)

    # Add some harsh harmonics for that screechy quality
    wave += 0.3 * np.sin(4 * np.pi * phase)  # 2nd harmonic
    wave += 0.15 * np.sin(6 * np.pi * phase)  # 3rd harmonic

    # Quick attack, medium decay - like a sudden scream
    envelope = np.exp(-t * 8)
    wave = wave * envelope

    # Normalize
    wave = wave / np.max(np.abs(wave)) * 0.5

    return (wave * MASTER_VOLUME).astype(np.float32)


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
            'bat_death': sfx_bat_death,  # Shrieking bat death sound!
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


def update_game_speed(level, base_sleep=0.2, multiplier=0.88, min_sleep=0.02):
    """
    Update music tempo based on game speed.
    Higher levels = faster game = faster music.
    Music tempo increases MORE GRADUALLY than game speed!

    Args:
        level: Current game level
        base_sleep: Base sleep time (from config)
        multiplier: Frame sleep level multiplier (from config)
        min_sleep: Minimum sleep time (from config)
    """
    global _game_speed_multiplier

    # Music tempo increases gradually over 30 levels
    # Level 1: 1.0x (base tempo)
    # Level 10: ~1.15x
    # Level 20: ~1.35x
    # Level 30: ~1.6x
    # This is much gentler than game speed increase!

    # Use a gentler curve: 2% increase per level (compounding)
    # 1.02^30 ≈ 1.81 at level 30
    music_multiplier = 0.97  # Gentler than game's 0.88

    # Calculate music speed multiplier
    new_multiplier = 1.0 / (music_multiplier ** (level - 1))

    # Cap between 1.0x and 1.8x speed
    new_multiplier = min(1.8, max(1.0, new_multiplier))

    if abs(new_multiplier - _game_speed_multiplier) > 0.02:
        _game_speed_multiplier = new_multiplier
        # Regenerate music with new tempo
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
