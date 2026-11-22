"""Recording a game and replaying it gives the very same game."""

import copy
import json
import time

from src.core import constants, state
from src.engine import input_handler, loop, meta, recorder
from src.sim import runner
from src.sim.bot import PROFILES, Bot


def record_bot_game(seed=7, frames=60 * 90):
    """Play like game.py does (state.init, then the session loop), with the bot's keys."""
    real_time = time.time
    clock_now = [1_800_000_000.0]
    clock = recorder.FrameTime(real=lambda: clock_now[0])
    time.time = clock
    try:
        constants.configure(1)
        clock.tick()
        state.init(seed)
        state.settings.bounce_on_enter = state.settings.trigger_on_enter = False
        state.meta.profile = meta.new_profile()
        init_time = state.game.start_time
        profile = copy.deepcopy(state.meta.profile)
        meta.start_run()
        state.ui.show_title = False
        state.ui.menu_stack = []
        clock_now[0] += 0.7  # time spent between the menu and the first frame
        state.game.start_time = state.game.last_mile_update = clock.tick()
        record = recorder.Recorder(init_time, state.game.start_time, profile)
        bot = Bot(PROFILES['expert'], seed=seed)
        pause_keys = {}
        session = loop.Session()
        for n in range(frames):
            # Real frames are not exactly 1/60 s apart
            clock_now[0] += 1 / 60 + (0.004 if n % 7 == 0 else 0)
            # A pause now and then: P, some frames (and minutes) later P again
            if n % 1500 == 700 and state.choice.active is None and not state.game.paused:
                pause_keys[n] = ['p']
                pause_keys[n + 400] = ['p']
            if n % 1500 == 900:
                clock_now[0] += 120  # two minutes away from the keyboard, paused
            held = state.game.paused or state.choice.active is not None
            now = clock.tick(held)
            keys = pause_keys.pop(n, None) or ([] if state.game.paused else bot.press())
            record.frame(now, keys, held)
            for key in keys:
                input_handler.process_input(key)
            session.step()
            if state.game.game_over:
                break
        result = (state.game.level, int(state.game.score), state.game.miles, state.game.lives)
        data = dict(record.header, times=record.times, keys=record.keys)
        return json.loads(json.dumps(data)), result
    finally:
        time.time = real_time


def test_a_replay_ends_exactly_like_the_recorded_game():
    data, result = record_bot_game()
    assert data['keys'], 'the bot pressed keys'
    runner.replay(data)
    assert (state.game.level, int(state.game.score), state.game.miles, state.game.lives) == result


def test_pauses_are_not_recorded():
    data, _result = record_bot_game(frames=60 * 60)
    times = data['times']
    # Several pauses of two minutes each, yet the recording spans about a minute
    assert times[-1] - times[0] < 70
    assert len(times) < 60 * 60


def test_games_loaded_from_a_save_are_not_recorded():
    state.init(3)
    state.game.frame_count = 500
    record = recorder.Recorder(0.0, 0.0, {})
    record.frame(1.0, ['UP'])
    assert record.save() is None
