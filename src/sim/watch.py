"""Watch the bot play, in the terminal, in real time (or faster, or slower).

    python3 game.py --bot expert
    python3 game.py --bot perfect --speed 4 --start-level 10
    python3 game.py --bot novice --seed 7 --games 3

While watching:
    + / -    faster / slower (x0.25 ... x16)
    B        take over the controls, or hand them back to the bot
    P        pause menu (the bot waits)
    Q        quit

A game shown here is the very game tools/simulate.py measures for the same
seed and options: both drive the game frame by frame on the same virtual clock.
"""

import argparse
import time

from src.core import state
from src.engine import input_handler
from src.engine.timing import FrameClock
from src.services import optional, sound
from src.sim.options import DIFFICULTIES, add_game_options, formation_from, overrides_from, skill_from
from src.sim.runner import FRAME_DT, RunConfig, end_reason, start_game
from src.ui import framebuffer, keyboard, render, terminal
from src.ui.layout import TOTAL_WIDTH

SPEEDS = (0.25, 0.5, 1, 2, 4, 8, 16)
STATUS_COLOR = "\033[38;5;250m"
HIGHLIGHT = "\033[38;5;220m"


def build_parser():
    parser = argparse.ArgumentParser(
        prog='game.py --bot PROFILE',
        description='Watch the bot play BVB.',
        epilog='Keys while watching: +/- speed, B take over, P pause, Q quit.',
    )
    add_game_options(parser)
    parser.add_argument('--speed', type=float, default=1, help='game speed multiplier (default 1)')
    parser.add_argument('--games', type=int, default=1, help='games to play back to back, seeds seed, seed+1, ...')
    parser.add_argument('--sound', action='store_true', help='play sound effects (off by default)')
    parser.add_argument('--config', help=argparse.SUPPRESS)  # read by the game at startup
    parser.add_argument('--theme', help=argparse.SUPPRESS)
    return parser


class VirtualTime:
    """Game time advancing by whole frames, like in the simulator."""

    def __init__(self, start=1_700_000_000.0):
        self.now = start

    def __call__(self):
        return self.now


class Watch:
    def __init__(self, args, config):
        self.args = args
        self.config = config
        self.speed = min(SPEEDS, key=lambda s: abs(s - args.speed))
        self.human = False
        self.quit = False
        self.credit = 0.0  # fraction of a game frame owed to the next render frame

    # ------------------------------------------------------------------ input

    def handle_keys(self, bot):
        for key in keyboard.read_keys():
            if key == 'QUIT':
                self.quit = True
                return
            if key in ('+', '='):
                self.speed = SPEEDS[min(len(SPEEDS) - 1, SPEEDS.index(self.speed) + 1)]
            elif key in ('-', '_'):
                self.speed = SPEEDS[max(0, SPEEDS.index(self.speed) - 1)]
            elif key in ('b', 'B') and not state.game.paused:
                self.human = not self.human
                bot.cooldown = 0
            elif self.human or state.game.paused or key in ('p', 'P'):
                input_handler.process_input(key)

    # ------------------------------------------------------------------ drawing

    def draw_status(self, fb):
        who = 'YOU are playing' if self.human else f'BOT {self.args.bot} is playing'
        left = f" {who}  |  x{self.speed:g}  |  seed {self.config.seed}  |  {self.args.difficulty}"
        right = "+/- speed   B take over   P pause   Q quit "
        y = fb.height - 1
        fb.fill(0, y, fb.width)
        fb.put_string(0, y, left, HIGHLIGHT)
        fb.put_string(max(len(left) + 2, TOTAL_WIDTH - len(right)), y, right, STATUS_COLOR)

    def draw_result(self, end, minutes):
        lines = [
            f"{end.upper()}",
            f"level {state.game.level}   score {int(state.game.score):,}   {minutes:.1f} min of play",
            "next game in a moment" if self.more_games else "press any key",
        ]
        width = max(len(line) for line in lines) + 6

        def overlay(fb):
            x = (TOTAL_WIDTH - width) // 2
            y = fb.height // 2 - 3
            fb.put_string(x, y, "╔" + "═" * (width - 2) + "╗", HIGHLIGHT)
            for i, line in enumerate(lines, 1):
                fb.put_string(x, y + i, "║" + line.center(width - 2) + "║", HIGHLIGHT)
            fb.put_string(x, y + len(lines) + 1, "╚" + "═" * (width - 2) + "╝", HIGHLIGHT)

        return overlay

    # ------------------------------------------------------------------ loop

    def play(self, virtual, more_games):
        self.more_games = more_games
        bot, session = start_game(self.config, virtual.now)
        framebuffer.reset_framebuffer()
        render.OVERLAYS[:] = [self.draw_status]
        clock = FrameClock()
        frames = 0
        end = None

        while not self.quit:
            self.handle_keys(bot)
            if self.quit:
                break
            self.credit += self.speed
            while self.credit >= 1 and end is None:
                self.credit -= 1
                if not self.human and not state.game.paused:
                    for key in bot.press():
                        input_handler.process_input(key)
                session.step()
                frames += 1
                end = end_reason(self.config)
                virtual.now += FRAME_DT
            if state.ui.show_title:
                # MAIN MENU from the pause menu: leave the game
                end = end or 'left the game'
            render.render_game()
            if end:
                break
            clock.wait()

        if end and not self.quit:
            render.OVERLAYS.append(self.draw_result(end, frames * FRAME_DT / 60))
            self.show_result(clock)
        return end, frames * FRAME_DT / 60

    def show_result(self, clock):
        deadline = time.perf_counter() + 3
        while not self.quit:
            keys = keyboard.read_keys()
            if keys:
                self.quit = 'QUIT' in keys
                if not self.more_games or self.quit:
                    return
            if self.more_games and time.perf_counter() >= deadline:
                return
            render.render_game()
            clock.wait()


def main(argv):
    args = build_parser().parse_args(argv)
    if not args.sound:
        sound._backend = None
    optional.firebase_client = None  # never send scores from bot games

    results = []
    real_time = time.time
    terminal.setup()
    try:
        for game in range(max(1, args.games)):
            config = RunConfig(
                seed=args.seed + game,
                difficulty=DIFFICULTIES[args.difficulty],
                skill=skill_from(args),
                overrides=overrides_from(args),
                formation=formation_from(args),
                start_level=args.start_level,
            )
            watch = Watch(args, config)
            virtual = VirtualTime()
            time.time = virtual
            end, minutes = watch.play(virtual, more_games=game + 1 < args.games)
            time.time = real_time
            results.append((config.seed, end or 'quit', state.game.level, int(state.game.score), minutes))
            if watch.quit:
                break
    finally:
        time.time = real_time
        render.OVERLAYS.clear()
        terminal.cleanup()

    for seed, end, level, score, minutes in results:
        print(f"seed {seed}: {end}, level {level}, score {score:,}, {minutes:.1f} min of play")
