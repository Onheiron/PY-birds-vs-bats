"""Sound effects, synthesized: 8-bit style waves (pure numpy).

Every function returns a mono float32 wave at SAMPLE_RATE, in -1..1; playing
them is src/services/audio.py's job. (The music is src/services/music/:
written by the game and played with real instrument samples.)
"""

import numpy as np

# Audio settings
SAMPLE_RATE = 22050  # Lower sample rate for authentic 8-bit feel
MASTER_VOLUME = 0.3  # Global volume (0.0 - 1.0)

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
    np.linspace(0, duration, samples, False)
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


def sfx_boss_scream():
    """
    Boss scream - terrifying, distorted, low-frequency roar!
    A deep, rumbling screech that freezes birds in fear.
    """
    duration = 0.6
    samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, samples, False)

    # Low fundamental frequency with harmonic distortion
    freq_base = 120  # Deep bass
    freq_high = 400  # Higher overtone

    # Add wobble/distortion
    wobble = 1 + 0.3 * np.sin(2 * np.pi * 8 * t)  # Slow tremolo
    fast_wobble = 1 + 0.1 * np.sin(2 * np.pi * 45 * t)  # Fast vibrato

    # Generate base tone
    phase_base = np.cumsum(freq_base * wobble) / SAMPLE_RATE
    wave = np.sin(2 * np.pi * phase_base)

    # Add harsh overtones for distortion
    phase_high = np.cumsum(freq_high * fast_wobble) / SAMPLE_RATE
    wave += 0.5 * np.sin(2 * np.pi * phase_high)
    wave += 0.3 * np.sin(4 * np.pi * phase_high)  # More harmonics
    wave += 0.2 * np.sin(6 * np.pi * phase_high)

    # Add noise for texture
    noise = np.random.randn(samples) * 0.15
    wave += noise

    # Clip for distortion effect
    wave = np.clip(wave, -0.8, 0.8)

    # Envelope: quick attack, sustain, medium release
    attack = np.minimum(t / 0.05, 1.0)
    release = np.maximum(1.0 - (t - 0.4) / 0.2, 0.0)
    envelope = np.minimum(attack, release)
    wave = wave * envelope

    # Normalize
    wave = wave / np.max(np.abs(wave)) * 0.6

    return (wave * MASTER_VOLUME).astype(np.float32)


def sfx_boss_death():
    """
    Boss death - dramatic, long death cry with descending pitch!
    A satisfying victory screech as the boss falls.
    """
    duration = 0.8
    samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, samples, False)

    # Start high, descend dramatically
    freq_start = 600
    freq_end = 80
    freq = freq_start * np.exp(-t * 3)
    freq = np.maximum(freq, freq_end)

    # Add death rattle wobble
    wobble = 1 + 0.2 * np.sin(2 * np.pi * 20 * t) * np.exp(-t * 2)
    freq = freq * wobble

    # Generate with phase accumulation
    phase = np.cumsum(freq) / SAMPLE_RATE
    wave = np.sin(2 * np.pi * phase)

    # Add harmonics
    wave += 0.4 * np.sin(2 * np.pi * phase * 2)
    wave += 0.2 * np.sin(2 * np.pi * phase * 3)

    # Envelope - quick attack, long decay
    envelope = np.exp(-t * 2)
    wave = wave * envelope

    # Normalize
    wave = wave / np.max(np.abs(wave)) * 0.6

    return (wave * MASTER_VOLUME).astype(np.float32)


# =============================================================================
# SOUND EFFECT CACHE
# =============================================================================

SFX = {}  # name -> wave, filled by sfx_wave()


def sfx_wave(name):
    """The wave of a named sound effect (None if unknown); generated once."""
    makers = {
        'bounce': sfx_bounce,
        'hit': sfx_hit,
        'destroy': sfx_destroy,
        'powerup': sfx_powerup,
        'egg': sfx_egg,
        'level_up': sfx_level_up,
        'game_over': sfx_game_over,
        'bird_lost': sfx_bird_lost,
        'bat_death': sfx_bat_death,
        'boss_scream': sfx_boss_scream,
        'boss_death': sfx_boss_death,
    }
    if name not in SFX and name in makers:
        SFX[name] = makers[name]()
    return SFX.get(name)
