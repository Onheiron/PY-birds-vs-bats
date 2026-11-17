"""A bot that plays BVB through the real input path, with tunable skill.

Every frame the bot looks at the game state and may press one key, exactly
like a player: LEFT/RIGHT move the cursor one lane, UP bounces the falling
birds under the cursor (or fires the power of the rising ones).

How it plays:

1. Survival first. For every bird that needs a press it estimates the frames
   left before the bird is lost (floor, poison) and the frames needed to get
   there (cursor travel plus the presses the bird needs: Dinosaur, frozen and
   poisoned birds need several). The bird with the least slack goes first.
2. Height second. With no emergency it bounces the reachable falling bird
   nearest to the cursor, as early as possible: a flock that stays high
   builds momentum, gears and score.
3. Powers when idle. It fires a rising bird's power when it helps (an enemy
   ahead, a neighbour to bounce, a charge to refill) and nothing is urgent.
4. Anticipation. Otherwise it waits under the bird that will start falling
   next, and tends to dormant Orange eggs and fading Rainbow birds.

Skill is a ``Skill`` profile: keys per second, reaction time, the chance of a
wasted press. The bot uses its own random generator, so it never disturbs the
game's seeded randomness.
"""

import random
from dataclasses import dataclass, replace

from src.core import constants, state
from src.engine import bird_kinds, clock
from src.engine.birds import get_affected_lanes
from src.engine.logic.helpers import get_obstacle_lanes
from src.engine.timing import frames_per_update
from src.entities.bird_types import BirdType, get_bird_type_by_color
from src.entities.sprites import OBSTACLE_SPRITE_T1, OBSTACLE_SPRITES


@dataclass(frozen=True)
class Skill:
    """How well the bot plays."""

    key_interval: int = 1  # frames between two key presses (1 = 60 keys/s)
    reaction_frames: int = 0  # frames before it notices that a bird started falling
    miss_rate: float = 0.0  # chance that a press does nothing
    use_powers: bool = True
    anticipate: bool = True  # wait under the next bird to fall
    safety_frames: int = 6  # margin kept when judging whether a bird can wait
    # How far a bird must fall (0 = ceiling, 1 = floor) before an early bounce is
    # worth a press. Bouncing near the ceiling is wasted: the bird hits it again.
    bounce_from: float = 0.35
    # Birds only collide while rising: hold a bounce while an enemy sits above
    # the bird in its lane, unless the bird cannot wait any longer
    dodge: bool = True
    dodge_margin: int = 60  # frames of slack below which a blocked bird is bounced anyway


PROFILES = {
    # Frame-perfect, 60 keys per second: an upper bound on what the rules allow
    'perfect': Skill(),
    # A very good human: 15 keys/s, 150 ms reactions, rare slips
    'expert': Skill(key_interval=4, reaction_frames=9, miss_rate=0.02, safety_frames=10),
    # A decent player: 10 keys/s, 250 ms reactions
    'average': Skill(key_interval=6, reaction_frames=15, miss_rate=0.05, safety_frames=14),
    # Someone learning: 6 keys/s, 400 ms reactions, no powers, no anticipation
    'novice': Skill(
        key_interval=10, reaction_frames=24, miss_rate=0.1, use_powers=False, anticipate=False, safety_frames=18
    ),
}


def profile(name, **changes):
    """A named skill profile, optionally with some fields changed."""
    return replace(PROFILES[name], **changes)


# Powers that are always worth firing when the bot has time
_FREE_POWERS = {BirdType.TWISTER}
# Powers worth firing when an enemy is in the bird's lane, above it
_ATTACK_POWERS = {
    BirdType.RED,
    BirdType.BLUE,
    BirdType.STEALTH,
    BirdType.PURPLE,
    BirdType.FROSTY,
    BirdType.POISON,
    BirdType.BERSERK,
    BirdType.ROCK,
}
# Powers that help falling neighbours (bounce or slow them)
_SUPPORT_POWERS = {BirdType.WHITE: 2, BirdType.YELLOW: 1}


