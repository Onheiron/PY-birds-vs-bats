"""Tutorial tips: once each, they hold the game, ENTER goes on, S skips them all."""

from src.engine import input_handler, meta, tutorial
from tests.harness import Simulation


def start(sim):
    state = sim.state
    state.meta.profile = meta.new_profile()
    state.settings.tutorial = True
    tutorial._started['frame'] = None
    return state


def test_the_first_tip_holds_the_game_until_enter():
    with Simulation(seed=1, key_rate=0) as sim:
        state = start(sim)
        sim.run(120)
        assert state.ui.tip is not None and state.ui.tip['id'] == 'bounce'
        assert 'KEEP THEM FLYING' in sim.screen.text()
        frame = state.game.frame_count
        sim.run(60)
        assert state.game.frame_count == frame  # held
        input_handler.process_input('ENTER')
        assert state.ui.tip is None
        sim.run(60)
        assert state.game.frame_count > frame
        assert 'bounce' in state.meta.profile['tutorial_seen']


def test_a_tip_shows_once_and_skip_ends_the_tutorial(monkeypatch):
    from src.services import save_manager

    monkeypatch.setattr(save_manager, 'save_default_settings', lambda: None)
    with Simulation(seed=1, key_rate=0) as sim:
        state = start(sim)
        assert tutorial.show('boss')
        tutorial.dismiss()
        assert not tutorial.show('boss')  # seen
        assert tutorial.show('fear')
        input_handler.process_input('s')
        assert state.ui.tip is None and state.settings.tutorial is False
        assert not tutorial.show('waves')
        assert set(state.meta.profile['tutorial_seen']) == set(tutorial.TIPS)
