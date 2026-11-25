"""``bvb`` (or ``python -m birds_vs_bats``): runs the game from this folder.

The game's code is the ``src`` package next to this file, with its data files
(configuration, themes, music samples, fonts) beside it, as in the repository.
This folder goes first on the import path, so ``src`` is the game's own.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import game

    game.main()


if __name__ == '__main__':
    main()
