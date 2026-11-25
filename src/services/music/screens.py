"""Music of the screens around the game: the title (and its menus), and the game over.

- title: a theme in G major that loops (flute and violin, harp, pizzicato
  bass, strings, light drums);
- game over: a short A minor phrase (violin, strings, harp), then a calm loop
  (strings, harp, celesta) while the screen stays.
"""

import numpy as np

from src.services.music import sampler, score

N = score.note

TITLE = {
    'bpm': 92,
    'chords': ['G', 'C', 'Am', 'D', 'G', 'Bm', 'Am', 'G', 'Em', 'D', 'D', 'G', 'G', 'Bm', 'D', 'G'],
    'melody': '''
        G4:.5 B4:.5 D5:1 E5:.5 D5:.5 B4:1 | C5:1 E5:1 D5:1 B4:1 | A4:.5 B4:.5 C5:1 B4:.5 A4:.5 G4:1 | A4:3 r:1 |
        G4:.5 B4:.5 D5:1 E5:.5 D5:.5 G5:1 | F#5:1 E5:1 D5:1 B4:1 | C5:.5 D5:.5 E5:1 D5:.5 C5:.5 A4:1 | G4:3 r:1 |
        E5:1 F#5:.5 G5:.5 A5:1 G5:1 | F#5:1.5 E5:.5 D5:2 | C5:1 D5:.5 E5:.5 F#5:1 A5:1 | G5:2 D5:1 r:1 |
        G4:.5 B4:.5 D5:1 E5:.5 D5:.5 G5:1 | F#5:1 E5:1 D5:1 B4:1 | C5:.5 E5:.5 D5:.5 B4:.5 A4:1 F#4:1 | G4:3 r:1''',
}


def title():
    """The title loop: stereo float32."""
    bpm, beats = TITLE['bpm'], score.BEATS
    melody = score.melody(TITLE['melody'])
    low = [(st, du, [n - 12 for n in ns], v - 20) for st, du, ns, v in melody]
    bass = [
        (bar * 4 + beat, 0.9, [score.tone(chord, 0 if beat == 0 else 2, 2)], 85)
        for bar, chord in enumerate(TITLE['chords'])
        for beat in (0, 2)
    ]
    pad = [(bar * 4, 4, [score.tone(chord, d, 3) for d in (0, 1, 2)], 60) for bar, chord in enumerate(TITLE['chords'])]
    hits = [(0, 36), (2, 36), (1, 42), (3, 42), (1.5, 42), (3.5, 42)]
    drums = [(bar * 4 + st, 0.5, [hit], 80 if hit == 36 else 50) for bar in range(score.BARS) for st, hit in hits]
    return sampler.mix(
        [
            (sampler.render_part(melody, 'flute', bpm, beats), 1.0, 0.0),
            (sampler.render_part(low, 'violin', bpm, beats), 0.45, -0.3),
            (sampler.render_part(score.frosty(TITLE, 2, 2), 'harp', bpm, beats), 0.7, 0.4),
            (sampler.render_part(bass, 'pizzicato', bpm, beats), 0.9, 0.1),
            (sampler.render_part(pad, 'strings', bpm, beats), 0.5, 0.0),
            (sampler.render_part(drums, 'drums', bpm, beats), 0.45, 0.0),
        ]
    )


def game_over_phrase():
    """The game over phrase (about 11 s, played once): stereo float32."""
    bpm, beats = 66, 12
    violin = score.melody('E5:1 D5:1 C5:1 B4:1 | A4:2 G#4:1 B4:1 | A4:4')
    pad = [
        (0, 4, [N('A3'), N('C4'), N('E4')], 62),
        (4, 2, [N('F3'), N('A3'), N('C4')], 60),
        (6, 2, [N('E3'), N('G#3'), N('B3')], 62),
        (8, 4, [N('A2'), N('E3'), N('A3'), N('C4')], 64),
    ]
    harp = [(8 + i * 0.25, 1, [N(n)], 75) for i, n in enumerate(['A5', 'E5', 'C5', 'A4', 'E4', 'C4', 'A3'])]
    return sampler.one_shot(
        [
            (sampler.render_part(violin, 'violin', bpm, beats), 1.0, 0.0),
            (sampler.render_part(pad, 'strings', bpm, beats), 0.6, 0.0),
            (sampler.render_part(harp, 'harp', bpm, beats), 0.7, 0.3),
            (sampler.render_part([(8, 2, [N('A1')], 90)], 'timpani', bpm, beats), 0.7, 0.0),
        ],
        wet=0.18,
        tail=1.0,
    )


def game_over_loop():
    """The calm loop under the game over screen (8 bars): stereo float32."""
    bpm, beats = 60, 32
    chords = ['Am', 'F', 'C', 'E', 'Am', 'F', 'Dm', 'E']
    pad = [(bar * 4, 4, [score.tone(chord, d, 3) for d in (0, 1, 2)], 56) for bar, chord in enumerate(chords)]
    harp = [
        (bar * 4 + i, 1.5, [score.tone(chord, [0, 2, 1, 2][i], 4)], 62)
        for bar, chord in enumerate(chords)
        for i in range(4)
    ]
    celesta = [(bar * 4 + 2.5, 1, [score.tone(chord, 2, 6)], 55) for bar, chord in enumerate(chords) if bar % 2]
    return sampler.mix(
        [
            (sampler.render_part(pad, 'strings', bpm, beats), 0.6, 0.0),
            (sampler.render_part(harp, 'harp', bpm, beats), 0.8, 0.3),
            (sampler.render_part(celesta, 'celesta', bpm, beats), 0.5, -0.3),
        ],
        wet=0.25,
    )


SCREENS = {'title': title, 'game_over_phrase': game_over_phrase, 'game_over_loop': game_over_loop}
_made = {}


def render(name):
    """Stereo float32 audio of a screen's music, made once."""
    if name not in _made:
        _made[name] = SCREENS[name]()
    return _made[name]


def seconds(audio):
    return len(audio) / sampler.SAMPLE_RATE if isinstance(audio, np.ndarray) else 0.0
