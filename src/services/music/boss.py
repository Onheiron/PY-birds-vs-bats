"""The music of the bosses: a theme for each kind, the flock dressed in its style, the corruption.

When a boss arrives, the world's music is corrupted (a ``bridge`` of 8 bars):
for 4 bars the boss's bass creeps in under it while the world's music starts
to wobble out of tune, then for 4 more its lead takes over while the world's
music is muffled, dirtied and pushed away. Then the boss's loop plays alone.

A boss's theme is written in C and played on the world's tonic, so the
corruption stays in key. Every bird type plays its own part (score.py) on the
boss's chords, in the boss's style: marcato for the Bat King, staccato and an
octave down for the Tree, with an echo above for the Wind, wobbling for the
Jelly, in 3/4 and sparser for the Owl (a waltz).

As the boss loses health (steps 0-3: above 66%, 33%, 10%, below), the world's
melody comes back over the boss's loop, louder each step, in the boss's mode:
the world fighting back.
"""

import numpy as np

from src.services.music import sampler, score
from src.services.music.instruments import BIRD_INSTRUMENT, SAMPLE_RATE

SR = SAMPLE_RATE

BOSSES = {
    'normal': {
        'name': 'The Bat King',
        'tempo': 0.95,
        'meter': 4,
        'chords': ['Cm', 'Cm', 'Ab', 'G', 'Cm', 'Cm', 'Fm', 'G', 'Ab', 'Fm', 'Cm', 'G', 'Cm', 'Ab', 'G', 'Cm'],
        'lead': 'church_organ',
        'melody': '''
            C5:1 C5:.5 D5:.5 Eb5:1.5 D5:.5 | C5:1 G4:1 C5:1 Eb5:1 | Ab5:1.5 G5:.5 F5:1 Eb5:1 | D5:2 G4:2 |
            C5:1 C5:.5 D5:.5 Eb5:1.5 F5:.5 | G5:1 Eb5:1 C5:1 G5:1 | Ab5:1 G5:.5 F5:.5 Eb5:1 C5:1 | D5:3 r:1 |
            Eb5:1.5 F5:.5 G5:1 Ab5:1 | F5:1.5 Eb5:.5 C5:2 | G5:1 F5:.5 Eb5:.5 D5:1 C5:1 | B4:2 D5:2 |
            C5:1 C5:.5 D5:.5 Eb5:1.5 D5:.5 | C5:1 Eb5:1 Ab5:1 G5:1 | F5:.5 Eb5:.5 D5:.5 C5:.5 B4:1 D5:1 | C5:3 r:1''',
        'bass': 'tuba',
        'bass_pattern': [(i * 0.5, 0.5, d) for i, d in enumerate([0, 0, 2, 0, 1, 0, 2, 0])],
        'pad': 'choir',
        'drums': [(0, 36), (1, 38), (2, 36), (2.5, 36), (3, 38), (0, 45)],
        'timpani': True,
        'style': 'marcato',
    },
    'tree': {
        'name': 'The Old Tree',
        'tempo': 0.75,
        'meter': 4,
        'chords': ['Cm', 'Cm', 'Bb', 'Bb', 'Ab', 'Ab', 'G', 'G', 'Cm', 'Eb', 'Bb', 'F', 'Ab', 'G', 'Cm', 'Cm'],
        'lead': 'cello',
        'melody': '''
            C3:2 Eb3:1 F3:1 | G3:3 F3:1 | Bb2:2 D3:1 F3:1 | Bb3:3 r:1 | Ab3:1.5 G3:.5 F3:1 Eb3:1 | C3:3 r:1 |
            D3:1 F3:1 G3:1 B3:1 | G3:4 | C4:2 Bb3:1 G3:1 | Eb3:2 G3:2 | F3:1.5 Eb3:.5 D3:1 Bb2:1 | F3:3 r:1 |
            Ab3:1 G3:1 F3:1 Eb3:1 | D3:1 Eb3:1 F3:1 B2:1 | C3:4 | r:4''',
        'bass': 'bassoon',
        'bass_pattern': [(0, 1, 0), (1.5, 0.5, 0), (2, 1, 1), (3, 1, 2)],
        'pad': 'strings',
        'drums': [(0, 36), (0, 45), (2, 45), (3, 45), (3.5, 45)],
        'timpani': True,
        'style': 'staccato',
    },
    'wind': {
        'name': 'The Gale',
        'tempo': 1.15,
        'meter': 4,
        'chords': ['Cm', 'Ab', 'Bb', 'G', 'Cm', 'Ab', 'Fm', 'G', 'Ab', 'Bb', 'Cm', 'G', 'Ab', 'Bb', 'G', 'Cm'],
        'lead': 'piccolo',
        'melody': '''
            C6:.25 D6:.25 Eb6:.25 F6:.25 G6:1 Eb6:.5 C6:.5 G5:1 |
            Ab5:.25 Bb5:.25 C6:.25 D6:.25 Eb6:1 C6:.5 Ab5:.5 Eb5:1 |
            Bb5:.25 C6:.25 D6:.25 Eb6:.25 F6:1 D6:.5 Bb5:.5 F5:1 | G5:.5 B5:.5 D6:.5 F6:.5 G6:2 |
            C6:.25 D6:.25 Eb6:.25 F6:.25 G6:1 Eb6:.5 C6:.5 G5:1 |
            Ab5:.25 Bb5:.25 C6:.25 D6:.25 Eb6:1 C6:.5 Ab5:.5 Eb5:1 |
            F5:.25 G5:.25 Ab5:.25 C6:.25 F6:1 Eb6:.5 D6:.5 C6:1 | B5:.5 D6:.5 G6:1 F6:.5 D6:.5 B5:1 |
            Eb6:1 C6:.5 Ab5:.5 Eb6:1 Ab6:1 | F6:1 D6:.5 Bb5:.5 F6:1 Bb6:1 |
            G6:.5 F6:.5 Eb6:.5 D6:.5 C6:1 G5:1 | B5:2 D6:1 r:1 |
            C6:.25 Eb6:.25 Ab6:.25 C7:.25 Ab6:1 Eb6:1 C6:1 | D6:.25 F6:.25 Bb6:.25 D7:.25 Bb6:1 F6:1 D6:1 |
            G5:.25 B5:.25 D6:.25 F6:.25 G6:.5 F6:.5 D6:.5 B5:.5 G5:1 | C6:3 r:1''',
        'bass': 'cello',
        'bass_pattern': [(i * 0.5, 0.5, d) for i, d in enumerate([0, 2, 3, 2, 0, 2, 1, 2])],
        'pad': 'choir',
        'drums': [(0, 36), (1, 38), (2, 36), (3, 38)] + [(i / 2, 42) for i in range(8)],
        'style': 'swirl',
    },
    'jelly': {
        'name': 'The Jelly',
        'tempo': 0.9,
        'meter': 4,
        'chords': ['Cm', 'Db', 'Cm', 'Db', 'Fm', 'Gb', 'Fm', 'G', 'Cm', 'Db', 'Ab', 'G', 'Cm', 'Db', 'G', 'Cm'],
        'lead': 'vibraphone',
        'melody': '''
            C5:1 Db5:.5 C5:.5 B4:1 C5:1 | Db5:1 F5:.5 Ab5:.5 F5:1 Db5:1 | Eb5:1 D5:.5 Eb5:.5 G5:1 Eb5:1 |
            F5:1.5 E5:.5 F5:1 Ab4:1 | Ab4:1 C5:.5 F5:.5 E5:1 F5:1 | Gb4:1 Bb4:.5 Db5:.5 C5:1 Db5:1 |
            C5:.5 B4:.5 C5:.5 Db5:.5 C5:1 Ab4:1 | G4:1 B4:1 D5:1 F5:1 |
            C5:1 Db5:.5 C5:.5 B4:1 C5:1 | Db5:1 F5:.5 Ab5:.5 F5:1 Db5:1 | Eb5:1 C5:.5 Ab4:.5 C5:1 Eb5:1 |
            D5:1.5 C#5:.5 D5:1 B4:1 | C5:.5 Eb5:.5 G5:.5 Gb5:.5 F5:1 Eb5:1 | Db5:2 F5:1 Db5:1 | B4:1 D5:1 G4:1 B4:1 |
            C5:3 r:1''',
        'bass': 'synth_bass',
        'bass_pattern': [(0, 0.5, 0), (0.75, 0.25, 0), (1.5, 0.5, 2), (2.5, 0.5, 0), (3, 0.5, 1)],
        'pad': 'strings',
        'drums': [(0, 36), (1.5, 36), (1, 38), (3, 38), (2.5, 70), (3.5, 70)],
        'style': 'wobble',
    },
    'owl': {
        'name': 'The Night Owl',
        'tempo': 0.8,
        'meter': 3,
        'chords': ['Cm', 'Cm', 'Ab', 'Ab', 'Fm', 'Fm', 'G', 'G', 'Cm', 'Cm', 'Ab', 'Eb', 'Fm', 'G', 'Cm', 'Cm'],
        'lead': 'ocarina',
        'melody': '''
            G5:2 Eb5:1 | C5:3 | Eb5:1.5 D5:.5 C5:1 | Ab4:3 | F5:2 Eb5:1 | C5:2 Ab4:1 | B4:1.5 C5:.5 D5:1 | G4:3 |
            G5:2 Eb5:1 | C6:2 G5:1 | Ab5:1.5 G5:.5 F5:1 | Eb5:3 | F5:1 Eb5:1 C5:1 | D5:1.5 Eb5:.5 B4:1 | C5:3 | r:3''',
        'bass': 'bassoon',
        'bass_pattern': [(0, 1.5, 0), (1.5, 1.5, 2)],
        'pad': 'choir',
        'drums': [(0, 36), (1.5, 70), (2, 70)],
        'style': 'waltz',
    },
}

