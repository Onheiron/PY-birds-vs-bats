"""The instruments of the music: General MIDI programs and how their samples are taken.

Each instrument is sampled (tools/build_sample_bank.py) from ``low`` to
``high`` every ``step`` semitones, each note held ``hold`` seconds. When it
plays, a note uses the nearest sample, pitched. ``sustain``: a held note keeps
sounding (winds, strings): longer notes loop the middle of the sample; else
the note dies away by itself (plucked, struck). ``gain`` balances the mix,
``pan`` places it (-1 left, +1 right), ``release`` is the fade at note off (s).
"""

SAMPLE_RATE = 22050

INSTRUMENTS = {
    # The six world themes
    'flute': {'program': 73, 'low': 60, 'high': 96, 'hold': 4.0, 'sustain': True, 'gain': 0.9},
    'alto_sax': {'program': 65, 'low': 49, 'high': 85, 'hold': 4.0, 'sustain': True, 'gain': 0.8},
    'harpsichord': {'program': 6, 'low': 43, 'high': 85, 'hold': 2.5, 'gain': 0.8},
    'finger_bass': {'program': 33, 'low': 28, 'high': 64, 'hold': 3.0, 'gain': 1.0},
    'overdrive_guitar': {'program': 29, 'low': 40, 'high': 88, 'hold': 3.0, 'sustain': True, 'gain': 0.6},
    'violin': {'program': 40, 'low': 55, 'high': 96, 'hold': 4.0, 'sustain': True, 'gain': 0.85},
    # Birds
    'marimba': {'program': 12, 'low': 48, 'high': 90, 'hold': 1.5, 'gain': 0.9, 'pan': -0.4},  # Yellow
    'trumpet': {'program': 56, 'low': 52, 'high': 84, 'hold': 3.0, 'sustain': True, 'gain': 0.65, 'pan': 0.35},  # Red
    'brass': {'program': 61, 'low': 46, 'high': 82, 'hold': 3.0, 'sustain': True, 'gain': 0.6, 'pan': 0.35},  # Reds
    'clarinet': {'program': 71, 'low': 48, 'high': 84, 'hold': 4.0, 'sustain': True, 'gain': 0.75, 'pan': 0.15},  # Blue
    'horn': {'program': 60, 'low': 36, 'high': 72, 'hold': 4.0, 'sustain': True, 'gain': 0.6, 'pan': -0.2},  # Purple
    'celesta': {'program': 8, 'low': 60, 'high': 102, 'hold': 2.0, 'gain': 0.7, 'pan': 0.5},  # White
    'glockenspiel': {'program': 9, 'low': 72, 'high': 102, 'hold': 2.0, 'gain': 0.5, 'pan': -0.5},  # Gold
    'trombone': {'program': 57, 'low': 40, 'high': 72, 'hold': 3.0, 'sustain': True, 'gain': 0.6, 'pan': 0.2},  # Orange
    'accordion': {
        'program': 21,
        'low': 48,
        'high': 84,
        'hold': 4.0,
        'sustain': True,
        'gain': 0.5,
        'pan': -0.3,
    },  # Patchwork
    'pizzicato': {'program': 45, 'low': 36, 'high': 84, 'hold': 1.2, 'gain': 0.9, 'pan': 0.4},  # Cookie
    'music_box': {'program': 10, 'low': 72, 'high': 102, 'hold': 2.0, 'gain': 0.55, 'pan': 0.6},  # Clockwork
    'choir': {'program': 52, 'low': 48, 'high': 78, 'hold': 4.0, 'sustain': True, 'gain': 0.5},  # Stealth
    'tuba': {'program': 58, 'low': 28, 'high': 58, 'hold': 3.0, 'sustain': True, 'gain': 0.8},  # Dinosaur
    'square': {'program': 80, 'low': 48, 'high': 90, 'hold': 2.0, 'sustain': True, 'gain': 0.3, 'pan': 0.3},  # Glitch
    'pan_flute': {
        'program': 75,
        'low': 60,
        'high': 90,
        'hold': 4.0,
        'sustain': True,
        'gain': 0.6,
        'pan': -0.6,
    },  # Twister
    'harp': {'program': 46, 'low': 36, 'high': 96, 'hold': 2.5, 'gain': 0.75, 'pan': 0.5},  # Frosty
    'oboe': {'program': 68, 'low': 58, 'high': 88, 'hold': 4.0, 'sustain': True, 'gain': 0.6, 'pan': -0.25},  # Poison
    'taiko': {'program': 116, 'low': 36, 'high': 60, 'hold': 1.5, 'gain': 0.8, 'pan': -0.2},  # Berserk
    'timpani': {'program': 47, 'low': 36, 'high': 60, 'hold': 2.5, 'gain': 0.8, 'pan': 0.2},  # Rock
    'strings': {'program': 48, 'low': 36, 'high': 96, 'hold': 4.0, 'sustain': True, 'gain': 0.5},  # Rainbow
    'bassoon': {'program': 70, 'low': 34, 'high': 70, 'hold': 3.0, 'sustain': True, 'gain': 0.65, 'pan': 0.3},  # Zombie
    'tremolo': {'program': 44, 'low': 36, 'high': 72, 'hold': 4.0, 'sustain': True, 'gain': 0.45},  # bats
    # The bosses (src/services/music/boss.py)
    'church_organ': {'program': 19, 'low': 36, 'high': 84, 'hold': 4.0, 'sustain': True, 'gain': 0.45},  # Bat King
    'cello': {'program': 42, 'low': 36, 'high': 76, 'hold': 4.0, 'sustain': True, 'gain': 0.7},  # Tree, Wind
    'piccolo': {'program': 72, 'low': 62, 'high': 98, 'hold': 3.0, 'sustain': True, 'gain': 0.55},  # Wind
    'vibraphone': {'program': 11, 'low': 53, 'high': 89, 'hold': 2.5, 'gain': 0.75},  # Jelly
    'synth_bass': {'program': 38, 'low': 28, 'high': 64, 'hold': 2.0, 'gain': 0.7},  # Jelly
    'ocarina': {'program': 79, 'low': 60, 'high': 90, 'hold': 4.0, 'sustain': True, 'gain': 0.6},  # Owl
    # Drum kit (General MIDI channel 10): kick, snare, closed and open hat, crash, low tom, shaker
    'drums': {'drum': True, 'notes': [36, 38, 42, 46, 49, 45, 70], 'hold': 1.5, 'gain': 0.7},
}

# Which instrument each bird type plays (and the bats)
BIRD_INSTRUMENT = {
    'YELLOW': 'marimba',
    'RED': 'trumpet',
    'BLUE': 'clarinet',
    'PURPLE': 'horn',
    'WHITE': 'celesta',
    'GOLD': 'glockenspiel',
    'ORANGE': 'trombone',
    'PATCHWORK': 'accordion',
    'COOKIE': 'pizzicato',
    'CLOCKWORK': 'music_box',
    'STEALTH': 'choir',
    'DINOSAUR': 'tuba',
    'GLITCH': 'square',
    'TWISTER': 'pan_flute',
    'FROSTY': 'harp',
    'POISON': 'oboe',
    'BERSERK': 'taiko',
    'ROCK': 'timpani',
    'RAINBOW': 'strings',
    'ZOMBIE': 'bassoon',
    'BATS': 'tremolo',
}
