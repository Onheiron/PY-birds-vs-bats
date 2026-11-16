"""Locating data files (configs, themes, schema) in source and frozen builds."""

import os
import sys


def resource_dir():
    """Directory holding the bundled data files.

    PyInstaller unpacks them next to the code in ``sys._MEIPASS``; when running
    from source they sit in the project root.
    """
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def bundled(name):
    """Path of a data file shipped with the game."""
    return os.path.join(resource_dir(), name)


def find(name):
    """Resolve a data file: the user's copy (absolute path or current directory)
    wins over the bundled one. Returns None when neither exists."""
    for candidate in (os.path.abspath(name), bundled(name)):
        if os.path.isfile(candidate):
            return candidate
    return None