# The tonic of each world, from C: the boss plays its theme there
WORLD_TONIC = {1: 0, 2: -3, 3: -1, 4: 4, 5: 2, 6: -3}
LEAD_GAIN = 1.0
BASS_GAIN = 0.7
PAD_GAIN = 0.5
DRUM_GAIN = 0.55
PART_GAIN = 0.75
HERO_GAIN = (0.0, 0.35, 0.7, 1.0)  # the world's melody, by health step
LEAD_CUT = (1.0, 0.85, 0.65, 0.45)  # the boss's lead, by health step
BRIDGE_BARS = 8

_NAMES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']


def kind(boss_type):
    return boss_type if boss_type in BOSSES else 'normal'


def health_step(fraction):
    """0 above 66% of the boss's health, 1 above 33%, 2 above 10%, 3 below."""
    return 0 if fraction > 0.66 else 1 if fraction > 0.33 else 2 if fraction > 0.10 else 3


def _shift_chord(name, semis):
    root = score._PC[name[0]]
    rest = name[1:]
    if rest.startswith('#'):
        root, rest = root + 1, rest[1:]
    elif rest.startswith('b'):
        root, rest = root - 1, rest[1:]
    return _NAMES[(root + semis) % 12] + rest


def _tonic(world):
    return WORLD_TONIC.get(max(1, min(6, world)), 0)


