"""Menus, title screen, game over screen, saves and terminal output."""

import io
import random

import pytest

from src.engine import menus
from src.services import save_manager
from src.ui import game_over, terminal
from tests.harness import Simulation


@pytest.fixture
def sim():
    with Simulation(seed=77, level=5, all_birds=True) as simulation:
        simulation.run(120)
        yield simulation


def walk_menu(sim, title):
    """Press every kind of navigation key in every submenu; the UI must never crash."""
    state = sim.state
    rng = random.Random(5)
    keys = ['DOWN'] * 8 + ['UP'] * 3
    for option in range(7):
        keys += ['DOWN'] * option + ['ENTER']
        keys += ['DOWN', 'DOWN', 'RIGHT', 'LEFT', 'UP', 'DOWN', 'DOWN', 'DOWN', 'ENTER', 'DOWN', 'RIGHT']
        keys += ['ESC', 'ESC', 'ESC'] + ['UP'] * option
    keys += [rng.choice(['UP', 'DOWN', 'LEFT', 'RIGHT', 'ENTER', 'ESC', 'x', 'DOWN']) for _ in range(300)]

    screens = set()
    for key in keys:
        # Keep the menu open whatever the key did (start game, resume, quit...)
        state.game.quit_requested = False
        state.game.game_over = False
        if title:
            state.ui.show_title = True
        else:
            state.ui.show_title = False
            state.game.paused = True
        sim.press(key, title=title)
        screens.add(sim.screen.digest())
    return screens


def test_pause_menu_navigation(sim):
    sim.press('p')
    assert sim.state.game.paused
    assert 'RESUME' in sim.screen.text()
    assert len(walk_menu(sim, title=False)) > 20


def test_title_screen_navigation(sim):
    state = sim.state
    state.ui.show_title = True
    menus.open_title()
    sim.press(None, title=True)
    text = sim.screen.text()
    for option in ('CONTINUE', 'NEW GAME', 'LOAD', 'BIRDPEDIA', 'SETTINGS', 'QUIT'):
        assert option in text
    assert len(walk_menu(sim, title=True)) > 20


def test_new_game_from_title_applies_selected_difficulty(sim):
    state = sim.state
    state.ui.show_title = True
    menus.open_title()
    sim.press('DOWN', title=True)  # CONTINUE -> NEW GAME
    state.settings.difficulty = 1
    try:
        sim.press('RIGHT', title=True)  # NORMAL -> HARD
        assert state.settings.difficulty == 2
        sim.press('ENTER', title=True)
        assert state.ui.show_title is False
        assert state.game.score == 0
        assert sim.constants.game.life_recovery_on_spawn is False
    finally:
        sim.constants.reload_for_difficulty(1)
        state.settings.difficulty = 1


def test_quit_key_requests_exit(sim):
    sim.step(key='QUIT')
    assert sim.state.game.quit_requested
    assert sim.state.game.game_over


def test_save_and_load_round_trip(sim):
    state = sim.state
    saved = {
        'score': state.game.score,
        'miles': state.game.miles,
        'level': state.game.level,
        'lives': state.game.lives,
        'colors': list(state.birds.colors),
        'lanes': list(state.birds.random_lanes),
        'lost': list(state.birds.lost),
        'xp': list(state.birds.per_bird_xp),
        'obstacles': len(state.enemies.obstacles),
    }
    assert save_manager.save_game(2)
    assert save_manager.list_save_slots()[2]['exists']

    sim.run(900)  # keep playing: the world moves on
    assert state.game.miles != saved['miles']

    assert save_manager.load_game(2)
    assert state.game.score == saved['score']
    assert state.game.miles == saved['miles']
    assert state.game.level == saved['level']
    assert state.game.lives == saved['lives']
    assert state.birds.colors == saved['colors']
    assert state.birds.random_lanes == saved['lanes']
    assert state.birds.lost == saved['lost']
    assert state.birds.per_bird_xp == saved['xp']
    assert len(state.enemies.obstacles) == saved['obstacles']

    # The restored game keeps running
    sim.run(300)
    assert save_manager.delete_save(2)
    assert not save_manager.load_game(2)


def test_game_over_screen_layout(sim):
    sim.state.game.score = 12345
    elapsed, elapsed_str, avg_ppm = game_over.session_stats()
    assert elapsed >= 0 and ':' in elapsed_str and avg_ppm >= 0

    fb = sim.fb
    game_over.draw(fb, elapsed_str, player_name='ADA', phase='name')
    text = '\n'.join(''.join(char for char, _ in row) for row in fb.current)
    assert 'GAME  OVER' in text
    assert 'Final Score:    12,345' in text
    assert '[ ADA_' in text

    game_over.draw(fb, elapsed_str, selected=1, phase='menu')
    text = '\n'.join(''.join(char for char, _ in row) for row in fb.current)
    assert '> [  EXIT ] <' in text and 'RETRY' in text
    fb.invalidate()


def test_write_frame_wraps_output_in_a_synchronized_update(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr(terminal.sys, 'stdout', stream)
    monkeypatch.setattr(terminal, '_sync_output', True)
    terminal.write_frame('')
    assert stream.getvalue() == ''  # nothing changed: nothing is sent
    terminal.write_frame('X')
    assert stream.getvalue() == '\033[?2026hX\033[?2026l'

    stream.seek(0)
    stream.truncate()
    monkeypatch.setattr(terminal, '_sync_output', False)
    terminal.write_frame('Y')
    assert stream.getvalue() == 'Y'
