"""Control profiles: what the on-screen hints call each action.

Hints are templates: ``"{navigate} Navigate  {select} Select  {back} Back"``.
``hint()`` fills them in with the labels of the active profile:

- keyboard: the keys (with the player's key bindings): ↑↓ ⏎ ESC SPC...
- xbox / steamdeck: [A] [B] [X] [Y], LB/RB or L1/R1, [Menu];
- playstation: ✕ ○ □ △, L1/R1, [Options].

The profile is the ``controls_profile`` setting (SETTINGS > CONTROLS > BUTTON
LABELS); 'auto' follows the device used last: the keyboard, or the kind of
gamepad (src/ui/window.py tells which). In a terminal it is always the
keyboard.
"""

import re

from src.core import state

PROFILES = ('auto', 'keyboard', 'xbox', 'playstation', 'steamdeck')
PROFILE_NAMES = {
    'auto': 'AUTO',
    'keyboard': 'KEYBOARD',
    'xbox': 'XBOX',
    'playstation': 'PLAYSTATION',
    'steamdeck': 'STEAM DECK',
}

_KEY_SYMBOLS = {'LEFT': '←', 'RIGHT': '→', 'UP': '↑', 'DOWN': '↓', 'SPACE': 'SPC', 'ENTER': '⏎'}

_PAD = {
    'navigate': '↑↓',
    'change': '←→',
    'scroll': '↑↓',
    'select': '[A]',
    'confirm': '[A]',
    'back': '[B]',
    'delete': '[B]',
    'reroll': '[X]',
    'skip': '[Y]',
    'bounce': '[A]',
    'swap': '[B]',
    'move': '←→ LB/RB',
    'pause': '[Menu]',
    'mute': '[X]',
    'xp': '[Y]',
    'rebind': '[A]',
    'quit': '[Menu]',
}

LABELS = {
    'xbox': _PAD,
    'steamdeck': dict(_PAD, move='←→ L1/R1'),
    'playstation': dict(
        _PAD,
        select='✕',
        confirm='✕',
        back='○',
        delete='○',
        reroll='□',
        skip='△',
        bounce='✕',
        swap='○',
        move='←→ L1/R1',
        pause='[Options]',
        quit='[Options]',
        mute='□',
        xp='△',
        rebind='✕',
    ),
}


def _key(control, default):
    key = state.settings.key_bindings.get(control, default)
    return _KEY_SYMBOLS.get(key, key)


def keyboard_labels():
    """Keyboard labels, with the player's key bindings."""
    return {
        'navigate': '↑↓',
        'change': '←→',
        'scroll': '↑↓',
        'select': '⏎',
        'confirm': '⏎',
        'back': 'ESC',
        'delete': '⌫',
        'reroll': 'R',
        'skip': 'S',
        'bounce': _key('BOUNCE', 'UP'),
        'swap': _key('SWAP', 'SPACE'),
        'move': _key('MOVE_LEFT', 'LEFT') + _key('MOVE_RIGHT', 'RIGHT'),
        'pause': 'P',
        'mute': 'M',
        'xp': 'X',
        'rebind': '⏎',
        'quit': 'Q',
    }


def active_profile():
    """The profile in use: the setting, or (auto) the device used last."""
    chosen = getattr(state.settings, 'controls_profile', 'auto')
    if chosen != 'auto':
        return chosen
    from src.ui import window

    if window.active():
        return window.get().last_device
    return 'keyboard'


def labels(profile=None):
    profile = profile or active_profile()
    return LABELS.get(profile) or keyboard_labels()


def label(action, profile=None):
    return labels(profile).get(action, action)


def hint(template, profile=None):
    """``template`` with every {action} replaced by its label in the active profile
    (anything else in braces is left as it is)."""
    names = labels(profile)
    return re.sub(r'\{(\w+)\}', lambda m: names.get(m.group(1), m.group(0)), template)


def cycle_profile(delta=1):
    current = getattr(state.settings, 'controls_profile', 'auto')
    index = PROFILES.index(current) if current in PROFILES else 0
    state.settings.controls_profile = PROFILES[(index + delta) % len(PROFILES)]


def profile_name():
    return PROFILE_NAMES.get(getattr(state.settings, 'controls_profile', 'auto'), 'AUTO')
