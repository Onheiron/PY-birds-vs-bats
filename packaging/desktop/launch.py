"""Entry point of the desktop builds (macOS app, Windows, Linux): the game in a window of its own.

``--fullscreen`` starts it full screen (F11 toggles it while playing),
``--terminal`` plays in the terminal it was started from (as game.py does).
With the environment variable BVB_OUTPUT set to a file, what the game prints
goes there (a windowed build has no console: the smoke test reads it).
"""

import os
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

    try:
        game.main()
    except SystemExit:
        raise
    except BaseException:
        _crash_log()
        raise
