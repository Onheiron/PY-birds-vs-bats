"""Frame pacing: a fixed-rate render clock and the physics tick divider."""
import time

from src.core import constants, state

FPS = 60
FRAME_TIME = 1.0 / FPS

# Render frames between two physics updates at the slowest / fastest gear
MAX_FRAMES_PER_UPDATE = 10
MIN_FRAMES_PER_UPDATE = 2


class FrameClock:
    """Sleeps until the next frame deadline.

    Deadlines advance by a fixed step instead of "now + frame time", so the
    time spent drawing or an oversleep on one frame is compensated on the
    next and the average rate stays locked to ``fps``.
    """

    def __init__(self, fps=FPS, timer=time.perf_counter, sleep=time.sleep):
        self.frame_time = 1.0 / fps
        self._timer = timer
        self._sleep = sleep
        self._deadline = timer()

    def wait(self):
        """Block until the next frame is due."""
        self._deadline += self.frame_time
        delay = self._deadline - self._timer()
        if delay > 0:
            self._sleep(delay)
        elif delay < -4 * self.frame_time:
            # Long stall (suspend, slow terminal): do not fast-forward to catch up
            self._deadline = self._timer()


def frames_per_update(speed_level):
    """Render frames between physics updates for a gear (1-10).

    Gear 1:  10 frames/update = 6 updates/sec (slow)
    Gear 10:  2 frames/update = 30 updates/sec (fast but playable)
    """
    min_speed = getattr(constants.speed, 'min_speed', 1)
    max_speed = getattr(constants.speed, 'max_speed', 10)

    # Normalise the gear to 0..1
    t = (speed_level - min_speed) / (max_speed - min_speed) if max_speed > min_speed else 0
    t = max(0, min(1, t))

    frames = MAX_FRAMES_PER_UPDATE - t * (MAX_FRAMES_PER_UPDATE - MIN_FRAMES_PER_UPDATE)
    frames = max(MIN_FRAMES_PER_UPDATE, round(frames))

    # Timelapse power-up slows the simulation down
    if state.powerups.timelapse_active:
        frames = int(frames * state.powerups.timelapse_slowdown)

    return frames
