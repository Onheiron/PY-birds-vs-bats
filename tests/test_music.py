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


def test_the_music_holds_while_the_game_is_paused(mixer):
    from src.services import audio

    audio._ready = None
    assert audio.is_audio_available()
    audio.update_active_birds({'YELLOW': 1})
    audio.start_music()
    deadline = time.time() + 20
    while audio._music['playing_now'] is None and time.time() < deadline:
        time.sleep(0.05)
    channel = mixer.mixer.Channel(audio._music['channel'])
    audio.pause_music(True)
    assert audio._music['paused']
    audio.pause_music(False)
    assert not audio._music['paused'] and channel.get_busy()
    audio.cleanup()


def test_every_effect_and_screen_music_is_made(mixer):
    from src.services.music import effects, screens

    for name in effects.EFFECTS:
        audio = effects.render(name)
        assert audio.ndim == 2 and 0.05 < np.abs(audio).max() < 1.0, name
    assert effects.render('bounce') is None  # the bounce stays silent: it would play all the time
    for name in screens.SCREENS:
        audio = screens.render(name)
        assert audio.ndim == 2 and screens.seconds(audio) > 5, name


def test_title_game_and_game_over_music_take_turns(mixer, monkeypatch):
    from src.services import audio

    monkeypatch.setattr(audio, 'GAME_OVER_DELAY', 0.0)
    audio._ready = None
    assert audio.is_audio_available()
    audio.play_screen('title')
    assert audio._music['screen'] == 'title' and not audio._music['playing']
    audio.update_active_birds({'YELLOW': 1})
    audio.start_music()
    assert audio._music['screen'] is None and audio._music['playing']
    audio.play_screen('game_over')
    assert audio._music['screen'] == 'game_over' and not audio._music['playing']
    audio.play_sfx('swap')
    audio.play_sfx('card_take')
    audio.cleanup()


def test_leaving_a_paused_game_for_the_title_brings_the_title_music(mixer):
    from src.services import audio

    audio._ready = None
    assert audio.is_audio_available()
    audio.update_active_birds({'YELLOW': 1})
    audio.start_music()
    audio.pause_music(True)  # paused in the game...
    audio.stop_music()  # ...then back to the title (the session ends)
    assert not audio._music['paused']
    audio.play_screen('title')
    deadline = time.time() + 20
    while not any(mixer.mixer.Channel(i).get_busy() for i in (0, 1)) and time.time() < deadline:
        time.sleep(0.05)
    assert not audio._music['paused']
    assert mixer.mixer.Channel(audio._music['channel']).get_busy()
    audio.pause_music(True)  # a pause outside the game holds nothing
    assert not audio._music['paused']
    audio.cleanup()


def test_boss_themes_and_dressed_parts_fit_their_loop():
    from src.services.music import boss

    for kind, spec in boss.BOSSES.items():
        beats = boss.beats(kind)
        end = max(st + du for st, du, _n, _v in score.melody(spec['melody']))
        assert beats - spec['meter'] <= end <= beats, kind  # 16 bars (the last one may rest)
        for world in range(1, 7):
            for key, instrument, events, _gain, _post in boss.layers(
                kind,
                world,
                {'YELLOW': 2, 'RED': 1, 'GOLD': 1},
                3,
                2,
                arrangement.quantity_step,
                arrangement._instrument_for,
            ):
                spec_i = INSTRUMENTS[instrument]
                for start, length, notes, velocity in events:
                    assert -0.01 <= start < beats + 1 and length > 0 and 0 < velocity <= 127, key
                    if not spec_i.get('drum'):
                        assert all(spec_i['low'] - 13 <= n <= spec_i['high'] + 13 for n in notes), (key, notes)
    assert [boss.health_step(f) for f in (1.0, 0.7, 0.5, 0.2, 0.05)] == [0, 0, 1, 2, 3]
    assert boss.kind('unknown') == 'normal'


def test_boss_loops_and_the_corruption(mixer):
    flock = {'YELLOW': 4, 'RED': 3, 'BLUE': 2}
    world = arrangement.loop(1, flock, 2, 5)
    for kind in ('normal', 'tree', 'wind', 'jelly', 'owl'):
        loop = arrangement.loop(1, flock, 2, 5, boss=kind, health=2)
        assert loop.ndim == 2 and np.abs(loop).max() < 1.0, kind
        assert 0.5 < np.sqrt((loop**2).mean()) / np.sqrt((world**2).mean()) < 2.0, kind  # no loudness jump
    bridge = arrangement.bridge(1, flock, 2, 5, 'normal')
    quarter = len(bridge) // 4
    first, last = bridge[:quarter], bridge[-quarter:]
    assert np.abs(bridge).max() < 1.0 and np.sqrt((first**2).mean()) > 0.03 and np.sqrt((last**2).mean()) > 0.03


def test_a_boss_arrives_with_its_corruption_and_leaves(mixer, monkeypatch):
    from src.services import audio
    from src.services.music import boss

    monkeypatch.setattr(boss, 'BRIDGE_BARS', 1)
    audio._ready = None
    assert audio.is_audio_available()
    audio.update_music_for_biome(1)
    audio.update_active_birds({'YELLOW': 1})
    audio.start_music()
    deadline = time.time() + 20
    while audio._music['playing_now'] is None and time.time() < deadline:
        time.sleep(0.05)
    audio.update_boss('owl', 0)
    deadline = time.time() + 30
    while audio._music['playing_now'][4] != 'owl' and time.time() < deadline:
        time.sleep(0.05)
    assert audio._music['bridge_until'] > 0  # the corruption came first
    deadline = time.time() + 30
    while audio._music['loop_len'] == 0 and time.time() < deadline:
        time.sleep(0.05)
    assert audio._music['loop_len'] > 0  # then the boss's loop
    audio.update_boss('owl', 2)
    deadline = time.time() + 30
    while audio._music['playing_now'][5] != 2 and time.time() < deadline:
        time.sleep(0.05)
    assert audio._music['playing_now'][5] == 2
    audio.update_boss(None)
    deadline = time.time() + 30
    while audio._music['playing_now'][4] is not None and time.time() < deadline:
        time.sleep(0.05)
    assert audio._music['playing_now'][4] is None and audio._music['bridge_until'] == 0
    audio.cleanup()


def test_a_new_loop_starts_where_the_old_one_was():
    from src.services import audio

    audio._music['loop_len'] = 10.0
    audio._music['loop_start'] = time.monotonic() - 2.5  # a quarter in
    wave = np.arange(400, dtype=np.float32)
    turned = audio._from_where_it_was(wave)
    assert 95 <= turned[0] <= 105 and len(turned) == 400
    audio._music['loop_len'] = 0.0


def test_boss_health_of_every_kind():
    from src.services.sound import boss_health

    assert boss_health({'hp': 50, 'max_hp': 200}) == 0.25
    tree = {'boss_type': 'tree', 'branches': [{'hp': 10, 'max_hp': 10}, {'hp': 0, 'max_hp': 10, 'destroyed': True}]}
    assert boss_health(tree) == 0.5