def harmony(boss_type, world):
    """The boss as a 'world' of score.py: its chords on the world's tonic (the parts play on them)."""
    b = BOSSES[kind(boss_type)]
    return {'chords': [_shift_chord(c, _tonic(world)) for c in b['chords']]}


def beats(boss_type):
    return score.BARS * BOSSES[kind(boss_type)]['meter']


def bpm(boss_type, world, speed):
    return score.world(world)['bpm'] * BOSSES[kind(boss_type)]['tempo'] * score.SPEED_TEMPO[speed]


def _to_meter(events, meter):
    """Parts are written in bars of 4: squeeze each bar into ``meter`` beats."""
    if meter == 4:
        return events
    k = meter / 4
    return [(st * k, du * k, ns, v) for st, du, ns, v in events]


def dress(events, boss_type):
    """A part in the boss's style."""
    style = BOSSES[kind(boss_type)]['style']
    if style == 'marcato':  # short and heavy, an accent on the beat
        return [(st, du * 0.55, ns, min(127, v + (14 if st % 1 == 0 else -6))) for st, du, ns, v in events]
    if style == 'staccato':  # short, low, on the beats only
        out = []
        for st, du, ns, v in events:
            if st % 1:
                continue
            out.append((st, min(du, 1.0) * 0.45, [n - 12 if n >= 67 else n for n in ns], min(127, v + 6)))
        return out
    if style == 'swirl':  # each note blown up an octave a moment later
        out = []
        for st, du, ns, v in events:
            out.append((st, du * 0.7, ns, v))
            up = [n + 12 for n in ns if n + 12 <= 96]  # not out of the high instruments' range
            if up:
                out.append((st + 0.25, du * 0.5, up, max(30, v - 28)))
        return out
    if style == 'wobble':  # held and soft (the audio wobbles too, see _wobble)
        return [(st, du * 1.25, ns, v - 6) for st, du, ns, v in events]
    if style == 'waltz':  # sparser, in 3, held
        thin = [e for i, e in enumerate(events) if e[0] % 1 == 0 or i % 3 == 0]
        return _to_meter([(st, du * 1.3, ns, v - 8) for st, du, ns, v in thin], 3)
    return events


