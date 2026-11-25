"""The name entry at game over: typed keys, and the on-screen keyboard for gamepads."""

from src.ui.game_over import KEYBOARD_ROWS, name_entry_key


def press(keys, name='', cursor=(0, 0), lower=False, max_length=20):
    done = None
    for key in keys:
        name, cursor, lower, done = name_entry_key(name, key, cursor, lower, max_length)
        if done is not None:
            break
    return name, cursor, lower, done


def test_typing_on_a_keyboard_still_works():
    assert press(list('Bob') + ['BACKSPACE', 'SPACE', 'ENTER']) == ('Bo ', (0, 0), False, 'Bo ')
    assert press(['x', 'ESC'])[3] == ''


def test_the_on_screen_keyboard_types_moves_and_confirms():
    # B is right of A; down to N; the bottom row has the case switch, space, delete and OK
    name, cursor, lower, done = press(['RIGHT', 'PICK', 'DOWN', 'LEFT', 'PICK'])
    assert name == 'BN' and done is None
    bottom = len(KEYBOARD_ROWS) - 1
    name, cursor, lower, done = press(['PICK'], name, (bottom, 0))  # aA: lower case
    assert lower
    name, cursor, lower, done = press(['PICK'], name, (0, 2), lower)
    assert name == 'BNc'
    name, *_rest = press(['PICK'], name, (bottom, 2), lower)  # DEL
    assert name == 'BN'
    assert press(['PICK'], 'BN', (bottom, 3))[3] == 'BN'  # OK
    assert press(['UP'], cursor=(0, 5))[1] == (bottom, 3)  # wraps, onto the shorter row


def test_the_name_has_a_maximum_length():
    assert press(['PICK'] * 30, max_length=5)[0] == 'AAAAA'
