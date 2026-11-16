"""Double-buffered framebuffer with differential terminal output."""

from src.core import constants
import re
from src.entities.sprites import RESET
from src.ui.layout import TOTAL_WIDTH


class FrameBuffer:
    """
    Virtual framebuffer for differential rendering.
    Stores character and color for each cell, outputs only changed cells.
    """

    def __init__(self, width, height):
        self.width = width
        self.height = height
        # Each cell: (char, color_code)
        # Current frame being built
        self.current = [[(' ', '') for _ in range(width)] for _ in range(height)]
        # Previous frame (already displayed)
        self.previous = [[(' ', '') for _ in range(width)] for _ in range(height)]
        self.first_frame = True

    def clear(self):
        """Clear current buffer to spaces."""
        for y in range(self.height):
            for x in range(self.width):
                self.current[y][x] = (' ', '')

    def put(self, x, y, char, color=''):
        """Put a character at position with optional color."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.current[y][x] = (char, color)

    def put_string(self, x, y, text, color=''):
        """Put a string starting at position."""
        # Strip ANSI codes from text to get actual characters
        clean_text = re.sub(r'\033\[[0-9;]*m', '', text)
        for i, char in enumerate(clean_text):
            if x + i < self.width:
                self.put(x + i, y, char, color)

    def put_colored_string(self, x, y, text):
        """Put string that may contain ANSI color codes."""
        # Parse text extracting color codes and characters
        current_color = ''
        pos = 0
        i = 0
        while i < len(text):
            if text[i] == '\033':
                # Find end of ANSI sequence
                end = text.find('m', i)
                if end != -1:
                    code = text[i:end+1]
                    if code == RESET:
                        current_color = ''
                    else:
                        current_color = code
                    i = end + 1
                    continue
            # Regular character
            if x + pos < self.width and 0 <= y < self.height:
                self.current[y][x + pos] = (text[i], current_color)
            pos += 1
            i += 1

    def render(self):
        """Generate output string with only changed cells."""
        output = []
        last_color = ''

        if self.first_frame:
            # First frame: clear screen and render everything
            output.append("\033[2J\033[H")
            self.first_frame = False

            for y in range(self.height):
                output.append(f"\033[{y+1};1H")  # Move to line start
                line_chars = []
                for x in range(self.width):
                    char, color = self.current[y][x]
                    if color != last_color:
                        # Always reset first to clear any modifiers (bold/faint)
                        # then apply new color
                        if color:
                            line_chars.append(RESET + color)
                        else:
                            line_chars.append(RESET)
                        last_color = color
                    line_chars.append(char)
                output.append(''.join(line_chars))
        else:
            # Differential rendering: only output changed cells
            for y in range(self.height):
                x = 0
                while x < self.width:
                    if self.current[y][x] != self.previous[y][x]:
                        # Find run of changed cells
                        run_start = x
                        while x < self.width and self.current[y][x] != self.previous[y][x]:
                            x += 1

                        # Output this run
                        output.append(f"\033[{y+1};{run_start+1}H")
                        for rx in range(run_start, x):
                            char, color = self.current[y][rx]
                            if color != last_color:
                                # Always reset first to clear any modifiers (bold/faint)
                                # then apply new color
                                if color:
                                    output.append(RESET + color)
                                else:
                                    output.append(RESET)
                                last_color = color
                            output.append(char)
                    else:
                        x += 1

        # Reset color at end
        if last_color:
            output.append(RESET)

        # Swap buffers
        self.previous, self.current = self.current, self.previous
        # Clear new current buffer
        for y in range(self.height):
            for x in range(self.width):
                self.current[y][x] = (' ', '')

        return ''.join(output)

# Global framebuffer instance
_framebuffer = None


def get_framebuffer():
    """Get or create the global framebuffer."""
    global _framebuffer
    if _framebuffer is None:
        # Height: header(2) + game area + floor(1) + cursor(1) + notification(1) + footer(2) + extra
        total_height = constants.layout.height + 8
        # Width: game area + side panels for 16:9 widescreen
        _framebuffer = FrameBuffer(TOTAL_WIDTH, total_height)
    return _framebuffer


def reset_framebuffer():
    """Drop the global framebuffer so the next frame is a full redraw."""
    global _framebuffer
    _framebuffer = None
