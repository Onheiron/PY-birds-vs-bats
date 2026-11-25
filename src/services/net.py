"""HTTPS for the game (the updater, the online leaderboards): certificates that work everywhere.

A bundled Python (PyInstaller, above all the Steam Linux build made in the Steam
Runtime) looks for the system's certificates where the build machine kept them,
which may not exist on the player's computer (the Steam Deck): every HTTPS
request then fails. The certifi bundle shipped with the game is used instead,
when there is one.
"""

import ssl
import urllib.error
import urllib.request

_context = None


def context():
    global _context
    if _context is None:
        try:
            import certifi

            _context = ssl.create_default_context(cafile=certifi.where())
        except (ImportError, OSError, ssl.SSLError):
            _context = ssl.create_default_context()
    return _context


def urlopen(request, timeout):
    """Open ``request`` with the certifi certificates; when they do not do (a network with its own
    certificates: a company proxy), with the system's."""
    try:
        return urllib.request.urlopen(request, timeout=timeout, context=context())  # noqa: S310 (https, fixed hosts)
    except urllib.error.URLError as error:
        if not isinstance(getattr(error, 'reason', None), ssl.SSLError):
            raise
        return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310
