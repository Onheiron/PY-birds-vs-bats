"""The score: what every part plays, world by world.

Each world has a theme (a melody of 16 bars for its own instrument), a key, a
chord for every bar and a tempo. Every bird type plays a part on those chords
with its instrument (instruments.BIRD_INSTRUMENT), so any set of birds sounds
together. A part has 3 x 3 versions:

- quantity step q: 1 bird of the type, 2-3, 4 or more (more voices, fuller);
- speed step s: gears 1-3, 4-6, 7-10 (the tempo, and a calmer or more driving
  rhythm).

The bats have a part too (dissonant tremolo strings, by how many are on
screen), and every world a drum part by speed step.

A part is a list of notes: (start beat, length in beats, MIDI notes, velocity),
over the 64 beats of the loop.
"""

import random

BARS = 16
BEATS = BARS * 4
SPEED_TEMPO = {1: 0.92, 2: 1.08, 3: 1.26}  # tempo factor of each speed step

_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def note(name):
    """'C#5' -> 73."""
    pitch = _PC[name[0]]
    rest = name[1:]
    while rest and rest[0] in '#b':
        pitch += 1 if rest[0] == '#' else -1
        rest = rest[1:]
    return pitch + 12 * (int(rest) + 1)


def melody(text):
    """'G4:.5 C5:.5 r:1 | ...' -> notes."""
    out, t = [], 0.0
    for token in text.replace('|', ' ').split():
        name, length = token.split(':')
        length = float(length)
        if name != 'r':
            out.append((t, length, [note(name)], 96))
        t += length
    return out


def chord_pcs(name):
    """'Am' -> pitch classes of root, third, fifth."""
    root = _PC[name[0]]
    rest = name[1:]
    if rest.startswith('#'):
        root, rest = root + 1, rest[1:]
    elif rest.startswith('b'):
        root, rest = root - 1, rest[1:]
    third, fifth = (3, 7) if rest == 'm' else (3, 6) if rest == 'dim' else (4, 8) if rest == 'aug' else (4, 7)
    return [root % 12, (root + third) % 12, (root + fifth) % 12]


