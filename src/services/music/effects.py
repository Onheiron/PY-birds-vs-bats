"""Sound effects, played with the instruments of the music (sampler.py).

Each effect is a few notes; ``render(name)`` makes it once (stereo float32)
and keeps it. The bounce has none: it would play all the time.
"""

from src.services.music import sampler
from src.services.music.score import note as N  # noqa: N812

SECOND = 60  # tempo for effects: a beat is a second


def _notes(instrument, events, seconds):
    """Mono audio of events (start s, length s, [notes], velocity)."""
    return sampler.render_part(events, instrument, SECOND, seconds)


def _run(instrument, names, start, step, length, velocity):
    return [(start + i * step, length, [N(n)], velocity) for i, n in enumerate(names)]


def hit():
    """A muted thud: a low tom and a short low pizzicato."""
    return [
        (_notes('drums', [(0, 0.2, [45], 110)], 0.5), 1.0, 0),
        (_notes('pizzicato', [(0, 0.1, [N('E3')], 100)], 0.5), 0.7, 0),
    ]


def destroy():
    """Timpani, a short crash, a harp run down."""
    harp = _run('harp', ['G6', 'E6', 'C6', 'G5', 'E5'], 0.05, 0.04, 0.3, 80)
    return [
        (_notes('timpani', [(0, 0.5, [N('G2')], 120)], 1.2), 1.0, 0),
        (_notes('drums', [(0, 0.5, [49], 90)], 1.2), 0.5, 0),
        (_notes('harp', harp, 1.2), 0.7, 0.3),
    ]


def powerup():
    """A harp glissando up and a celesta on top."""
    harp = _run('harp', ['C5', 'D5', 'E5', 'G5', 'A5', 'C6', 'D6', 'E6'], 0, 0.035, 0.4, 85)
    return [
        (_notes('harp', harp, 1.2), 0.9, -0.2),
        (_notes('celesta', [(0.3, 0.6, [N('G6'), N('C7')], 90)], 1.2), 0.8, 0.2),
    ]


def egg():
    """A celesta chime and a glockenspiel sparkle."""
    return [
        (_notes('celesta', [(0, 0.3, [N('E6')], 95), (0.12, 0.6, [N('G6')], 95)], 1.0), 0.9, 0),
        (_notes('glockenspiel', [(0.25, 0.4, [N('C7')], 80)], 1.0), 0.6, 0.3),
    ]


def level_up():
    """A trumpet arpeggio into a brass chord and a crash."""
    return [
        (_notes('trumpet', _run('trumpet', ['C5', 'E5', 'G5'], 0, 0.09, 0.12, 100), 1.8), 0.9, 0.2),
        (_notes('brass', [(0.3, 0.9, [N('C4'), N('E4'), N('G4'), N('C5')], 105)], 1.8), 0.9, 0),
        (_notes('drums', [(0.3, 1, [49], 85)], 1.8), 0.5, 0),
    ]


def game_over():
    """The sad trombone."""
    trombone = [
        (0, 0.45, [N('G3')], 95),
        (0.5, 0.45, [N('F#3')], 92),
        (1.0, 0.45, [N('F3')], 90),
        (1.5, 1.4, [N('E3')], 95),
    ]
    return [(_notes('trombone', trombone, 3.2), 1.0, 0), (_notes('timpani', [(1.5, 1, [N('E2')], 90)], 3.2), 0.6, 0)]


def bird_lost():
    """A clarinet falling a minor third, a soft thud."""
    return [
        (_notes('clarinet', [(0, 0.18, [N('E5')], 95), (0.2, 0.5, [N('C#5')], 90)], 1.0), 0.9, 0),
        (_notes('drums', [(0.2, 0.3, [45], 70)], 1.0), 0.5, 0),
    ]


def bat_death():
    """A little chiptune squeak sliding down, and a pizzicato pop."""
    return [
        (sampler.glide('square', N('C6'), N('C5'), 0.22, 0.6, 100), 0.9, 0),
        (_notes('pizzicato', [(0, 0.1, [N('G5')], 90)], 0.6), 0.6, 0),
    ]


