"""Runs the real program in a pseudo-terminal, driving it with key presses."""

import os
import re
import select
import signal
import struct
import subprocess
import sys
import time

import pytest

from tests.conftest import ROOT
from tests.harness import Screen

pytestmark = pytest.mark.skipif(os.name == 'nt', reason='needs a POSIX pseudo-terminal')

COLUMNS, ROWS = 200, 60


class GameProcess:
    """The game attached to a pty, with its screen reconstructed from the output."""

    def __init__(self, tmp_path, *args):
        import fcntl
        import pty
        import termios

        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', ROWS, COLUMNS, 0, 0))
        env = dict(os.environ, HOME=str(tmp_path), TERM='xterm-256color', COLUMNS=str(COLUMNS), LINES=str(ROWS))
        self.process = subprocess.Popen(
            [sys.executable, str(ROOT / 'game.py'), *args],
            stdin=slave,
            stdout=slave,
            stderr=subprocess.PIPE,
            cwd=tmp_path,  # not the project root: data files must still be found
            env=env,
            start_new_session=True,
        )
        os.close(slave)
        self.raw = ''
        self.screen = Screen(COLUMNS, ROWS)

    def pump(self, seconds):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if select.select([self.master], [], [], 0.05)[0]:
                try:
                    data = os.read(self.master, 65536).decode('utf-8', errors='replace')
                except OSError:
                    break
                self.raw += data
                self.screen.feed(data)

    def wait_for(self, text, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.pump(0.1)
            if text in self.screen.text():
                return
            if self.process.poll() is not None:
                break
        raise AssertionError(f'{text!r} never appeared. stderr: {self.stderr()}\n{self.screen.text()}')

    def wait_exit(self, timeout=15):
        """Wait for the process to end, draining its output meanwhile.

        A pty has a small buffer (about 1 KB on macOS): if nobody reads it, the
        game blocks writing its last frames and never gets to exit.
        """
        deadline = time.time() + timeout
        while self.process.poll() is None and time.time() < deadline:
            self.pump(0.1)
        self.pump(0.2)
        if self.process.poll() is None:
            raise AssertionError(f'game did not exit within {timeout}s\n{self.screen.text()}')
        return self.process.returncode

    def send(self, keys):
        os.write(self.master, keys.encode())

    def stderr(self):
        if self.process.poll() is None:
            return ''
        return self.process.stderr.read().decode(errors='replace')

    def close(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGKILL)
        self.process.wait()
        self.process.stderr.close()
        os.close(self.master)


@pytest.fixture
def game(tmp_path):
    process = GameProcess(tmp_path)
    yield process
    process.close()


def test_play_a_session_and_quit_cleanly(game):
    game.wait_for('NEW GAME')
    assert '\033[?1049h' in game.raw  # alternate screen
    assert '\033[?25l' in game.raw  # cursor hidden

    game.send('\r')  # NEW GAME (a fresh home: no game to CONTINUE)
    game.wait_for('PRESTIGE')
    game.wait_for('MPH')

    # Play for a moment: move, bounce, swap
    for keys in ('\x1b[C', '\x1b[A', '\x1b[D\x1b[A', ' ', '\x1b[C', ' ', '\x1b[A'):
        game.send(keys)
        game.pump(0.15)

    game.send('p')
    game.wait_for('RESUME')
    game.send('p')
    game.pump(0.3)

    game.send('q')
    assert game.wait_exit() == 0, game.stderr()
    # Terminal handed back as it was: cursor visible, alternate screen left;
    # then, on the normal screen, where the game was recorded
    restored, _, after = game.raw.rpartition('\033[?25h\033[?1049l')
    assert restored
    assert 'Last game recorded:' in after
    assert 'Traceback' not in game.stderr()


def test_quit_from_title_screen(game):
    game.wait_for('NEW GAME')
    game.send('\x03')  # Ctrl+C arrives as a key in raw mode
    assert game.wait_exit() == 0, game.stderr()


def test_unknown_config_reports_a_clear_error(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / 'game.py'), '--config', 'missing.yml'],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=dict(os.environ, HOME=str(tmp_path)),
        timeout=30,
    )
    assert result.returncode != 0
    assert re.search(r"ERROR: configuration file 'missing.yml' not found", result.stderr)
    assert 'Traceback' not in result.stderr


def test_version_flag(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / 'game.py'), '--version'], capture_output=True, text=True, cwd=tmp_path, timeout=30
    )
    from src import __version__

    assert result.returncode == 0
    assert result.stdout.strip() == f'BVB {__version__}'


def test_watch_the_bot_play(tmp_path):
    game = GameProcess(tmp_path, '--bot', 'perfect', '--speed', '4')
    try:
        game.wait_for('BOT perfect is playing')
        game.wait_for('MPH')
        game.send('+')
        game.wait_for('x8')
        game.send('b')
        game.wait_for('YOU are playing')
        game.send('q')
        assert game.wait_exit() == 0, game.stderr()
    finally:
        game.close()