class Bot:
    """Decides the key to press each frame."""

    def __init__(self, skill=None, seed=0):
        self.skill = skill or PROFILES['expert']
        self.rng = random.Random(seed)
        self.cooldown = 0
        self.fall_seen = {}  # bird -> frame it was first seen falling
        self.frame = 0
        self.keys_pressed = 0

    # ------------------------------------------------------------------ helpers

    def _bindings(self):
        bindings = state.settings.key_bindings
        return bindings.get('MOVE_LEFT', 'LEFT'), bindings.get('MOVE_RIGHT', 'RIGHT'), bindings.get('BOUNCE', 'UP')

    def _frames_per_cell(self, i):
        """Frames the bird needs to move one cell, from its current speed."""
        speed = state.birds.speeds[i]
        falling = state.birds.vy[i] == 1
        special = state.special
        if falling:
            if i in special.scared_birds:
                speed += 1
            if i in special.dive_fall_boosts:
                speed += special.dive_fall_boosts[i].get('speed', 1)
            speed += 1  # winds and spells can push a fall: assume the worst
        speed = max(1, min(6, speed))
        move_interval = max(1, 6 - speed)
        return move_interval * frames_per_update(state.game.speed)

    def _presses_needed(self, i):
        special = state.special
        if i in special.frozen_birds:
            info = special.frozen_birds[i]
            return max(1, info.get('thaw_attempts_needed', 3) - info.get('thaw_attempts_done', 0))
        if get_bird_type_by_color(state.birds.colors[i]) == BirdType.DINOSAUR:
            return max(1, constants.dinosaur.presses_to_bounce - special.dinosaur_up_presses.get(i, 0))
        return 1

    def _travel_frames(self, lane):
        """Frames to bring the cursor over ``lane`` (wide cursor included)."""
        half = state.powerups.wide_cursor_lanes // 2 if state.powerups.wide_cursor_active else 0
        distance = max(0, abs(lane - state.player.lane) - half)
        return distance * self.skill.key_interval

    def _bleeding_presses_left(self, i):
        info = state.special.bleeding_birds.get(i)
        if info is None:
            return None
        return info.get('lives_needed', 3) - info.get('lives_lost', 0)

    def _harmful_press(self):
        """Would UP right now hurt a bird under the cursor?"""
        for lane in get_affected_lanes():
            for i, bird_lane in enumerate(state.birds.random_lanes):
                if bird_lane != lane or state.birds.lost[i]:
                    continue
                left = self._bleeding_presses_left(i)
                if left is not None and left <= 1:
                    return True  # this press would bleed it out
                bird_type = get_bird_type_by_color(state.birds.colors[i])
                rising = state.birds.vy[i] == -1
                if bird_type == BirdType.COOKIE and rising and not state.birds.power_used[i]:
                    return True  # Cookie power: each crumb brings it closer to death
        return False

    # ------------------------------------------------------------------ targets

    def _urgent_targets(self):
        """(slack frames, lane, bird) for every bird that needs a press."""
        targets = []
        floor = constants.layout.height - 1
        special = state.special
        now = clock.now()
        frames_per_second = 60
        spans = self._enemy_spans() if self.skill.dodge else {}
        for i in range(constants.layout.num_balls):
            if state.birds.lost[i]:
                continue
            bird_type = get_bird_type_by_color(state.birds.colors[i])
            falling = state.birds.vy[i] == 1
            poisoned = i in special.poisoned_birds

            if not falling and not poisoned:
                self.fall_seen.pop(i, None)
                continue
            if state.birds.y[i] >= 999:
                continue  # dormant Orange egg: handled when idle
            if bird_type == BirdType.CLOCKWORK and falling and special.clockwork_charge.get(i, 1) > 0:
                continue  # bounces by itself at the starting line
            if bird_type == BirdType.RAINBOW and special.rainbow_charge.get(i, 100) > 0:
                continue  # warps instead of dying
            if (i in special.scared_birds and bird_type != BirdType.PURPLE) or i in special.stunned_birds:
                continue  # cannot be bounced right now

            if falling:
                seen = self.fall_seen.setdefault(i, self.frame)
                if self.frame - seen < self.skill.reaction_frames:
                    continue
            if not falling and poisoned:
                # A rising poisoned bird only needs presses to be cured
                pass

            presses = self._presses_needed(i)
            if poisoned:
                info = special.poisoned_birds[i]
                presses = max(presses, info.get('cure_attempts_needed', 3) - info.get('cure_attempts_done', 0))

            deadline = float('inf')
            below, above = (None, False)
            if falling:
                deadline = (floor - state.birds.y[i]) * self._frames_per_cell(i)
                if self.skill.dodge:
                    below, above = self._hazards(i, spans)
                    if below is not None:
                        deadline = min(deadline, below * self._frames_per_cell(i))
            if poisoned:
                deadline = min(deadline, (special.poisoned_birds[i].get('death_time', now) - now) * frames_per_second)

            left = self._bleeding_presses_left(i)
            if left is not None:
                if left <= 1:
                    continue  # one more press kills it: let it ride
                if deadline > self.skill.safety_frames * 4:
                    continue  # bleeding: save presses for the last moment

            lane = state.birds.random_lanes[i]
            needed = self._travel_frames(lane) + presses * self.skill.key_interval
            # Worth bouncing early once it has fallen far enough or is about to pass an
            # enemy; not while an enemy above would stop it, unless time runs out
            ready = not falling or poisoned or state.birds.y[i] >= self._bounce_line() or below is not None
            if ready and above:
                ready = deadline - needed < self.skill.dodge_margin
            targets.append((deadline - needed, lane, i, ready))
        return targets

    def _enemy_spans(self):
        """lane -> [(top, bottom)] of the enemies a rising bird would hit there."""
        spans = {}
        positions = constants.layout.lane_positions
        num_lanes = constants.layout.num_lanes
        for bat in state.enemies.bats:
            for lane in range(num_lanes):
                if not (bat['x_pos'] + 8 < positions[lane] - 2 or bat['x_pos'] > positions[lane] + 2):
                    spans.setdefault(lane, []).append((bat['y_pos'], bat['y_pos'] + 1))
        for obs in state.enemies.obstacles:
            height = len(OBSTACLE_SPRITES.get(obs.get('tier', 1), OBSTACLE_SPRITE_T1))
            for lane in get_obstacle_lanes(obs):
                spans.setdefault(lane, []).append((obs['y_pos'] - 1, obs['y_pos'] + height))
        return spans

    def _hazards(self, i, spans):
        """(cells until the falling bird passes an enemy below it, enemy above it?)

        Birds only collide while rising. A bird that falls past an enemy and is
        bounced under it flies straight into it, so the bounce must come first.
        """
        if bird_kinds.is_intangible(i):
            return None, False
        y = state.birds.y[i]
        bottom_of_bird = y + bird_kinds.height(i)
        below = None
        above = False
        for top, bottom in spans.get(state.birds.random_lanes[i], ()):
            if top > bottom_of_bird:
                gap = top - bottom_of_bird
                below = gap if below is None else min(below, gap)
            elif bottom < y:
                above = True
        return below, above

    def _bounce_line(self):
        floor = constants.layout.height - 1
        return 1 + self.skill.bounce_from * (floor - 1)

    def _power_target(self):
        """Lane of a rising bird whose power is worth firing now, or None."""
        if not self.skill.use_powers:
            return None
        best = None
        enemy_lanes = self._enemy_lanes()
        for i in range(constants.layout.num_balls):
            if state.birds.lost[i] or state.birds.vy[i] != -1 or state.birds.power_used[i]:
                continue
            lane = state.birds.random_lanes[i]
            if lane in state.spells.silenced_lanes or i in state.special.poisoned_birds:
                continue
            bird_type = get_bird_type_by_color(state.birds.colors[i])
            useful = False
            if bird_type in _FREE_POWERS:
                useful = True
            elif bird_type in _ATTACK_POWERS:
                useful = lane in enemy_lanes.get(i, ())
            elif bird_type in _SUPPORT_POWERS:
                reach = _SUPPORT_POWERS[bird_type]
                useful = self._falling_neighbour(lane, reach)
            elif bird_type == BirdType.CLOCKWORK:
                useful = state.special.clockwork_charge.get(i, 3) < getattr(constants.clockwork, 'max_charge', 3)
            if useful:
                cost = self._travel_frames(lane)
                if best is None or cost < best[0]:
                    best = (cost, lane)
        return best[1] if best else None

    def _enemy_lanes(self):
        """For each bird, the lanes where an enemy sits above it."""
        lanes_by_bird = {}
        positions = constants.layout.lane_positions
        enemies = [(e['x_pos'] + 4, e['y_pos']) for e in state.enemies.bats]
        enemies += [(e['x_pos'], e['y_pos']) for e in state.enemies.mini_bats]
        enemies += [(positions[o['lane']], o['y_pos']) for o in state.enemies.obstacles if 'lane' in o]
        if state.enemies.boss is not None:
            boss = state.enemies.boss
            enemies.append((boss.get('x_pos', 0) + 8, boss.get('y_pos', 0)))
        for i in range(constants.layout.num_balls):
            lane = state.birds.random_lanes[i]
            x = positions[lane]
            if any(abs(ex - x) <= 3 and ey < state.birds.y[i] for ex, ey in enemies):
                lanes_by_bird[i] = (lane,)
        return lanes_by_bird

    def _falling_neighbour(self, lane, reach):
        for i, bird_lane in enumerate(state.birds.random_lanes):
            if state.birds.lost[i] or bird_lane == lane or abs(bird_lane - lane) > reach:
                continue
            if state.birds.vy[i] == 1:
                return True
        return False

    def _idle_lane(self):
        """Where to wait: dormant eggs, fading Rainbows, then the next bird to fall."""
        special = state.special
        for i in range(constants.layout.num_balls):
            if state.birds.lost[i]:
                continue
            bird_type = get_bird_type_by_color(state.birds.colors[i])
            if bird_type == BirdType.ORANGE and state.birds.y[i] >= 999:
                return state.birds.random_lanes[i], True  # press to try to hatch it again
            if bird_type == BirdType.RAINBOW and special.rainbow_charge.get(i, 100) < 60:
                return state.birds.random_lanes[i], True  # presses may recharge it
        if not self.skill.anticipate:
            return None, False
        # The rising bird closest to the ceiling is the next one to fall
        rising = [
            (state.birds.y[i] * self._frames_per_cell(i), state.birds.random_lanes[i])
            for i in range(constants.layout.num_balls)
            if not state.birds.lost[i] and state.birds.vy[i] == -1 and state.birds.y[i] < 999
        ]
        if rising:
            return min(rising)[1], False
        return None, False

    # ------------------------------------------------------------------ decide

    def _key_towards(self, lane, press_when_there):
        left, right, up = self._bindings()
        if lane in get_affected_lanes():
            if press_when_there and not self._harmful_press():
                return up
            return None
        return left if lane < state.player.lane else right

    def decide(self):
        """The key to press this frame, or None."""
        targets = self._urgent_targets()
        if targets:
            slack, lane, _bird, _ready = min(targets)
            if slack <= self.skill.safety_frames:
                return self._key_towards(lane, True)
            # Nothing urgent: a power if there is time for it...
            power_lane = self._power_target()
            if power_lane is not None and self._travel_frames(power_lane) * 2 + self.skill.safety_frames < slack:
                key = self._key_towards(power_lane, True)
                if key is not None:
                    return key
            # ...else bounce the closest bird that has fallen far enough,
            # or wait under the one that will need it first
            ready = [t for t in targets if t[3]]
            if ready:
                _slack, lane, _bird, _ready = min(ready, key=lambda t: (self._travel_frames(t[1]), t[0]))
                return self._key_towards(lane, True)
            return self._key_towards(lane, False)

        power_lane = self._power_target()
        if power_lane is not None:
            key = self._key_towards(power_lane, True)
            if key is not None:
                return key

        lane, press = self._idle_lane()
        if lane is None:
            return None
        return self._key_towards(lane, press)

    def press(self):
        """Keys pressed this frame (at most one, respecting the key rate)."""
        self.frame += 1
        if self.cooldown > 0:
            self.cooldown -= 1
            return []
        key = self.decide()
        if key is None:
            return []
        self.cooldown = self.skill.key_interval - 1
        self.keys_pressed += 1
        if self.rng.random() < self.skill.miss_rate:
            return []  # fumbled the key: time spent, nothing happens
        return [key]
