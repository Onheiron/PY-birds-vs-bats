"""Default end-of-biome boss (scream attack)."""

from src.core import constants
from src.core import state
from src.engine.logic.bosses.common import _get_boss_config
from src.engine.logic.helpers import _set_ball_vy
from src.engine.logic.sfx import play_sfx


def _boss_start_scream(boss):
    """Start boss scream attack."""
    boss['state'] = 'screaming'
    boss['scream_timer'] = 15  # Scream duration in frames

    # Play scream SFX
    play_sfx('boss_scream')

    # Apply scare effect to all birds below the boss
    boss_cfg = _get_boss_config()
    scream_cfg = getattr(boss_cfg, 'scream', None)
    scare_duration = getattr(scream_cfg, 'scare_duration', 1.5) if scream_cfg else 1.5
    scare_frames = int(scare_duration / constants.timing.base_sleep)

    boss_bottom = boss['y_pos'] + 3  # Boss is 3 lines tall

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        bird_y = state.birds.y[i]

        # Only affect birds below the boss
        if bird_y > boss_bottom:
            # Bounce bird down
            if state.birds.vy[i] == -1:
                _set_ball_vy(i, 1)

            # Apply scare effect (like tier 1 bat)
            state.special.scared_birds[i] = scare_frames
