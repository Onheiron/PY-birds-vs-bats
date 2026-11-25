"""The audio engine (SDL audio through pygame-ce), on a silent dummy device."""

import os

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
