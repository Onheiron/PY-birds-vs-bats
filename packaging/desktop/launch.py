"""Entry point of the desktop builds (macOS app, Windows, Linux): the game in a window of its own.

``--fullscreen`` starts it full screen (F11 toggles it while playing),
``--terminal`` plays in the terminal it was started from (as game.py does).
With the environment variable BVB_OUTPUT set to a file, what the game prints
goes there (a windowed build has no console: the smoke test reads it).
"""

import os
import sys

if __name__ == '__main__':
    out = os.environ.get('BVB_OUTPUT')
    if out:
        sys.stdout = sys.stderr = open(out, 'w', encoding='utf-8', buffering=1)  # noqa: SIM115
    args = sys.argv[1:]
    if '--terminal' in args:
        args.remove('--terminal')
    elif '--window' not in args and '--fullscreen' not in args:
        args.append('--window')
    sys.argv[1:] = args
    import game

    game.main()
