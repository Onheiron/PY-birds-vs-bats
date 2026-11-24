"""Entry point of the Steam build: the game in its own window, full screen.

``--window`` keeps it in a window instead of full screen, ``--terminal`` plays
in the terminal it was started from (as game.py does).
"""

import sys

if __name__ == '__main__':
    args = sys.argv[1:]
    if '--terminal' in args:
        args.remove('--terminal')
    elif '--window' not in args and '--fullscreen' not in args:
        args.append('--fullscreen')
    sys.argv[1:] = args
    import game

    game.main()
