"""Non-blocking keyboard input."""

import os
import sys

if os.name == 'nt':
    import msvcrt


def get_key():
    """Non-blocking key read for Windows and Unix"""
    if os.name == 'nt':
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b'\xe0':  # Arrow key prefix
                key = msvcrt.getch()
                if key == b'K':  # Left
                    return 'LEFT'
                elif key == b'M':  # Right
                    return 'RIGHT'
                elif key == b'H':  # Up
                    return 'UP'
                elif key == b'P':  # Down
                    return 'DOWN'
            elif key == b' ':  # Space
                return 'SPACE'
            elif key == b'\x03':  # Ctrl+C
                return 'QUIT'
            return None
        return None
    else:
        # Unix/macOS version - truly non-blocking with fcntl
        # Read all available input to avoid buffer buildup of repeated keys.
        # Non-blocking read will return available bytes or '' if none.
        buf = sys.stdin.read(4096)

        if not buf:
            return None

        # Parse the buffer and pick the last meaningful key event.
        last = None
        i = 0
        L = len(buf)
        while i < L:
            ch = buf[i]
            # Escape sequences (arrows) are 3 chars: \x1b[A etc.
            if ch == '\x1b' and i + 2 < L:
                seq = buf[i:i+3]
                if seq == '\x1b[D':
                    last = 'LEFT'
                    i += 3
                    continue
                elif seq == '\x1b[C':
                    last = 'RIGHT'
                    i += 3
                    continue
                elif seq == '\x1b[A':
                    last = 'UP'
                    i += 3
                    continue
                elif seq == '\x1b[B':
                    last = 'DOWN'
                    i += 3
                    continue
            # Single-char controls
            if ch == ' ':
                last = 'SPACE'
            elif ch == '\x03' or ch == 'q':
                last = 'QUIT'
            elif ch == '\r' or ch == '\n':
                last = 'ENTER'
            elif ch == '\x7f' or ch == '\x08':
                last = 'BACKSPACE'
            elif ch == '\x1b':
                # Lone ESC (not part of arrow sequence)
                last = 'ESC'
            else:
                # printable char
                if len(ch) == 1 and ch.isprintable():
                    last = ch
            i += 1

        return last
