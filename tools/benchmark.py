#!/usr/bin/env python3
"""Measure how long a frame takes (simulation + rendering), headless.

Usage: python tools/benchmark.py [--frames N] [--profile]

At 60 FPS a frame has a budget of 16.7 ms; the numbers printed here are the
share of it the game itself uses, terminal excluded.
"""

import argparse
import cProfile
import os
import pstats
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# (label, seed, level, all bird types, start next to the boss)
SCENARIOS = [
    ('Windy Woods', 1, 1, False, False),
    ('Rotten Marshes', 13, 7, True, False),
    ('Tree Boss', 5, 12, True, True),
    ('Void Cave + Owl Boss', 8, 15, True, True),
    ('Mountain Range', 11, 16, True, False),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--frames', type=int, default=3000)
    parser.add_argument('--profile', action='store_true', help='print the hottest functions')
    options = parser.parse_args()
    sys.argv = sys.argv[:1]  # the game parses the command line too
    os.environ['HOME'] = os.environ['USERPROFILE'] = tempfile.mkdtemp(prefix='bvb-bench-')

    from tests.harness import Simulation

    profiler = cProfile.Profile()
    total = 0.0
    for label, seed, level, all_birds, near_boss in SCENARIOS:
        with Simulation(seed=seed, level=level, all_birds=all_birds, near_boss=near_boss) as sim:
            sim.screen.feed = lambda data: None  # do not time the test terminal
            sim.run(100)  # warm up caches
            sent = sim.output_bytes
            if options.profile:
                profiler.enable()
            start = time.perf_counter()
            sim.run(options.frames)
            elapsed = time.perf_counter() - start
            profiler.disable()
            total += elapsed
            per_frame_us = elapsed / options.frames * 1e6
            output = (sim.output_bytes - sent) / options.frames
            print(f'{label:22s} {per_frame_us:7.0f} us/frame  {output:6.0f} bytes/frame')

    average_us = total / (options.frames * len(SCENARIOS)) * 1e6
    print(f'{"average":22s} {average_us:7.0f} us/frame  ({average_us / 16667 * 100:.1f}% of a 60 FPS frame)')
    if options.profile:
        pstats.Stats(profiler).sort_stats('tottime').print_stats(25)


if __name__ == '__main__':
    main()
