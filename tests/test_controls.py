"""Control profiles: the hints name the controls of the device in use."""

import pytest

from src.core import state as game_state
from src.ui import controls
from tests.harness import Simulation


@pytest.fixture(autouse=True)
def restore_settings():
    bindings = dict(game_state.settings.key_bindings)
    profile = getattr(game_state.settings, 'controls_profile', 'auto')
    yield
    game_state.settings.key_bindings = bindings
    game_state.settings.controls_profile = profile


def test_hints_follow_the_profile():
    with Simulation(seed=1, key_rate=0):
        template = '{navigate} Navigate  {select} Select  {back} Back'
        assert controls.hint(template, 'keyboard') == '↑↓ Navigate  ⏎ Select  ESC Back'
        assert controls.hint(template, 'xbox') == '↑↓ Navigate  [A] Select  [B] Back'
        assert controls.hint(template, 'playstation') == '↑↓ Navigate  ✕ Select  ○ Back'
        assert controls.hint('{move} move', 'steamdeck') == '←→ L1/R1 move'
        assert controls.hint('{unknown} stays') == '{unknown} stays'


def test_the_keyboard_profile_shows_the_players_bindings():
    with Simulation(seed=1, key_rate=0):
        game_state.settings.key_bindings = dict(game_state.settings.key_bindings, BOUNCE='W', SWAP='E')
        assert controls.hint('{bounce} bounce {swap} swap', 'keyboard') == 'W bounce E swap'


def test_the_setting_chooses_the_profile_and_auto_is_the_keyboard_in_a_terminal():
    with Simulation(seed=1, key_rate=0):
        game_state.settings.controls_profile = 'auto'
        assert controls.active_profile() == 'keyboard'
        controls.cycle_profile()
        assert game_state.settings.controls_profile == 'keyboard'
        game_state.settings.controls_profile = 'playstation'
        assert controls.label('bounce') == '✕'
