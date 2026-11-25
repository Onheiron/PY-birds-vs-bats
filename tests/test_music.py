"""The music: score, steps, and loops played with the instrument samples."""

import os
import time

import pytest

from src.services.music import arrangement, score
from src.services.music.instruments import BIRD_INSTRUMENT, INSTRUMENTS

np = pytest.importorskip('numpy')


def test_every_part_fits_the_loop_in_every_world_and_step():
    for world in range(1, 7):
        assert abs(max(st + du for st, du, _n, _v in score.theme(world)) - score.BEATS) <= 1
        for kind in score.PARTS:
            spec = INSTRUMENTS[BIRD_INSTRUMENT[kind]]
            for q in (1, 2, 3):
                for s in (1, 2, 3):
                    for start, length, notes, velocity in score.part(world, kind, q, s):
                        assert 0 <= start < score.BEATS and length > 0 and 0 < velocity <= 127
                        # within the instrument's sampled range (pitched at most half an octave out)
                        assert all(spec['low'] - 6 <= n <= spec['high'] + 6 for n in notes), (kind, notes)


def test_steps_of_quantity_and_speed():
    assert [arrangement.quantity_step(n) for n in (0, 1, 2, 3, 4, 9)] == [0, 1, 2, 2, 3, 3]
    assert [arrangement.quantity_step(n, 'BATS') for n in (0, 2, 3, 5)] == [0, 1, 2, 3]
    assert [arrangement.speed_step(g) for g in (1, 3, 4, 6, 7, 10)] == [1, 1, 2, 2, 3, 3]


def test_more_birds_play_more_and_one_red_is_a_trumpet():
    few = arrangement.layers(1, {'RED': 1}, 0, 1)
    many = arrangement.layers(1, {'RED': 4, 'YELLOW': 2}, 3, 8)
    assert [layer[1] for layer in few] == ['flute', 'drums', 'trumpet']
    assert {layer[1] for layer in many} >= {'brass', 'marimba', 'tremolo'}


@pytest.fixture
def mixer():
    pygame = pytest.importorskip('pygame')
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    from src.services.music import sampler

    if not sampler.available():
        pytest.skip('no sample bank')
    pygame.mixer.pre_init(22050, -16, 2, 512)
    pygame.mixer.init()
    yield pygame
    pygame.mixer.quit()


def test_a_loop_is_stereo_seamless_and_at_a_steady_level(mixer):
    quiet = arrangement.loop(1, {'YELLOW': 1}, 0, 1)
    full = arrangement.loop(5, {'RED': 4, 'YELLOW': 2, 'BERSERK': 1, 'GOLD': 1}, 6, 9)
    for loop in (quiet, full):
        assert loop.ndim == 2 and loop.shape[1] == 2
        assert np.abs(loop).max() < 1.0
    rms = [float(np.sqrt((loop**2).mean())) for loop in (quiet, full)]
    assert min(rms) > 0.05 and max(rms) / min(rms) < 2.0  # no loudness jump between a lone bird and a full flock


def test_the_game_music_follows_the_flock(mixer):
    from src.services import audio

    audio._ready = None
    assert audio.is_audio_available()
    audio.update_music_for_biome(1)
    audio.update_active_birds({'YELLOW': 4, 'RED': 3, 'BLUE': 2})
    audio.start_music()
    deadline = time.time() + 20
    while audio._music['playing_now'] is None and time.time() < deadline:
        time.sleep(0.05)
    first = audio._music['playing_now']
    assert first is not None
    audio.update_active_birds({'YELLOW': 4, 'RED': 3, 'BLUE': 3})  # still the same steps: nothing to redo
    assert audio._music['playing_now'] == first
    audio.update_tempo_for_gear(8)
    deadline = time.time() + 20
    while audio._music['playing_now'] == first and time.time() < deadline:
        time.sleep(0.05)
    assert audio._music['playing_now'][3] == 3  # speed step 3
    audio.cleanup()