def tone(chord, degree, octave):
    """Degree 0/1/2 (root/third/fifth, 3+ an octave up) of ``chord``, from the root in ``octave``."""
    pcs = chord_pcs(chord)
    root = 12 * (octave + 1) + pcs[0]
    pitch = 12 * (octave + 1) + pcs[degree % 3]
    if pitch < root:
        pitch += 12
    return pitch + 12 * (degree // 3)


# --------------------------------------------------------------------------- the worlds

WORLDS = {
    1: {
        'name': 'Windy Woods',
        'instrument': 'flute',
        'bpm': 100,
        'chords': ['C', 'C', 'Am', 'G', 'C', 'Am', 'G', 'C', 'F', 'C', 'Dm', 'C', 'C', 'Am', 'G', 'C'],
        'melody': '''
            G4:.5 C5:.5 E5:1 D5:.5 C5:.5 D5:1 | E5:1.5 G5:.5 A5:1 G5:1 | E5:.5 D5:.5 C5:1 A4:1 C5:1 | D5:3 r:1 |
            G4:.5 C5:.5 E5:1 D5:.5 C5:.5 D5:1 | E5:1.5 G5:.5 C6:1 B5:.5 A5:.5 | G5:1 E5:.5 F5:.5 D5:1 B4:1 | C5:3 r:1 |
            A5:1 G5:.5 F5:.5 E5:1 F5:1 | G5:1.5 E5:.5 C5:2 | F5:1 E5:.5 D5:.5 C5:1 D5:1 | E5:2 G4:1 r:1 |
            G4:.5 C5:.5 E5:1 D5:.5 C5:.5 D5:1 | E5:1.5 G5:.5 C6:1 B5:.5 A5:.5 |
            G5:.5 A5:.5 G5:.5 E5:.5 D5:1 E5:.5 D5:.5 | C5:3 r:1''',
        'drums': 'light',
    },
    2: {
        'name': 'The Borders',
        'instrument': 'alto_sax',
        'bpm': 92,
        'chords': ['E', 'Am', 'E', 'E', 'E', 'Am', 'Bdim', 'Am', 'Caug', 'Dm', 'E', 'E', 'E', 'Am', 'E', 'Am'],
        'melody': '''
            r:.5 E4:.5 G#4:.5 A4:.5 B4:1 G#4:1 | A4:.5 G#4:.5 E4:1 C4:1.5 r:.5 |
            r:.5 E4:.5 G#4:.5 B4:.5 C5:1 B4:.5 A4:.5 | G#4:3 r:1 |
            r:.5 E4:.5 G#4:.5 A4:.5 B4:1 D5:1 | C5:.5 B4:.5 G#4:1 A4:1.5 r:.5 |
            F4:.5 G#4:.5 B4:.5 D5:.5 C5:.75 B4:.25 G#4:1 | A4:3 r:1 |
            C5:1.5 B4:.5 G#4:1 E4:1 | F4:1.5 E4:.5 D4:1 E4:1 | G#4:.5 A4:.5 B4:.5 C5:.5 D5:1 E5:1 |
            D5:.5 C5:.5 B4:.5 G#4:.5 E4:2 |
            r:.5 E4:.5 G#4:.5 A4:.5 B4:1 G#4:1 | A4:.5 G#4:.5 E4:1 C4:1.5 r:.5 |
            E5:.5 D5:.5 C5:.5 B4:.5 G#4:1 B4:1 | A4:3 r:1''',
        'drums': 'sneaky',
    },
    3: {
        'name': 'Rotten Marshes',
        'instrument': 'harpsichord',
        'bpm': 84,
        'chords': ['Bdim', 'G', 'C', 'F', 'Bdim', 'G', 'Dm', 'Bdim', 'G', 'Dm', 'Em', 'F', 'Bdim', 'G', 'Dm', 'Bdim'],
        'melody': '''
            B3:.5 D4:.5 F4:.5 D4:.5 B3:.5 D4:.5 F4:.5 A4:.5 | G4:.5 F4:.5 E4:.5 D4:.5 C4:1 B3:1 |
            C4:.5 E4:.5 G4:.5 E4:.5 C4:.5 E4:.5 G4:.5 B4:.5 | A4:.5 G4:.5 F4:.5 E4:.5 F4:2 |
            B3:.5 D4:.5 F4:.5 D4:.5 B3:.5 D4:.5 F4:.5 A4:.5 | G4:.5 A4:.5 B4:.5 C5:.5 D5:1 C5:1 |
            B4:.25 C5:.25 B4:.25 A4:.25 G4:.5 F4:.5 E4:.5 F4:.5 D4:1 | B3:3 r:1 |
            D5:1 C5:.5 B4:.5 A4:1 G4:1 | F4:.5 G4:.5 A4:.5 F4:.5 D4:2 | E4:.5 F4:.5 G4:.5 A4:.5 B4:.5 C5:.5 D5:1 |
            C5:.5 B4:.5 A4:.5 G4:.5 F4:2 |
            B3:.5 D4:.5 F4:.5 D4:.5 B3:.5 D4:.5 F4:.5 A4:.5 | G4:.5 F4:.5 E4:.5 D4:.5 C4:1 B3:1 |
            F4:.5 E4:.5 D4:.5 C4:.5 D4:.5 E4:.5 F4:1 | B3:3 r:1''',
        'drums': 'shaker',
    },
    4: {
        'name': 'The Dark Swamp',
        'instrument': 'finger_bass',
        'bpm': 76,
        'chords': ['Em', 'Em', 'Am', 'F', 'Em', 'Em', 'F', 'Em', 'C', 'F', 'Em', 'F', 'Em', 'Em', 'Dm', 'Em'],
        'melody': '''
            E2:1 E2:.5 F2:.5 E2:1 r:.5 B1:.5 | E2:1 E2:.5 G2:.5 F2:1 E2:1 | A2:1 A2:.5 B2:.5 C3:1 B2:.5 A2:.5 |
            G2:.5 F2:.5 E2:1 F2:2 |
            E2:1 E2:.5 F2:.5 E2:1 r:.5 B1:.5 | E2:1 E2:.5 G2:.5 F2:1 E2:1 | C3:1 B2:.5 A2:.5 G2:.5 A2:.5 F2:1 |
            E2:3 r:1 |
            E3:1.5 D3:.5 C3:1 B2:1 | C3:1 B2:.5 A2:.5 G2:1 F2:1 | E2:.5 F2:.5 G2:.5 A2:.5 B2:.5 C3:.5 D3:1 |
            F3:2 E3:2 |
            E2:1 E2:.5 F2:.5 E2:1 r:.5 B1:.5 | E2:1 E2:.5 G2:.5 F2:1 E2:1 | F2:.5 G2:.5 F2:.5 E2:.5 D2:1 F2:1 |
            E2:3 r:1''',
        'drums': 'ritual',
    },
    5: {
        'name': 'The Void Cave',
        'instrument': 'overdrive_guitar',
        'bpm': 120,
        'chords': ['Dm', 'F', 'Dm', 'Am', 'Dm', 'F', 'Dm', 'Dm', 'G', 'C', 'Dm', 'Am', 'Dm', 'F', 'C', 'Dm'],
        'melody': '''
            D4:.5 D4:.5 A4:1 G4:.5 F4:.5 E4:1 | F4:.5 G4:.5 A4:1 C5:1 B4:1 | A4:.5 A4:.5 D5:1 C5:.5 B4:.5 A4:1 |
            G4:.5 A4:.5 F4:1 E4:2 |
            D4:.5 D4:.5 A4:1 G4:.5 F4:.5 E4:1 | F4:.5 G4:.5 A4:1 C5:.5 D5:.5 E5:1 | F5:1 E5:.5 D5:.5 C5:1 A4:1 |
            D5:3 r:1 |
            B4:1.5 A4:.5 G4:1 B4:1 | C5:1.5 B4:.5 A4:1 C5:1 | D5:.5 E5:.5 F5:.5 E5:.5 D5:.5 C5:.5 B4:.5 C5:.5 | A4:4 |
            D4:.5 D4:.5 A4:1 G4:.5 F4:.5 E4:1 | F4:.5 G4:.5 A4:1 C5:.5 D5:.5 E5:1 |
            F5:.5 E5:.5 D5:.5 C5:.5 B4:.5 A4:.5 G4:.5 E4:.5 | D4:3 r:1''',
        'drums': 'rock',
    },
    6: {
        'name': 'Mountain Range',
        'instrument': 'violin',
        'bpm': 72,
        'chords': ['Am', 'Am', 'G', 'Am', 'C', 'F', 'E', 'Am', 'Am', 'F', 'G', 'E', 'Am', 'Am', 'E', 'Am'],
        'melody': '''
            E5:1.5 D5:.5 C5:1 B4:1 | A4:1.5 B4:.5 C5:1 E5:1 | D5:1.5 C5:.5 B4:1 G4:1 | A4:3 r:1 |
            E5:1.5 F5:.5 G5:1 E5:1 | F5:1.5 E5:.5 D5:1 C5:1 | B4:1 C5:.5 D5:.5 E5:1 G#4:1 | A4:3 r:1 |
            C5:1 E5:1 A5:1.5 G5:.5 | F5:1 E5:1 D5:2 | G5:1 F5:.5 E5:.5 D5:1 C5:1 | B4:2 E5:2 |
            E5:1.5 D5:.5 C5:1 B4:1 | A4:1.5 B4:.5 C5:1 E5:1 | D5:1 C5:.5 B4:.5 C5:1 B4:.5 G#4:.5 | A4:4''',
        'drums': 'soft',
    },
}


def world(number):
    return WORLDS[max(1, min(6, number))]


def bpm(number, speed):
    return world(number)['bpm'] * SPEED_TEMPO[speed]


# --------------------------------------------------------------------------- the parts


def _each_bar(w, fn):
    out = []
    for bar, chord in enumerate(w['chords']):
        nxt = w['chords'][(bar + 1) % BARS]
        for start, length, notes, vel in fn(bar, chord, nxt):
            out.append((bar * 4 + start, length, notes if isinstance(notes, list) else [notes], vel))
    return out


def _thin(pattern, s):
    """Speed step 1 plays every other note, twice as long; 3 adds pick-ups."""
    if s == 1:
        return [(st, du * 2, d) for i, (st, du, d) in enumerate(pattern) if i % 2 == 0]
    return pattern


def yellow(w, q, s):
    """Marimba: bouncing arpeggios (2 marimbas with 4+ Yellows)."""

    def bar(_b, ch, _n):
        if q == 1:
            pattern = [(0, 1, 0), (1, 1, 1), (2, 1, 2), (3, 1, 1)]
        else:
            pattern = [(i * 0.5, 0.5, d) for i, d in enumerate([0, 2, 1, 2, 3, 2, 1, 2])]
        pattern = _thin(pattern, s)
        if s == 3:
            pattern = pattern + [(1.75, 0.25, 4), (3.75, 0.25, 4)]
        for st, du, d in pattern:
            yield st, du, tone(ch, d, 4), 84 if st % 2 == 0 else 70
            if q == 3:
                yield st, du, tone(ch, (d + 2) % 3, 5), 60

    return _each_bar(w, bar)


def red(w, q, s):
    """Trumpet, then brass: stabs, then chords and fanfares into each phrase."""

    def bar(b, ch, nxt):
        if q == 1:
            hits = [(0, 1)] if s == 1 else [(0, 0.75), (2, 0.75)]
            for st, du in hits:
                yield st, du, tone(ch, 2, 4), 92
            if s == 3:
                yield 3.5, 0.5, tone(ch, 0, 5), 80
            return
        hits = [(0, 1.5), (2, 1.5)] if s == 1 else [(0, 0.5), (1.5, 0.5), (3, 0.5)]
        if s == 3:
            hits = [(0, 0.5), (0.75, 0.25), (1.5, 0.5), (2.5, 0.5), (3, 0.5)]
        voices = [1, 2] if q == 2 else [0, 1, 2]
        for st, du in hits:
            yield st, du, [tone(ch, v, 4) for v in voices], 90
        if q == 3 and b % 4 == 3:
            for i, d in enumerate([0, 1, 2]):
                yield 3 + i / 3, 1 / 3, tone(nxt, d, 4), 96

    return _each_bar(w, bar)


def blue(w, q, s):
    """Clarinet: guide tones, a countermelody, then two clarinets."""

    def bar(_b, ch, _n):
        if q == 1 or s == 1:
            line = [(0, 2, 1), (2, 2, 2)] if q > 1 or s > 1 else [(0, 4, 1)]
        elif s == 2:
            line = [(0, 1, 1), (1, 1, 2), (2, 1.5, 1), (3.5, 0.5, 0)]
        else:
            line = [(0, 0.5, 1), (0.5, 0.5, 2), (1, 1, 1), (2, 0.5, 0), (2.5, 0.5, 1), (3, 1, 2)]
        for st, du, d in line:
            yield st, du, tone(ch, d, 3) + (12 if d == 0 else 0), 80
            if q == 3:
                yield st, du, tone(ch, d - 1 if d else 2, 3), 64

    return _each_bar(w, bar)


def purple(w, q, s):
    """Horn: long swelling notes (it charges its shot)."""

    def bar(_b, ch, _n):
        voices = [1] if q == 1 else [0, 2] if q == 2 else [0, 1, 2]
        if s == 3:
            for beat in range(4):
                yield beat, 0.9, [tone(ch, v, 3) for v in voices], 70 + 8 * (beat == 0)
        else:
            yield 0, 4 if s == 1 else 2, [tone(ch, v, 3) for v in voices], 72
            if s == 2:
                yield 2, 2, [tone(ch, v, 3) for v in voices], 66

    return _each_bar(w, bar)


def white(w, q, s):
    """Celesta: bright accents (one White at a time)."""

    def bar(b, ch, _n):
        if s == 1 and b % 2:
            return
        yield 0, 1, tone(ch, 2, 5), 80
        if s >= 2:
            yield 2.5, 0.5, tone(ch, 1, 6), 66
        if s == 3:
            yield 3.5, 0.5, tone(ch, 0, 6), 62

    return _each_bar(w, bar)


def gold(w, q, s):
    """Glockenspiel: a sparkle up the chord at the end of a bar."""

    def bar(b, ch, _n):
        if s == 1 and b % 2 == 0:
            return
        step = 0.25 if s == 3 else 1 / 3
        start = 4 - 4 * step
        for i, d in enumerate([0, 1, 2, 3]):
            yield start + i * step, step, tone(ch, d, 6), 70

    return _each_bar(w, bar)


def orange(w, q, s):
    """Trombones: power fifths (the Phoenix)."""

    def bar(_b, ch, _n):
        hits = [(0, 2)] if s == 1 else [(0, 1), (2, 1)] if s == 2 else [(0, 0.75), (1.5, 0.5), (2, 0.75), (3.5, 0.5)]
        for st, du in hits:
            yield st, du, [tone(ch, 0, 3), tone(ch, 2, 3)], 92

    return _each_bar(w, bar)


def patchwork(w, q, s):
    """Accordion: oom-pah, fuller with more Patchworks."""

    def bar(_b, ch, _n):
        offbeats = [1, 3] if s < 3 else [0.5, 1, 1.5, 2.5, 3, 3.5]
        if s == 1:
            offbeats = [1.5, 3.5]
        for st in offbeats:
            yield st, 0.4, [tone(ch, d, 4) for d in ([1, 2] if q == 1 else [0, 1, 2])], 70
        if q >= 2:
            yield 0, 0.9, tone(ch, 0, 3), 78
            yield 2, 0.9, tone(ch, 2, 2) if q == 3 else tone(ch, 0, 3), 74

    return _each_bar(w, bar)


def cookie(w, q, s):
    """Pizzicato strings: light offbeats."""

    def bar(_b, ch, _n):
        starts = [1, 3] if s == 1 else [0.5, 1.5, 2.5, 3.5] if s == 2 else [i * 0.5 + 0.5 for i in range(7)]
        for i, st in enumerate(starts):
            yield st, 0.3, tone(ch, i % 3, 4), 78
            if q >= 2:
                yield st, 0.3, tone(ch, (i + 1) % 3, 3), 66
            if q == 3:
                yield st, 0.3, tone(ch, i % 3, 5), 58

    return _each_bar(w, bar)


def clockwork(w, q, s):
    """Music box: a ticking figure, high up."""

    def bar(_b, ch, _n):
        step = {1: 1, 2: 0.5, 3: 0.25}[s]
        degrees = [0, 2, 1, 2] if q == 1 else [0, 2, 3, 2, 1, 2, 3, 4]
        t, i = 0.0, 0
        while t < 4:
            yield t, step, tone(ch, degrees[i % len(degrees)], 5), 64 if i % 4 == 0 else 52
            t += step
            i += 1

    return _each_bar(w, bar)


def stealth(w, q, s):
    """Choir: soft held chords."""

    def bar(b, ch, _n):
        voices = [0, 1] if q == 1 else [0, 1, 2] if q == 2 else [0, 1, 2, 3]
        length = 4 if s < 3 else 2
        for st in range(0, 4, length):
            yield st, length, [tone(ch, v, 3) for v in voices], 60

    return _each_bar(w, bar)


def dinosaur(w, q, s):
    """Tuba: the bass line."""

    def bar(_b, ch, nxt):
        if s == 1:
            yield 0, 2, tone(ch, 0, 1), 90
            yield 2, 2, tone(ch, 2 if q > 1 else 0, 1), 82
            return
        line = [(0, 1, tone(ch, 0, 1)), (2, 1, tone(ch, 2, 1))]
        if q >= 2 or s == 3:
            line = [(0, 1, tone(ch, 0, 1)), (1, 1, tone(ch, 2, 1)), (2, 1, tone(ch, 0, 2)), (3, 1, tone(nxt, 0, 1) - 1)]
        for st, du, n in line:
            yield st, du * 0.9, n, 88

    return _each_bar(w, bar)


def glitch(w, q, s):
    """Square wave: chiptune chaos (random chord tones, fixed per world)."""
    rng = random.Random(1000 + w['bpm'])

    def bar(_b, ch, _n):
        step = {1: 1, 2: 0.5, 3: 0.25}[s]
        t = 0.0
        while t < 4:
            if rng.random() < 0.35 + 0.15 * q:
                yield t, step, tone(ch, rng.randrange(4), 4 + rng.randrange(2)), 70
            t += step

    return _each_bar(w, bar)


def twister(w, q, s):
    """Pan flute: the wind, gliding long notes."""

    def bar(b, ch, _n):
        length = 4 if s == 1 else 2 if s == 2 else 1
        for i, st in enumerate(range(0, 4, length)):
            d = [2, 1, 0, 1][(b + i) % 4] + 3
            yield st, length, tone(ch, d, 4), 70
            if q >= 2:
                yield st, length, tone(ch, d - 1, 4), 58

    return _each_bar(w, bar)


def frosty(w, q, s):
    """Harp: icy arpeggios up the chord."""

    def bar(_b, ch, _n):
        step = {1: 0.5, 2: 0.5, 3: 0.25}[s]
        count = {1: 4, 2: 8, 3: 8}[q] if s != 1 else 4
        for i in range(count):
            yield i * step, step * 2, tone(ch, i % 6, 3 + (q == 3)), 72

    return _each_bar(w, bar)


def poison(w, q, s):
    """Oboe: a slow, sour line (third, then a step away)."""

    def bar(b, ch, _n):
        third = tone(ch, 1, 4)
        if s == 1:
            yield 0, 3, third, 70
            yield 3, 1, third + (1 if b % 2 else -1), 64
        else:
            for i, st in enumerate([0, 1, 2, 3] if s == 2 else [0, 0.5, 1, 2, 2.5, 3]):
                yield st, 0.9 if s == 2 else 0.45, third + [0, 1, 0, -1, 0, 2][i % 6], 68
        if q >= 2:
            yield 0, 4, tone(ch, 2, 3), 54

    return _each_bar(w, bar)


def berserk(w, q, s):
    """Taiko: war drums."""

    def bar(_b, ch, _n):
        hits = {1: [0, 2], 2: [0, 1.5, 2, 3], 3: [0, 0.75, 1.5, 2, 2.5, 3, 3.5]}[s]
        for st in hits:
            yield st, 0.5, tone(ch, 0, 2), 100 if st == 0 else 80
            if q >= 2 and st in (0, 2):
                yield st, 0.5, tone(ch, 2, 2), 84

    return _each_bar(w, bar)


def rock(w, q, s):
    """Timpani: deep strokes on the root and the fifth."""

    def bar(b, ch, _n):
        if s == 1 and b % 2:
            return
        yield 0, 1, tone(ch, 0, 2), 96
        if s >= 2:
            yield 2, 1, tone(ch, 2, 2), 84
        if s == 3 or q == 3:
            yield 3.5, 0.25, tone(ch, 0, 2), 70
            yield 3.75, 0.25, tone(ch, 0, 2), 76

    return _each_bar(w, bar)


def rainbow(w, q, s):
    """String ensemble: the richest sound (the Rainbow is mythical)."""

    def bar(_b, ch, _n):
        voices = [tone(ch, 0, 3), tone(ch, 1, 3), tone(ch, 2, 3), tone(ch, 1, 4)]
        if s == 3:
            for st in (0, 1, 2, 3):
                yield st, 0.95, voices, 70
        else:
            yield 0, 4 if s == 1 else 2, voices, 72
            if s == 2:
                yield 2, 2, voices, 68

    return _each_bar(w, bar)


def zombie(w, q, s):
    """Bassoon: clumsy staccato offbeats."""

    def bar(_b, ch, _n):
        starts = [1, 3] if s == 1 else [0.5, 1.5, 2.5, 3.5]
        if s == 3:
            starts = starts + [3.75]
        for i, st in enumerate(starts):
            yield st, 0.35, tone(ch, [0, 2][i % 2], 2), 80
            if q >= 2:
                yield st, 0.35, tone(ch, 1, 2), 64

    return _each_bar(w, bar)


def bats(w, q, s):
    """Tremolo strings: a dissonant cluster, root and the semitone above (more bats, more tension)."""

    def bar(_b, ch, _n):
        root = tone(ch, 0, 3)
        voices = (
            [root, root + 1]
            if q == 1
            else [root, root + 1, root + 6]
            if q == 2
            else [root - 12, root, root + 1, root + 6]
        )
        length = 4 if s == 1 else 2
        for st in range(0, 4, length):
            yield st, length, voices, 56 + 8 * q

    return _each_bar(w, bar)


PARTS = {
    'YELLOW': yellow,
    'RED': red,
    'BLUE': blue,
    'PURPLE': purple,
    'WHITE': white,
    'GOLD': gold,
    'ORANGE': orange,
    'PATCHWORK': patchwork,
    'COOKIE': cookie,
    'CLOCKWORK': clockwork,
    'STEALTH': stealth,
    'DINOSAUR': dinosaur,
    'GLITCH': glitch,
    'TWISTER': twister,
    'FROSTY': frosty,
    'POISON': poison,
    'BERSERK': berserk,
    'ROCK': rock,
    'RAINBOW': rainbow,
    'ZOMBIE': zombie,
    'BATS': bats,
}

# Birds there is one of at a time: always their quantity step 1
SOLO = {'WHITE', 'GOLD', 'ORANGE', 'RAINBOW'}


def part(world_number, kind, q, s):
    """The notes of a bird type (or 'BATS') in a world, quantity step q and speed step s."""
    q = 1 if kind in SOLO else q
    return PARTS[kind](world(world_number), q, s)


def theme(world_number):
    return melody(world(world_number)['melody'])


# Drum hits: GM notes kick 36, snare 38, closed hat 42, open hat 46, crash 49, low tom 45, shaker 70
_DRUMS = {
    'light': {
        1: [(0, 36), (2, 36), (1, 42), (3, 42)],
        2: [(0, 36), (2, 36), (1, 38), (3, 38)] + [(i / 2, 42) for i in range(8)],
        3: [(0, 36), (1.5, 36), (2, 36), (1, 38), (3, 38)] + [(i / 4, 42) for i in range(16)],
    },
    'sneaky': {
        1: [(0, 36), (2.5, 36), (3, 42)],
        2: [(0, 36), (2.5, 36), (1, 38), (3, 38), (0.5, 42), (1.5, 42), (2.5, 42), (3.5, 42)],
        3: [(0, 36), (0.75, 36), (2.5, 36), (1, 38), (3, 38)]
        + [(i / 2 + 0.5, 42) for i in range(0, 8, 2)]
        + [(i / 4, 42) for i in range(16) if i % 4 == 3],
    },
    'shaker': {
        1: [(0, 45)] + [(i, 70) for i in range(4)],
        2: [(0, 45), (2, 45)] + [(i / 2, 70) for i in range(8)],
        3: [(0, 45), (1.5, 45), (2, 45), (3, 38)] + [(i / 4, 70) for i in range(16)],
    },
    'ritual': {
        1: [(0, 45), (2, 45)],
        2: [(0, 45), (1.5, 45), (2, 45), (3, 36)],
        3: [(0, 45), (0.75, 45), (1.5, 45), (2, 45), (3, 36), (3.5, 36)] + [(i, 42) for i in range(4)],
    },
    'rock': {
        1: [(0, 36), (2, 38), (1, 42), (3, 42)],
        2: [(0, 36), (1.5, 36), (1, 38), (3, 38)] + [(i / 2, 42) for i in range(8)],
        3: [(0, 36), (0.5, 36), (1.5, 36), (2, 36), (1, 38), (3, 38)]
        + [(i / 2, 46 if i % 2 else 42) for i in range(8)],
    },
    'soft': {
        1: [(0, 36)],
        2: [(0, 36), (2, 36), (3, 42)],
        3: [(0, 36), (2, 36), (1, 38), (3, 38)] + [(i / 2, 42) for i in range(8)],
    },
}


def drums(world_number, s):
    """The drum part of a world at speed step s (a crash opens every 4 bars from step 2)."""
    pattern = _DRUMS[world(world_number)['drums']][s]
    out = []
    for bar in range(BARS):
        for start, hit in pattern:
            vel = 90 if hit in (36, 38, 45) else 60
            out.append((bar * 4 + start, 0.5, [hit], vel))
        if s >= 2 and bar % 4 == 0:
            out.append((bar * 4, 1, [49], 70))
    return out
