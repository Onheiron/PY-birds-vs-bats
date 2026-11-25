"""The window mode: the terminal emulator and the gamepad keys (needs pygame-ce)."""

import os

import pytest

pygame = pytest.importorskip('pygame')

from src.core import state as game_state  # noqa: E402
from src.ui import window  # noqa: E402
from tests.harness import Simulation  # noqa: E402


def test_the_screen_reads_ansi_like_a_terminal():
    screen = window.Screen(10, 3)
    screen.feed('\033[2J\033[H\033[1;38;5;196mAB\033[0m\033[2;4H\033[2;38;2;10;20;30mc\033[8mx')
    a, b = screen.grid[0][0], screen.grid[0][1]
    assert (a.char, a.fg, a.bold) == ('A', window.PALETTE[196], True)
    assert b.char == 'B'
    c = screen.grid[1][3]
    assert (c.char, c.fg, c.faint, c.bold) == ('c', (10, 20, 30), True, False)
    assert screen.grid[1][4].hidden  # conceal
    screen.feed('\033[?2026h\033[?25l')  # private modes are ignored
    assert screen.grid[0][0].char == 'A'


@pytest.fixture
def win():
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    w = window.Window(20, 10)
    yield w
    w.close()


def press(w, button):
    pygame.event.post(pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=button, instance_id=0))
    keys = w.read_keys()
    pygame.event.post(pygame.event.Event(pygame.CONTROLLERBUTTONUP, button=button, instance_id=0))
    w.read_keys()
    return keys


def test_gamepad_buttons_play_the_game(win):
    with Simulation(seed=1, key_rate=0):
        game_state.ui.show_title = False
        assert press(win, win.A) == ['UP']  # bounce
        assert press(win, win.B) == ['SPACE']  # swap
        assert press(win, win.DPAD_LEFT) == ['LEFT']
        assert press(win, win.RB) == ['RIGHT']
        assert press(win, win.START) == ['p']


def test_gamepad_buttons_in_menus_and_cards(win):
    with Simulation(seed=1, key_rate=0):
        game_state.ui.show_title = True
        assert press(win, win.A) == ['ENTER']
        assert press(win, win.B) == ['ESC']
        assert press(win, win.DPAD_DOWN) == ['DOWN']
        game_state.ui.show_title = False
        game_state.choice.active = {'kind': 'egg', 'cards': [], 'index': 0}
        assert press(win, win.A) == []  # A is the bounce: it never takes a card
        assert press(win, win.X) == ['ENTER']  # take
        assert press(win, win.Y) == ['r']  # reroll
        assert press(win, win.B) == ['s']  # skip
        game_state.choice.active = None


def test_the_keyboard_works_in_the_window(win):
    with Simulation(seed=1, key_rate=0):
        game_state.ui.show_title = False
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT, mod=0))
        pygame.event.post(pygame.event.Event(pygame.TEXTINPUT, text=' '))
        assert win.read_keys() == ['LEFT', 'SPACE']