def _wobble(audio):
    """Pitch that wobbles slowly, like jelly (mono)."""
    n = len(audio)
    t = np.arange(n) / SR
    pos = np.minimum(np.cumsum(1 + 0.012 * np.sin(2 * np.pi * 1.6 * t)), n - 2)
    return np.interp(pos, np.arange(n), audio).astype(np.float32)


def _bass(boss_type, chords, octave=2):
    b = BOSSES[kind(boss_type)]
    meter = b['meter']
    return [
        (bar * meter + st, du, [score.tone(chord, d, octave)], 92)
        for bar, chord in enumerate(chords)
        for st, du, d in b['bass_pattern']
    ]


def _hero(boss_type, world):
    """The world's melody in the boss's mode (its 3rd and 6th flattened) and meter."""
    tonic = _tonic(world) % 12
    out = []
    for st, du, ns, v in score.theme(world):
        out.append((st, du, [n - 1 if (n - tonic) % 12 in (4, 9) else n for n in ns], v))
    return _to_meter(out, BOSSES[kind(boss_type)]['meter'])


def layers(boss_type, world, counts, bats, speed, quantity_step, instrument_for):
    """[(key, instrument, events, gain, post)] of the boss's loop: its band, then the flock dressed.
    ``post``: an effect on the rendered audio, or None."""
    k = kind(boss_type)
    b = BOSSES[k]
    w = harmony(k, world)
    t = _tonic(world)
    meter = b['meter']
    lead = [(st, du, [n + t for n in ns], v) for st, du, ns, v in score.melody(b['melody'])]
    pad = [(bar * meter, meter, [score.tone(c, d, 3) for d in (0, 1, 2)], 58) for bar, c in enumerate(w['chords'])]
    drums = [
        (bar * meter + st, 0.5, [h], 96 if h in (36, 45) else 62) for bar in range(score.BARS) for st, h in b['drums']
    ]
    out = [
        (('boss_lead', k, world, speed), b['lead'], lead, LEAD_GAIN, None),
        (('boss_bass', k, world, speed), b['bass'], _bass(k, w['chords']), BASS_GAIN, None),
        (('boss_pad', k, world, speed), b['pad'], pad, PAD_GAIN, None),
        (('boss_drums', k, world, speed), 'drums', drums, DRUM_GAIN, None),
    ]
    if b.get('timpani'):
        roll = [
            (bar * meter + meter - 1 + i / 4, 0.25, [score.tone(c, 0, 2)], 70 + i * 8)
            for bar, c in enumerate(w['chords'])
            if bar % 4 == 3
            for i in range(4)
        ]
        out.append((('boss_timpani', k, world, speed), 'timpani', roll, 0.7, None))
    post = _wobble if b['style'] == 'wobble' else None
    for bird in sorted(counts):
        q = quantity_step(counts[bird])
        if q and bird in score.PARTS and bird in BIRD_INSTRUMENT:
            events = dress(score.PARTS[bird](w, 1 if bird in score.SOLO else q, speed), k)
            out.append(((bird, 'boss', k, world, q, speed), instrument_for(bird, q), events, PART_GAIN, post))
    q = quantity_step(bats, 'BATS')
    if q:
        events = dress(score.PARTS['BATS'](w, q, speed), k)
        out.append((('BATS', 'boss', k, world, q, speed), 'tremolo', events, PART_GAIN, post))
    return out


