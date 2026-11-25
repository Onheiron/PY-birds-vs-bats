"""Entry point of the Steam build: the game in its own window, full screen.

``--window`` keeps it in a window instead of full screen, ``--terminal`` plays
in the terminal it was started from (as game.py does).
"""

import sys


def _crash_log():
    """Keep what went wrong in ~/.bvb/logs/crash.txt: a windowed build has no console to show it."""
    import datetime
    import traceback
    from pathlib import Path

    try:
        folder = Path.home() / '.bvb' / 'logs'
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / 'crash.txt', 'a', encoding='utf-8') as f:
            f.write(f'--- {datetime.datetime.now().isoformat(timespec="seconds")} {sys.argv}\n')
            f.write(traceback.format_exc() + '\n')
    except OSError:
        pass


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--terminal' in args:
        args.remove('--terminal')
    elif '--window' not in args and '--fullscreen' not in args:
        args.append('--fullscreen')
    sys.argv[1:] = args
    import game

    try:
        game.main()
    except SystemExit:
        raise
    except BaseException:
        _crash_log()
        raise
