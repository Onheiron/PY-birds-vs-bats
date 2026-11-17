"""Frame pacing."""

import pytest

from src.core import state
from src.engine.timing import FRAME_TIME, FrameClock, frames_per_update


class FakeTime:
    def __init__(self):
        self.now = 100.0
        self.slept = []

    def timer(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def test_clock_sleeps_the_remainder_of_each_frame():
    fake = FakeTime()
    clock = FrameClock(fps=60, timer=fake.timer, sleep=fake.sleep)
    fake.now += 0.004  # frame took 4 ms to draw
    clock.wait()
    assert fake.slept == [pytest.approx(FRAME_TIME - 0.004)]


def test_clock_does_not_drift_when_sleep_overshoots():
    fake = FakeTime()

    def sloppy_sleep(seconds):
        fake.now += seconds + 0.001  # the OS wakes us 1 ms late, every time

    clock = FrameClock(fps=60, timer=fake.timer, sleep=sloppy_sleep)
    start = fake.now
    for _ in range(600):
        clock.wait()
    # 600 frames must take 10 s: lateness is absorbed, not accumulated
    assert fake.now - start == pytest.approx(10.0, abs=0.002)


def test_clock_skips_sleep_when_late_and_resyncs_after_a_stall():
    fake = FakeTime()
    clock = FrameClock(fps=60, timer=fake.timer, sleep=fake.sleep)
    fake.now += 0.020  # slightly over budget
    clock.wait()
    assert fake.slept == []

    fake.now += 5.0  # machine was suspended
    clock.wait()
    assert fake.slept == []
    # Back to normal pacing straight away, no burst of catch-up frames
    clock.wait()
    assert fake.slept == [pytest.approx(FRAME_TIME)]


def test_physics_tick_rate_follows_the_gear():
    state.powerups.timelapse_active = False
    assert frames_per_update(1) == 10
    assert frames_per_update(10) == 2
    rates = [frames_per_update(gear) for gear in range(1, 11)]
    assert rates == sorted(rates, reverse=True)
    # Out-of-range gears are clamped
    assert frames_per_update(0) == 10
    assert frames_per_update(99) == 2


def test_timelapse_slows_the_simulation():
    state.powerups.timelapse_active = True
    state.powerups.timelapse_slowdown = 2.0
    try:
        assert frames_per_update(10) == 4
    finally:
        state.powerups.timelapse_active = False
        state.powerups.timelapse_slowdown = 1.0