def hero_layer(boss_type, world, speed):
    k = kind(boss_type)
    return (('boss_hero', k, world, speed), score.world(world)['instrument'], _hero(k, world))


# --------------------------------------------------------------------------- the corruption


def _warp(stereo, depth):
    """Pitch that wobbles and sags; ``depth`` (0..1 per sample) sets how much."""
    n = len(stereo)
    t = np.arange(n) / SR
    rate = 1 + depth * (0.035 * np.sin(2 * np.pi * 0.9 * t) + 0.02 * np.sin(2 * np.pi * 5.3 * t)) - depth * 0.03
    pos = np.minimum(np.cumsum(rate), n - 2)
    grid = np.arange(n)
    return np.stack([np.interp(pos, grid, stereo[:, c]) for c in (0, 1)], axis=1)


def _lowpass(stereo, cutoff):
    spec = np.fft.rfft(stereo, axis=0)
    freqs = np.fft.rfftfreq(len(stereo), 1 / SR)
    spec *= (1 / np.sqrt(1 + (freqs / cutoff) ** 4))[:, None]
    return np.fft.irfft(spec, len(stereo), axis=0)


def _crush(stereo, hold=6, drive=3.0):
    held = np.repeat(stereo[::hold], hold, axis=0)[: len(stereo)]
    return np.tanh(held * drive) / np.tanh(drive)


def corrupt(stereo, amount):
    """``amount`` 0..1 per sample: the music warped, muffled, dirtied and pushed away."""
    a = amount[:, None]
    wobbly = _warp(stereo, amount)
    dark = _lowpass(wobbly, 700)
    out = wobbly * (1 - a) + (dark * 0.6 + _crush(dark) * 0.4) * a
    return out * (1 - 0.75 * a)


def bridge(world_loop, boss_type, world, world_bpm):
    """The corruption (stereo float32): ``world_loop`` (the world's music, stereo) for 8 bars at
    ``world_bpm``, corrupted, with the boss's bass creeping in and its lead taking over."""
    k = kind(boss_type)
    b = BOSSES[k]
    t = _tonic(world)
    bar = int(4 * 60 / world_bpm * SR)
    n = BRIDGE_BARS * bar
    half = n // 2
    head = np.tile(world_loop, (int(np.ceil(n / len(world_loop))), 1))[:n]
    amount = np.concatenate([np.linspace(0, 0.45, half) ** 1.3, np.linspace(0.45, 1.0, n - half)])
    head = corrupt(head, amount)
    tonic_chord = _shift_chord(b['chords'][0], t)
    k_beats = BRIDGE_BARS * 4
    pedal = [
        (bar_i * 4 + st, du, [score.tone(tonic_chord, d, 2)], 90)
        for bar_i in range(BRIDGE_BARS)
        for st, du, d in b['bass_pattern']
        if st < 4
    ]
    lead = [(st + k_beats / 2, du, [x + t for x in ns], v) for st, du, ns, v in score.melody(b['melody'])[:10]]
    lead = [e for e in lead if e[0] < k_beats]
    pulse = [(i * 2, 1, [45], 70 + i * 3) for i in range(BRIDGE_BARS * 2)]
    bass_audio = sampler.render_part(pedal, b['bass'], world_bpm, k_beats)[:n]
    lead_audio = sampler.render_part(lead, b['lead'], world_bpm, k_beats)[:n]
    pulse_audio = sampler.render_part(pulse, 'drums', world_bpm, k_beats)[:n]
    ramp = (np.linspace(0.1, 1.0, n) ** 1.5).astype(np.float32)
    rise = np.clip(np.linspace(-1, 1.2, n), 0, 1).astype(np.float32)
    boss_in = sampler.mix(
        [
            (bass_audio * ramp, BASS_GAIN * 1.2, -0.1),
            (pulse_audio * ramp, 0.5, 0.0),
            (lead_audio * rise, LEAD_GAIN, 0.0),
        ],
        wet=0.18,
    )
    return np.tanh(head + boss_in[:n]).astype(np.float32)
