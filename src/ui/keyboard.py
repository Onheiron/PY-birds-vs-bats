"""Non-blocking keyboard input for Unix terminals and the Windows console.

Raw input is turned into key names: 'LEFT', 'RIGHT', 'UP', 'DOWN', 'SPACE',
'ENTER', 'ESC', 'BACKSPACE', 'QUIT' or a single printable character.
"""

import os
import sys

if os.name == 'nt':
    import msvcrt
else:
    import select

_ARROWS = {'A': 'UP', 'B': 'DOWN', 'C': 'RIGHT', 'D': 'LEFT'}
# Windows console scan codes that follow a '\x00' or '\xe0' prefix
_WINDOWS_ARROWS = {'H': 'A', 'P': 'B', 'M': 'C', 'K': 'D'}
_CONTROL_KEYS = {
    ' ': 'SPACE',
    '\x03': 'QUIT',  # Ctrl+C
    '\r': 'ENTER',
    '\n': 'ENTER',
    '\x7f': 'BACKSPACE',
    '\x08': 'BACKSPACE',
    '\x1b': 'ESC',  # Lone ESC (not part of an arrow sequence)
}


def parse_keys(buffer, text=False):
    """Turn raw terminal input into a list of key names, in typing order.

    In game mode (``text=False``) 'q' means QUIT and consecutive repeats of
    the same key are collapsed, so OS key auto-repeat cannot pile up actions.
    In text mode every character is kept as typed.
    """
    keys = []
    i = 0
    length = len(buffer)
    while i < length:
        char = buffer[i]
        # Arrow keys: ESC [ A..D (normal mode) or ESC O A..D (application mode)
        if char == '\x1b' and i + 2 < length and buffer[i + 1] in '[O' and buffer[i + 2] in _ARROWS:
            key = _ARROWS[buffer[i + 2]]
            i += 3
        else:
            i += 1
            if char == 'q' and not text:
                key = 'QUIT'
            elif char in _CONTROL_KEYS:
                key = _CONTROL_KEYS[char]
            elif char.isprintable():
                key = char
            else:
                continue
        if text or not keys or keys[-1] != key:
            keys.append(key)
    return keys


def _read_pending_unix():
    """Read every byte waiting on stdin without blocking."""
    try:
        fd = sys.stdin.fileno()
        if not select.select([fd], [], [], 0)[0]:
            return ''
        return os.read(fd, 4096).decode('utf-8', errors='ignore')
    except (OSError, ValueError):
        return ''


def _read_pending_windows():
    """Drain the console input queue, translating arrows to ANSI sequences."""
    chars = []
    while msvcrt.kbhit():
        char = msvcrt.getwch()
        if char in ('\x00', '\xe0'):
            # Extended key: the next code identifies it
            arrow = _WINDOWS_ARROWS.get(msvcrt.getwch())
            if arrow:
                chars.append('\x1b[' + arrow)
        else:
            chars.append(char)
    return ''.join(chars)


_read_pending = _read_pending_windows if os.name == 'nt' else _read_pending_unix


def read_keys(text=False):
    """Return the keys pressed since the last call (possibly empty)."""
    buffer = _read_pending()
    return parse_keys(buffer, text) if buffer else []
