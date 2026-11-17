"""Framebuffer drawing primitives and differential output."""

import random

from src.ui.framebuffer import BLANK, FrameBuffer, RegionCache
from tests.harness import Screen

RED = '\033[31m'
BOLD_BLUE = '\033[1m\033[34m'


def row_text(fb, y):
    return ''.join(char for char, _ in fb.current[y])


def test_put_ignores_out_of_bounds():
    fb = FrameBuffer(4, 2)
    for x, y in [(-1, 0), (4, 0), (0, -1), (0, 2)]:
        fb.put(x, y, '#', RED)
    assert all(cell == BLANK for row in fb.current for cell in row)
    fb.put(3, 1, '#', RED)
    assert fb.current[1][3] == ('#', RED)


def test_put_string_clips_on_both_sides_and_strips_ansi():
    fb = FrameBuffer(6, 3)
    fb.put_string(-2, 0, 'abcdef', RED)
    assert row_text(fb, 0) == 'cdef  '
    fb.put_string(4, 1, 'wxyz')
    assert row_text(fb, 1) == '    wx'
    fb.put_string(0, 2, f'{RED}hi\033[0m!', BOLD_BLUE)
    assert row_text(fb, 2) == 'hi!   '
    assert fb.current[2][0] == ('h', BOLD_BLUE)
    # Off-screen rows and fully clipped strings are no-ops
    fb.put_string(0, 9, 'nope')
    fb.put_string(10, 0, 'nope')
    fb.put_string(-10, 0, 'nope')
    assert row_text(fb, 0) == 'cdef  '


def test_put_colored_string_tracks_embedded_colours():
    fb = FrameBuffer(5, 1)
    fb.put_colored_string(-1, 0, f'x{RED}ab\033[0mc')
    assert fb.current[0][:3] == [('a', RED), ('b', RED), ('c', '')]


def test_fill_and_put_cells():
    fb = FrameBuffer(5, 2)
    fb.fill(-2, 0, 4, ('.', RED))
    assert fb.current[0] == [('.', RED), ('.', RED), BLANK, BLANK, BLANK]
    fb.fill(0, 5, 3, ('.', RED))  # off-screen row
    fb.put_cells(1, 1, [('a', ''), ('b', '')])
    assert row_text(fb, 1) == ' ab  '


def test_first_render_draws_everything_then_only_differences():
    fb = FrameBuffer(8, 3)
    screen = Screen(8, 3)
    fb.put_string(0, 0, 'hello', RED)
    first = fb.render()
    assert first.startswith('\033[2J')
    screen.feed(first)
    assert screen.text().split('\n')[0] == 'hello'

    # Same content again: nothing to send
    fb.put_string(0, 0, 'hello', RED)
    assert fb.render() == ''

    # One changed cell: a single cursor move and one character (plus colour)
    fb.put_string(0, 0, 'hellp', RED)
    diff = fb.render()
    assert diff == f'\033[1;5H\033[0m{RED}p\033[0m'


def test_render_clears_the_canvas_for_the_next_frame():
    fb = FrameBuffer(4, 1)
    fb.put_string(0, 0, 'abcd')
    fb.render()
    assert fb.current[0] == [BLANK] * 4
    # An empty next frame erases what was on screen
    screen = Screen(4, 1)
    screen.feed('\033[1;1Habcd')
    screen.feed(fb.render())
    assert screen.text() == ''


def test_differential_output_always_matches_a_full_redraw():
    """Whatever is drawn, applying the diffs must leave the same screen as a full repaint."""
    rng = random.Random(7)
    width, height = 30, 8
    fb = FrameBuffer(width, height)
    reference = FrameBuffer(width, height)
    screen = Screen(width, height)
    colours = ['', RED, BOLD_BLUE]

    for _ in range(200):
        operations = []
        for _ in range(rng.randrange(0, 12)):
            text = ''.join(rng.choice('ab #│█') for _ in range(rng.randrange(1, 10)))
            operations.append((rng.randrange(-3, width), rng.randrange(0, height), text, rng.choice(colours)))
        for target in (fb, reference):
            for x, y, text, colour in operations:
                target.put_string(x, y, text, colour)

        screen.feed(fb.render())

        expected = Screen(width, height)
        reference.first_frame = True
        expected.feed(reference.render())
        assert screen.cells == expected.cells


def test_invalidate_forces_a_full_redraw():
    fb = FrameBuffer(3, 1)
    fb.put_string(0, 0, 'abc')
    fb.render()
    fb.put_string(0, 0, 'zzz')
    fb.invalidate()
    assert fb.current[0] == [BLANK] * 3
    assert fb.render().startswith('\033[2J')


def test_region_cache_restores_only_for_the_same_key():
    fb = FrameBuffer(6, 3)
    cache = RegionCache()
    assert cache.restore(fb, 'k', 1, 1) is False

    fb.put_string(1, 1, 'abc', RED)
    fb.put_string(1, 2, 'def', RED)
    cache.store(fb, 'k', 1, 1, 3, 2)

    fb.clear()
    assert cache.restore(fb, 'other', 1, 1) is False
    assert row_text(fb, 1) == '      '
    assert cache.restore(fb, 'k', 1, 1) is True
    assert row_text(fb, 1) == ' abc  '
    assert row_text(fb, 2) == ' def  '
    # Restored cells are copies: drawing over them must not corrupt the cache
    fb.put_string(1, 1, 'XXX')
    fb.clear()
    cache.restore(fb, 'k', 1, 1)
    assert row_text(fb, 1) == ' abc  '
