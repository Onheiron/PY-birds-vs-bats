"""Test setup: an isolated home directory and a predictable environment.

The game reads its configuration at import time and stores saves under the
user's home, so both are pinned down before any game module is imported.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_home = tempfile.mkdtemp(prefix='bvb-test-home-')
os.environ['HOME'] = _home
os.environ['USERPROFILE'] = _home
os.environ.pop('COLORTERM', None)
os.environ.pop('BVB_THEME_PATH', None)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
