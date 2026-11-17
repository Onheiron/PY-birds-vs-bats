"""Keyboard parsing."""

import pytest

from src.ui import keyboard
from src.ui.keyboard import parse_keys


@pytest.mark.parametrize(
    'raw, expected',
    [
        ('', []),
        ('\x1b[A', ['UP']),
        ('\x1b[B\x1b[C\x1b[D', ['DOWN', 'RIGHT', 'LEFT']),
        ('\x1bOA', ['UP']),  # application cursor mode
        (' ', ['SPACE']),
        ('\r', ['ENTER']),
        ('\n', ['ENTER']),
        ('\x7f', ['BACKSPACE']),
        ('\x1b', ['ESC']),
        ('\x03', ['QUIT']),
        ('q', ['QUIT']),
        ('p', ['p']),
        ('X', ['X']),
        ('\x01', []),  # unknown control characters are dropped
    ],
)
def test_single_keys(raw, expected):
    assert parse_keys(raw) == expected


def test_distinct_keys_in_one_read_are_all_delivered_in_order():
    assert parse_keys('\x1b[D\x1b[A ') == ['LEFT', 'UP', 'SPACE']


def test_auto_repeat_is_collapsed_in_game_mode():
    assert parse_keys('\x1b[A\x1b[A\x1b[A') == ['UP']
    assert parse_keys('\x1b[A\x1b[D\x1b[A') == ['UP', 'LEFT', 'UP']


def test_text_mode_keeps_every_character():
    assert parse_keys('quoll', text=True) == ['q', 'u', 'o', 'l', 'l']
    assert parse_keys('a b\x7f\r', text=True) == ['a', 'SPACE', 'b', 'BACKSPACE', 'ENTER']
    assert parse_keys('\x03', text=True) == ['QUIT']


def test_escape_followed_by_text_is_not_an_arrow():
    assert parse_keys('\x1b[Z') == ['ESC', '[', 'Z']


def test_read_keys_parses_what_is_pending(monkeypatch):
    monkeypatch.setattr(keyboard, '_read_pending', lambda: '\x1b[D\x1b[A')
    assert keyboard.read_keys() == ['LEFT', 'UP']
    monkeypatch.setattr(keyboard, '_read_pending', lambda: '')
    assert keyboard.read_keys() == []


def test_windows_console_events_are_translated(monkeypatch):
    class FakeMsvcrt:
        def __init__(self, chars):
            self.chars = list(chars)

        def kbhit(self):
            return bool(self.chars)

        def getwch(self):
            return self.chars.pop(0)

    # Arrow up (prefix 0xE0 + 'H'), 'a', arrow left (prefix 0x00 + 'K'), F1 (ignored), Enter
    fake = FakeMsvcrt(['\xe0', 'H', 'a', '\x00', 'K', '\x00', ';', '\r'])
    monkeypatch.setattr(keyboard, 'msvcrt', fake, raising=False)
    assert parse_keys(keyboard._read_pending_windows()) == ['UP', 'a', 'LEFT', 'ENTER']
