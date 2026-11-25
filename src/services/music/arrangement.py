"""The loop that plays now: the world's theme and drums, plus a part for every bird type
in the flock (by how many there are) and for the bats on screen, at the gear's speed.

Steps (score.py): quantity q = 1 bird, 2-3, 4+ (bats: 1-2, 3-4, 5+); speed
s = gears 1-3, 4-6, 7-10. Rendered parts are kept (a few dozen) so that a
change of flock or gear only renders what is new.
"""

from collections import OrderedDict

from src.services.music import sampler, score
from src.services.music.instruments import BIRD_INSTRUMENT, INSTRUMENTS

CACHE_SIZE = 48
THEME_GAIN = 1.0
DRUM_GAIN = 0.55
PART_GAIN = 0.8

_cache = OrderedDict()


def quantity_step(count, kind='BIRD'):
    if count <= 0:
        return 0
    if kind == 'BATS':
        return 1 if count <= 2 else 2 if count <= 4 else 3
    return 1 if count == 1 else 2 if count <= 3 else 3


def speed_step(gear):
    return 1 if gear <= 3 else 2 if gear <= 6 else 3


def _rendered(key, make):
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    audio = make()
    _cache[key] = audio
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return audio


def _instrument_for(kind, q):
    instrument = BIRD_INSTRUMENT[kind]
    if instrument == 'trumpet' and q >= 2:
        return 'brass'  # one Red: a trumpet; more: a brass section
    return instrument


def layers(world, counts, bats, gear):
    """[(key, instrument, events, gain)] of what plays: theme, drums, birds, bats."""
    s = speed_step(gear)
    w = score.world(world)
    out = [
        (('theme', world, s), w['instrument'], score.theme(world), THEME_GAIN),
        (('drums', world, s), 'drums', score.drums(world, s), DRUM_GAIN),
    ]
    for kind in sorted(counts):
        q = quantity_step(counts[kind])
        if q and kind in score.PARTS and kind in BIRD_INSTRUMENT:
            out.append(((kind, world, q, s), _instrument_for(kind, q), score.part(world, kind, q, s), PART_GAIN))
    q = quantity_step(bats, 'BATS')
    if q:
        out.append((('BATS', world, q, s), 'tremolo', score.part(world, 'BATS', q, s), PART_GAIN))
    return out


def loop(world, counts, bats=0, gear=1):
    """Stereo float32 loop (n, 2) for this state of the game."""
    bpm = score.bpm(world, speed_step(gear))
    parts = []
    playing = layers(world, counts, bats, gear)
    bus = 1.0 / (1.0 + 0.07 * max(0, len(playing) - 3))  # more parts, each a little softer
    for key, instrument, events, gain in playing:
        audio = _rendered(key, lambda i=instrument, e=events: sampler.render_part(e, i, bpm, score.BEATS))
        parts.append((audio, gain * bus, INSTRUMENTS[instrument].get('pan', 0.0)))
    return sampler.mix(parts)
