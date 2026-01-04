#!/usr/bin/env python3
"""
Theme configuration loader for BVB game.
Loads color definitions from theme.yml and provides ANSI escape codes.
"""
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

# Cache for loaded theme
_theme_cache = None


def _load_theme_file():
    """Load theme.yml file and return as dict."""
    if yaml is None:
        print("Warning: PyYAML not installed; using default theme", file=sys.stderr)
        return {}

    # Look for theme.yml in project root
    # Try multiple locations
    possible_paths = [
        os.path.join(os.getcwd(), 'theme.yml'),
        os.path.join(os.path.dirname(__file__), '..', '..', 'theme.yml'),
    ]

    for theme_path in possible_paths:
        if os.path.exists(theme_path):
            try:
                with open(theme_path, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: Failed to load theme from {theme_path}: {e}", file=sys.stderr)

    return {}


def _get_theme():
    """Get cached theme or load it."""
    global _theme_cache
    if _theme_cache is None:
        _theme_cache = _load_theme_file()
    return _theme_cache


def _code_to_ansi(code):
    """Convert a color code to ANSI escape sequence.

    Args:
        code: Color code. Can be:
            - Positive int (0-255): 256-color palette
            - Negative int: Basic ANSI codes (-1=red, -2=green, -3=blue, -4=cyan, -5=white)
            - String: Return as-is (already an escape sequence)

    Returns:
        ANSI escape sequence string
    """
    if isinstance(code, str):
        return code

    if code < 0:
        # Basic ANSI colors
        basic_codes = {
            -1: "\033[31m",   # red
            -2: "\033[32m",   # green
            -3: "\033[34m",   # blue
            -4: "\033[96m",   # cyan (light)
            -5: "\033[97m",   # white (bright)
        }
        return basic_codes.get(code, "\033[0m")

    # 256-color palette
    return f"\033[38;5;{code}m"


def get_color(category, name, default=None):
    """Get a single color from theme.

    Args:
        category: Top-level category (e.g., 'birds', 'panels')
        name: Color name within category (e.g., 'default', 'border')
        default: Default color code if not found

    Returns:
        ANSI escape sequence string
    """
    theme = _get_theme()
    cat = theme.get(category, {})

    if isinstance(cat, dict):
        code = cat.get(name, default)
    else:
        code = default

    if code is None:
        return "\033[0m"  # Reset/default

    return _code_to_ansi(code)


def get_gradient(category, name='gradient'):
    """Get a gradient (list of colors) from theme.

    Args:
        category: Top-level category (e.g., 'gauge', 'momentum')
        name: Gradient name within category (default: 'gradient')

    Returns:
        List of ANSI escape sequence strings
    """
    theme = _get_theme()
    cat = theme.get(category, {})

    if isinstance(cat, dict):
        codes = cat.get(name, [])
    else:
        codes = []

    if not codes:
        return ["\033[0m"]  # Return single reset color

    return [_code_to_ansi(c) for c in codes]


def get_base_color(name, default=None):
    """Shorthand to get a base color.

    Args:
        name: Color name (e.g., 'yellow', 'red', 'white')
        default: Default color code if not found

    Returns:
        ANSI escape sequence string
    """
    return get_color('base', name, default)


# Pre-load common colors for easy import
def _init_colors():
    """Initialize commonly used color constants."""
    colors = {}

    # Base colors
    base = _get_theme().get('base', {})
    for name, code in base.items():
        colors[name.upper()] = _code_to_ansi(code)

    # Always ensure RESET is available
    colors['RESET'] = "\033[0m"

    return colors


# Export commonly used colors as module-level constants
_colors = _init_colors()
RED = _colors.get('RED', "\033[31m")
GREEN = _colors.get('GREEN', "\033[32m")
BLUE = _colors.get('BLUE', "\033[34m")
CYAN = _colors.get('CYAN', "\033[96m")
WHITE = _colors.get('WHITE', "\033[97m")
YELLOW = _colors.get('YELLOW', "\033[38;5;220m")
BLACK = _colors.get('BLACK', "\033[38;5;16m")
DARK_GRAY = _colors.get('DARK_GRAY', "\033[38;5;240m")
RESET = "\033[0m"
