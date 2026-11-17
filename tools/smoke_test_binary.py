#!/usr/bin/env python3
"""Smoke test for a standalone build: the binary must start outside the source
tree, find its bundled data files and report the right version.

Usage: python tools/smoke_test_binary.py dist/BVB
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(binary, *args, cwd):
    return subprocess.run([str(binary), *args], capture_output=True, text=True, cwd=cwd, timeout=120)


def main():
    binary = Path(sys.argv[1]).resolve()
    namespace = {}
    exec((ROOT / 'src' / '__init__.py').read_text(encoding='utf-8'), namespace)
    expected = f"BVB {namespace['__version__']}"

    with tempfile.TemporaryDirectory() as empty_dir:
        version = run(binary, '--version', cwd=empty_dir)
        assert version.returncode == 0, version.stderr
        assert version.stdout.strip() == expected, f'{version.stdout!r} != {expected!r}'

        usage = run(binary, '--help', cwd=empty_dir)
        assert usage.returncode == 0 and '--config' in usage.stdout, usage.stderr

        # A missing config is reported after the bundled defaults were located and
        # the game modules imported: this exercises the frozen import graph.
        missing = run(binary, '--config', 'missing.yml', cwd=empty_dir)
        assert missing.returncode != 0
        assert "configuration file 'missing.yml' not found" in missing.stderr, missing.stderr

        if os.name != 'nt':
            play_in_pty(binary, empty_dir)

    print(f'{binary.name}: OK ({expected})')


def play_in_pty(binary, cwd):
    """Start the binary in a pseudo-terminal, reach the title screen and quit."""
    import pty
    import select
    import time

    master, slave = pty.openpty()
    process = subprocess.Popen(
        [str(binary)], stdin=slave, stdout=slave, stderr=subprocess.PIPE, cwd=cwd, env=dict(os.environ, HOME=cwd)
    )
    os.close(slave)
    output = b''
    deadline = time.time() + 60
    try:
        while time.time() < deadline and b'NEW GAME' not in output:
            if select.select([master], [], [], 0.2)[0]:
                output += os.read(master, 65536)
            if process.poll() is not None:
                break
        assert b'NEW GAME' in output, (
            process.stderr.read().decode(errors='replace') if process.poll() else output[-400:]
        )
        os.write(master, b'\x03')
        assert process.wait(timeout=30) == 0
    finally:
        if process.poll() is None:
            process.kill()
        os.close(master)


if __name__ == '__main__':
    main()
