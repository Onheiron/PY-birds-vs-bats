"""Double-buffered framebuffer with differential terminal output."""
import re

from src.entities.sprites import RESET
from src.ui.layout import TOTAL_WIDTH

_ANSI_SGR = re.compile(r'\033\[[0-9;]*m')

# A cell is a (char, color_code) tuple. BLANK is shared by every empty cell.
BLANK = (' ', '')


class FrameBuffer:
    """Virtual framebuffer for differential rendering.

    Layers draw into ``current``; ``render()`` emits only the cells that differ
    from ``previous`` (what the terminal already shows) and swaps the buffers.
    Rows are plain lists of cells so layers may slice-assign whole runs.
    """

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self._blank_row = [BLANK] * width
        # Current frame being built
        self.current = [self._blank_row[:] for _ in range(height)]
        # Previous frame (already displayed)
        self.previous = [self._blank_row[:] for _ in range(height)]
        self.first_frame = True

    def clear(self):
        """Clear current buffer to spaces."""
        blank = self._blank_row
        for row in self.current:
            row[:] = blank

    def invalidate(self):
        """Discard what was drawn so far and force a full redraw on next render."""
        self.first_frame = True
        self.clear()

    def put(self, x, y, char, color=''):
        """Put a character at position with optional color."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.current[y][x] = (char, color)

    def put_cells(self, x, y, cells):
        """Blit a pre-built run of cells; the run must fit inside the row."""
        self.current[y][x:x + len(cells)] = cells

    def fill(self, x, y, count, cell=BLANK):
        """Fill ``count`` cells of a row with the same cell, clipped to the buffer."""
        if not 0 <= y < self.height:
            return
        start = max(0, x)
        end = min(self.width, x + count)
        if start < end:
            self.current[y][start:end] = [cell] * (end - start)

    def put_string(self, x, y, text, color=''):
        """Put a string starting at position (embedded ANSI codes are dropped)."""
        if not 0 <= y < self.height:
            return
        if '\033' in text:
            text = _ANSI_SGR.sub('', text)
        end = x + len(text)
        if end > self.width:
            text = text[:self.width - x]
            end = self.width
        if x < 0:
            text = text[-x:]
            x = 0
        if x < end:
            self.current[y][x:end] = [(char, color) for char in text]

    def put_colored_string(self, x, y, text):
        """Put string that may contain ANSI color codes."""
        if not 0 <= y < self.height:
            return
        row = self.current[y]
        width = self.width
        current_color = ''
        pos = x
        i = 0
        length = len(text)
        while i < length:
            char = text[i]
            if char == '\033':
                # Find end of ANSI sequence
                end = text.find('m', i)
                if end != -1:
                    code = text[i:end + 1]
                    current_color = '' if code == RESET else code
                    i = end + 1
                    continue
            if 0 <= pos < width:
                row[pos] = (char, current_color)
            pos += 1
            i += 1

    def render(self):
        """Generate output string with only changed cells and swap buffers."""
        output = []
        append = output.append
        last_color = ''
        width = self.width
        current = self.current
        previous = self.previous

        if self.first_frame:
            # First frame: clear screen and render everything
            append("\033[2J\033[H")
            self.first_frame = False
            for y, row in enumerate(current):
                append(f"\033[{y + 1};1H")
                for char, color in row:
                    if color != last_color:
                        # Always reset first to clear any modifier (bold/faint)
                        append(RESET + color)
                        last_color = color
                    append(char)
        else:
            # Differential rendering: only output runs of changed cells
            for y, row in enumerate(current):
                prev_row = previous[y]
                if row == prev_row:
                    continue
                x = 0
                while x < width:
                    if row[x] == prev_row[x]:
                        x += 1
                        continue
                    append(f"\033[{y + 1};{x + 1}H")
                    while x < width:
                        cell = row[x]
                        if cell == prev_row[x]:
                            break
                        color = cell[1]
                        if color != last_color:
                            append(RESET + color)
                            last_color = color
                        append(cell[0])
                        x += 1

        # Reset color at end
        if last_color:
            append(RESET)

        # Swap buffers and start the next frame from a blank canvas
        self.previous, self.current = current, previous
        self.clear()

        return ''.join(output)


# Global framebuffer instance
_framebuffer = None


def get_framebuffer():
    """Get or create the global framebuffer."""
    global _framebuffer
    if _framebuffer is None:
        from src.core import constants
        # Height: header + game area + floor + cursor + notification + footer + extra
        total_height = constants.layout.height + 8
        # Width: game area + side panels for 16:9 widescreen
        _framebuffer = FrameBuffer(TOTAL_WIDTH, total_height)
    return _framebuffer


def reset_framebuffer():
    """Drop the global framebuffer so the next frame is a full redraw."""
    global _framebuffer
    _framebuffer = None
