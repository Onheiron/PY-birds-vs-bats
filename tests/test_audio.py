"""The audio engine (SDL audio through pygame-ce), on a silent dummy device."""

import os
import time

import pytest

pytest.importorskip('numpy')
pytest.importorskip('pygame')
os.environ['SDL_AUDIODRIVER'] = 'dummy'

from src.services import audio, synth  # noqa: E402


@pytest.fixture
def engine():
    audio._ready = None
    assert audio.is_audio_available()
    yield audio
    audio.cleanup()


def test_every_sound_effect_is_made_and_plays(engine):
    for name in ('bounce', 'hit', 'destroy', 'powerup', 'egg', 'level_up', 'bat_death', 'boss_death'):
        wave = synth.sfx_wave(name)
        assert wave is not None and len(wave) > 0 and abs(wave).max() <= 1.0
        engine.play_sfx(name)
    assert synth.sfx_wave('no such sound') is None


def test_the_music_follows_the_flock_with_a_crossfade(engine):
    import pygame

    engine.update_active_birds({'YELLOW', 'RED'})
    engine.start_music()
    first = engine._music['channel']
    assert pygame.mixer.Channel(first).get_busy()
    engine.update_active_birds({'YELLOW', 'RED', 'WHITE'})
    deadline = time.time() + 10
    while engine._music['channel'] == first and time.time() < deadline:
        time.sleep(0.05)
    assert engine._music['channel'] != first  # the new loop plays on the other channel
    engine.stop_music()
    assert not engine._music['playing']