def boss_scream():
    """A choir and a tremolo cluster sliding down, a taiko under it."""
    return [
        (sampler.glide('tremolo', N('C4'), N('A2'), 1.3, 1.6, 120), 1.0, -0.2),
        (sampler.glide('tremolo', N('C#4'), N('Bb2'), 1.3, 1.6, 120), 1.0, 0.2),
        (sampler.glide('choir', N('F#4'), N('D#3'), 1.2, 1.6, 110), 0.8, 0),
        (_notes('taiko', [(0, 0.5, [N('C2')], 120), (0.4, 0.5, [N('C2')], 110)], 1.6), 0.9, 0),
    ]


def boss_death():
    """A timpani roll into a big major chord, a crash, a harp run up."""
    roll = [(i * 0.07, 0.1, [N('C2')], 70 + i * 5) for i in range(10)] + [(0.75, 1, [N('C2')], 125)]
    harp = _run('harp', ['C5', 'E5', 'G5', 'C6', 'E6', 'G6', 'C7'], 0.8, 0.04, 0.4, 80)
    return [
        (_notes('timpani', roll, 2.6), 1.0, 0),
        (_notes('brass', [(0.75, 1.6, [N('C4'), N('E4'), N('G4'), N('C5')], 110)], 2.6), 0.9, 0),
        (_notes('strings', [(0.75, 1.8, [N('C3'), N('G3'), N('E4'), N('C5')], 100)], 2.6), 0.6, 0),
        (_notes('drums', [(0.75, 1, [49], 95)], 2.6), 0.6, 0),
        (_notes('harp', harp, 2.6), 0.7, 0.3),
    ]


def swap():
    """A pan flute swooping up and back."""
    return [
        (sampler.glide('pan_flute', N('G5'), N('D6'), 0.18, 0.5, 90), 0.8, -0.3),
        (sampler.glide('pan_flute', N('D6'), N('G5'), 0.18, 0.5, 90, delay=0.12), 0.8, 0.3),
    ]


def card_take():
    """A quick harp arpeggio and a celesta."""
    return [
        (_notes('harp', _run('harp', ['G4', 'B4', 'D5', 'G5'], 0, 0.05, 0.4, 90), 0.9), 0.9, 0),
        (_notes('celesta', [(0.2, 0.5, [N('B6')], 80)], 0.9), 0.6, 0.2),
    ]


def menu_move():
    return [(_notes('music_box', [(0, 0.15, [N('E6')], 70)], 0.3), 0.7, 0)]


def menu_select():
    return [(_notes('celesta', [(0, 0.12, [N('C6')], 90), (0.08, 0.3, [N('G6')], 90)], 0.6), 0.8, 0)]


def menu_back():
    return [(_notes('celesta', [(0, 0.12, [N('G6')], 85), (0.08, 0.3, [N('C6')], 80)], 0.6), 0.8, 0)]


EFFECTS = {
    'hit': hit,
    'destroy': destroy,
    'powerup': powerup,
    'egg': egg,
    'level_up': level_up,
    'game_over': game_over,
    'bird_lost': bird_lost,
    'bat_death': bat_death,
    'boss_scream': boss_scream,
    'boss_death': boss_death,
    'swap': swap,
    'card_take': card_take,
    'menu_move': menu_move,
    'menu_select': menu_select,
    'menu_back': menu_back,
}
QUIET = {'menu_move', 'menu_select', 'menu_back'}  # little room: they are dry and close

_made = {}


def render(name):
    """Stereo float32 audio of an effect, made once; None for an unknown (or silent) one."""
    if name not in EFFECTS:
        return None
    if name not in _made:
        _made[name] = sampler.one_shot(EFFECTS[name](), wet=0.06 if name in QUIET else 0.12)
    return _made[name]
