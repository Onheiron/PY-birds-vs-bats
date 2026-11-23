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
3. Powers when they count. Bouncing a bird and pressing UP again fires its
   power at once, so the question is when a power counts: a Blue or Red with an
   enemy above (a Red once its shooter neighbours rise too), a Yellow or White
   with falling neighbours. Powers under the cursor go before bounces that can
   wait; powers that need travel only when nothing needs bouncing. A rising
   White is a hub: one UP on it bounces every falling bird within two lanes,
   so the bot goes to it when it is closer than the falling bird.
4. Anticipation. Otherwise it waits under the bird that will start falling
   next, and tends to dormant Orange eggs and fading Rainbow birds.

Skill is a ``Skill`` profile: keys per second, reaction time, the chance of a
wasted press. The bot uses its own random generator, so it never disturbs the
game's seeded randomness.
"""

import random
from collections import Counter
from dataclasses import dataclass, replace

from src.core import constants, state
from src.engine import bird_kinds, clock, hazards, stats
from src.engine.birds import get_affected_lanes
from src.engine.logic.helpers import get_obstacle_lanes
from src.engine.timing import frames_per_update
from src.entities.bird_types import BirdType, get_bird_type_by_color
from src.entities.sprites import OBSTACLE_SPRITE_T1, OBSTACLE_SPRITES
from src.sim import strategy


@dataclass(frozen=True)
class Skill:
    """How well the bot plays."""

    key_interval: int = 1  # frames between two key presses (1 = 60 keys/s)
    # Two hands: LEFT/RIGHT with one, UP with the other, each at key_interval, so an
    # UP right after a move costs no extra time. False: one stream of keys
    two_hands: bool = True
    # Cursor assist of the CONTROLS menu the bot plays with: 'none', 'bounce'
    # (entering a lane bounces its falling birds) or 'trigger' (entering a lane acts as UP)
    assist: str = 'none'
    reaction_frames: int = 0  # frames before it notices that a bird started falling
    miss_rate: float = 0.0  # chance that a press does nothing
    use_powers: bool = True
    anticipate: bool = True  # wait under the next bird to fall
    safety_frames: int = 6  # margin kept when judging whether a bird can wait
    # How far a bird must fall (0 = ceiling, 1 = floor) before an early bounce is
    # worth a press. Bouncing near the ceiling is wasted: the bird hits it again.
    bounce_from: float = 0.35
    # Birds only collide while rising: hold a bounce while an enemy sits above
    # the bird in its lane, unless the bird cannot wait any longer. Off by
    # default: tools/analyze.py factors found it costs ~1.8 levels (holding
    # bounces lets birds fall too far; hitting enemies is how they die anyway)
    dodge: bool = False
    dodge_margin: int = 60  # frames of slack below which a blocked bird is bounced anyway
    # Egg cards: 'smart' (rarity, then kind), 'adaptive' (what the flock needs now), 'first', 'random'
    card_policy: str = 'smart'
    # Boss pacts: 'smart' (the one with the fewest drawbacks), 'adaptive', 'refuse', 'random'
    pact_policy: str = 'smart'

    # Strategy (see src/sim/strategy.py)
    max_gear: int = 0  # swap to shed momentum above this gear (0 = never)
    brake_when_falling: int = 0  # ...or when this many birds fall at once (0 = never)
    formation: str = (
        'none'  # 'auto' (every synergy), 'red_battery', 'yellow_guard', 'white_center', 'yellow_sides' or 'none'
    )
    formation_every: int = 600  # frames between two formation swaps
    keep_birds: int = 9  # look after at most this many birds, let the others fall
    favorites: tuple = ()  # bird kinds to protect first and to hatch
    cull_others: bool = False  # let non-favourite birds fall to free lanes for eggs
    min_lives_to_cull: int = 3  # never let birds go on purpose with this many lives or fewer
    swap_slack: int = 45  # frames of slack a strategic swap needs before the next bird is due
    # Powers
    purple_charge: float = 2.0  # seconds a Purple charges before release (0 = fire at once)
    red_battery: bool = True  # hold a Red shot until its shooter neighbours rise, unless the enemy is close
    power_travel: bool = True  # move the cursor just to fire a power (False: only powers under the cursor)
    # Seconds it keeps track of a bird it cannot see any more (dark, fog), guessing
    # where it is from where it last saw it going; then it forgets it until it sees it again
    memory: float = 2.0
    # Sweep: UP on every falling bird under the cursor, at any height. With two hands it
    # costs the moving hand nothing (arrow + UP is one decision); with one hand it is
    # done only when there is time for it
    sweep: bool = False
    # Keys of a combo played without looking (the SPACE, arrows, SPACE of a swap): frames apart
    combo_interval: int = 4


PROFILES = {
    # Frame-perfect, 60 keys per second: an upper bound on what the rules allow
    'perfect': Skill(memory=99.0),
    # Key rates are what a human keeps up for a whole game, not bursts.
    # A very good player: 7.5 keys/s, 200 ms reactions, rare slips. It arranges the
    # flock for its synergies and swaps to brake above gear 7
    'expert': Skill(
        key_interval=8,
        reaction_frames=12,
        miss_rate=0.02,
        safety_frames=12,
        formation='auto',
        max_gear=7,
        sweep=True,
        memory=3.0,
    ),
    # A decent player: 5 keys/s, 300 ms reactions; formation and brake as the expert
    'average': Skill(
        key_interval=12,
        reaction_frames=18,
        miss_rate=0.05,
        safety_frames=16,
        formation='auto',
        max_gear=7,
        sweep=True,
        memory=1.5,
    ),
    # Someone learning: 3 keys/s, 450 ms reactions, no powers, no anticipation
    'novice': Skill(
        key_interval=20,
        reaction_frames=27,
        miss_rate=0.1,
        use_powers=False,
        anticipate=False,
        safety_frames=20,
        memory=0.5,
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
        self.up_cooldown = 0  # the UP hand, when playing with two hands
        self.chasing = None  # the bird the cursor is running for
        self.view = {}  # bird -> (y, vy) it sees or remembers this frame
        self.memory = {}  # bird -> where it last saw it
        self.lit = None  # darkness this frame: (lane, row) -> level (None: no darkness)
        self.fall_seen = {}  # bird -> frame it was first seen falling
        self.frame = 0
        self.keys_pressed = 0
        self.plan = None  # (lane_a, lane_b, reason) of a swap in progress
        self.last_formation = -(10**9)
        self.abandon = set()  # birds let go on purpose
        self.counts = Counter()  # strategy actions: brakes, formation swaps, birds let go

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
            return max(1, int(stats.bird(i, 'presses_to_bounce')) - special.dinosaur_up_presses.get(i, 0))
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
            if state.birds.lost[i] or i in self.abandon or i not in self.view:
                continue  # lost, let go, or out of sight and forgotten
            bird_type = get_bird_type_by_color(state.birds.colors[i])
            falling = self._vy(i) == 1
            poisoned = i in special.poisoned_birds

            if not falling and not poisoned:
                self.fall_seen.pop(i, None)
                continue
            if self._y(i) >= 999:
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
                deadline = (floor - self._y(i)) * self._frames_per_cell(i)
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
            ready = not falling or poisoned or self._y(i) >= self._bounce_line() or below is not None
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

    def _power_useful(self, i, enemy_lanes):
        """Would firing rising bird ``i``'s power count right now?"""
        if state.birds.lost[i] or self._vy(i) != -1:
            return False
        # A1 grades and above (or cards) give more than one use per ascent
        if state.birds.power_uses[i] >= int(stats.bird(i, 'power_uses')):
            return False
        lane = state.birds.random_lanes[i]
        if lane in state.spells.silenced_lanes or i in state.special.poisoned_birds:
            return False
        bird_type = get_bird_type_by_color(state.birds.colors[i])
        if bird_type in _FREE_POWERS:
            return True
        if bird_type in _ATTACK_POWERS:
            # Blue sprints and Red shoots only into an enemy; a Red waits for its battery
            useful = lane in enemy_lanes.get(i, ())
            if useful and bird_type == BirdType.RED and self.skill.red_battery:
                useful = self._red_ready(i, lane)
            return useful
        if bird_type in _SUPPORT_POWERS:
            return self._falling_neighbour(lane, _SUPPORT_POWERS[bird_type])
        if bird_type == BirdType.CLOCKWORK:
            return state.special.clockwork_charge.get(i, 3) < getattr(constants.clockwork, 'max_charge', 3)
        return False

    def _power_target(self, lanes=None):
        """Lane of a rising bird whose power is worth firing now (only in ``lanes`` if given), or None."""
        if not self.skill.use_powers:
            return None
        best = None
        enemy_lanes = self._enemy_lanes()
        for i in range(constants.layout.num_balls):
            lane = state.birds.random_lanes[i]
            if lanes is not None and lane not in lanes:
                continue
            if self._power_useful(i, enemy_lanes):
                cost = self._travel_frames(lane)
                if best is None or cost < best[0]:
                    best = (cost, lane)
        return best[1] if best else None

    def _hub_lane(self, lane):
        """A rising White whose power would bounce the bird in ``lane`` from closer by, or ``lane``.

        One UP on the White bounces every falling bird within two lanes, so the
        cursor need not travel to each of them.
        """
        if not self.skill.use_powers:
            return lane
        best, best_cost = lane, self._travel_frames(lane)
        for i in range(constants.layout.num_balls):
            if state.birds.lost[i] or state.birds.vy[i] != -1:
                continue
            if get_bird_type_by_color(state.birds.colors[i]) != BirdType.WHITE:
                continue
            white_lane = state.birds.random_lanes[i]
            if abs(white_lane - lane) > 2 or white_lane == lane:
                continue
            if state.birds.power_uses[i] >= int(stats.bird(i, 'power_uses')):
                continue
            if white_lane in state.spells.silenced_lanes or i in state.special.poisoned_birds:
                continue
            cost = self._travel_frames(white_lane)
            if cost < best_cost:
                best, best_cost = white_lane, cost
        if best != lane:
            self.counts['white hub'] += 1
        return best

    def _red_ready(self, i, lane):
        """Fire a Red now? Yes if its shooter neighbours are rising, there are none, or the enemy is near."""
        shooters = (BirdType.RED, BirdType.PURPLE, BirdType.PATCHWORK)
        neighbours = [
            j
            for j in range(constants.layout.num_balls)
            if not state.birds.lost[j]
            and abs(state.birds.random_lanes[j] - lane) == 1
            and get_bird_type_by_color(state.birds.colors[j]) in shooters
        ]
        if not neighbours or any(state.birds.vy[j] == -1 for j in neighbours):
            return True
        x = constants.layout.lane_positions[lane]
        near = [
            e for e in state.enemies.bats if abs(e['x_pos'] + 4 - x) <= 3 and 0 <= state.birds.y[i] - e['y_pos'] <= 6
        ]
        return bool(near)

    def _purple_charge_key(self, slack):
        """Keep a charging Purple charging (UP within 0.6 s) until it reaches purple_charge seconds."""
        if self.skill.purple_charge <= 0:
            return None
        now = clock.now()
        for i in range(constants.layout.num_balls):
            if state.birds.lost[i] or state.special.purple_state[i] != 2:
                continue
            charged = now - state.special.purple_charge_started_frame[i]
            if charged >= self.skill.purple_charge:
                return None  # let it go: no more UP, it fires on release
            if now - state.special.last_up_time < 0.35 or slack < self.skill.safety_frames * 3:
                return None
            lane = state.birds.random_lanes[i]
            if lane in get_affected_lanes():
                return self._bindings()[2]
            return self._key_towards(lane, False)
        return None

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
        # Only the enemies it can see
        enemies = [
            (ex, ey)
            for ex, ey in enemies
            if self._sees(min(range(len(positions)), key=lambda lane: abs(positions[lane] - ex)), ey)
        ]
        for i in range(constants.layout.num_balls):
            if i not in self.view:
                continue
            lane = state.birds.random_lanes[i]
            x = positions[lane]
            if any(abs(ex - x) <= 3 and ey < self._y(i) for ex, ey in enemies):
                lanes_by_bird[i] = (lane,)
        return lanes_by_bird

    def _falling_neighbour(self, lane, reach):
        for i, bird_lane in enumerate(state.birds.random_lanes):
            if state.birds.lost[i] or bird_lane == lane or abs(bird_lane - lane) > reach:
                continue
            if self._vy(i) == 1:
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
            (self._y(i) * self._frames_per_cell(i), state.birds.random_lanes[i])
            for i in self.view
            if not state.birds.lost[i] and self._vy(i) == -1 and self._y(i) < 999
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

    def _choose(self, offer):
        """Index of the option the bot wants in a choice on screen."""
        options = offer['cards']
        policy = self.skill.pact_policy if offer['kind'] == 'pact' else self.skill.card_policy
        if policy == 'random':
            return self.rng.randrange(len(options))
        if policy == 'adaptive':
            return strategy.choose_card(offer, self.skill)
        if offer['kind'] == 'pact':
            if policy == 'refuse':
                return len(options) - 1
            pacts = [i for i, c in enumerate(options) if c['kind'] == 'pact']
            return min(pacts, key=lambda i: (len(options[i]['drawbacks']), -len(options[i]['effects'])))
        if policy == 'first':
            return 0
        rank = {'common': 0, 'uncommon': 1, 'rare': 2, 'epic': 3, 'legendary': 4, 'mythical': 5}
        value = {'bird': 1.6, 'flock': 1.5, 'stat': 1.0, 'cursed': 0.9, 'training': 0.5, 'boost': 0.4, 'powerup': 0.3}

        def worth(i):
            card = options[i]
            if card['kind'] == 'bird' and not strategy.wants_bird(card['bird'], self.skill):
                return 0
            return (rank[card['rarity']] + 1) * value.get(card['kind'], 1)

        return max(range(len(options)), key=worth)

    def _choice_key(self, offer):
        target = self._choose(offer)
        if offer['index'] < target:
            return 'DOWN'
        if offer['index'] > target:
            return 'UP'
        return 'ENTER'

    # ------------------------------------------------------------------ strategy

    def _update_abandon(self):
        before = self.abandon
        self.abandon = strategy.abandoned(self.skill)
        self.counts['birds let go'] += len(self.abandon - before)

    def _plan_swap(self, slack):
        """Start a strategic swap (brake or formation) when there is time for it."""
        if self.plan is not None or slack < 120 or not strategy.can_swap():
            return
        falling = sum(1 for i in strategy.alive() if state.birds.vy[i] == 1)
        if strategy.wants_brake(self.skill, falling):
            pair = strategy.brake_swap(state.player.lane)
            if pair:
                self.plan = (*pair, 'brakes')
                return
        if self.skill.formation != 'none' and self.frame - self.last_formation >= self.skill.formation_every:
            self.last_formation = self.frame
            pair = strategy.best_formation_swap(self.skill.formation)
            if pair:
                self.plan = (*pair, 'formation swaps')

    def _plan_travel(self):
        """Frames the rest of the swap in progress needs."""
        a, b, _reason = self.plan
        cursor = state.player.lane
        steps = abs(b - cursor) if state.player.selected_lane is not None else abs(a - cursor) + abs(b - a)
        return (steps + 2) * self.skill.key_interval

    def _swap_key(self):
        """Next key of the swap in progress (select lane a, then swap with lane b)."""
        left, right, _up = self._bindings()
        swap = state.settings.key_bindings.get('SWAP', 'SPACE')
        a, b, reason = self.plan
        cursor = state.player.lane
        if state.player.selected_lane is None:
            if cursor != a:
                return left if a < cursor else right
            return swap
        if cursor != b:
            return left if b < cursor else right
        self.plan = None
        if strategy.can_swap():
            self.counts[reason] += 1
        return swap

    def decide(self):
        """The key to press this frame, or None."""
        if state.choice.active is not None:
            return self._choice_key(state.choice.active)
        if self.frame % 30 == 0:
            self._update_abandon()
        targets = self._urgent_targets()
        slack_min = min((t[0] for t in targets), default=float('inf'))
        if self.plan is not None or slack_min > self.skill.swap_slack:
            self._plan_swap(slack_min)
        # A strategic swap goes on only while no bird will need the cursor before it ends
        if self.plan is not None and slack_min > self.skill.swap_slack + self._plan_travel():
            if state.player.selected_lane is None and not strategy.can_swap():
                self.plan = None
            else:
                return self._swap_key()
        charge = self._purple_charge_key(slack_min)
        if charge is not None:
            return charge
        if targets:
            # Triage: a bird that can no longer be reached is not the one to run for
            savable = [t for t in targets if t[0] >= 0]
            slack, lane, bird, _ready = min(savable or targets)
            # Stick to the bird it is running for unless another is clearly more urgent:
            # switching back and forth between two birds saves neither
            current = [t for t in savable if t[2] == self.chasing]
            if current and current[0][0] <= slack + self.skill.safety_frames:
                slack, lane, bird, _ready = current[0]
            self.chasing = bird
            # A bird under the cursor that has fallen far enough gets its UP now, unless
            # that UP is the last moment to set off for a savable bird elsewhere
            cursor_lanes = set(get_affected_lanes())
            here = [t for t in targets if t[1] in cursor_lanes and t[3]]
            if here and not self._harmful_press():
                margin = self.skill.key_interval + self.skill.safety_frames
                last_call = [t for t in savable if t[1] not in cursor_lanes and t[0] < margin]
                if not last_call:
                    return self._bindings()[2]
            if slack <= self.skill.safety_frames:
                return self._key_towards(self._hub_lane(lane), True)
            # Sweep: a falling bird under the cursor gets its UP on the way
            if self.skill.sweep and slack > self.skill.key_interval + self.skill.safety_frames:
                cursor_lanes = set(get_affected_lanes())
                if any(t[1] in cursor_lanes for t in targets) and not self._harmful_press():
                    self.counts['sweep bounces'] += 1
                    return self._bindings()[2]
            # The second UP: a power under the cursor that counts now costs no travel
            if slack > self.skill.key_interval + self.skill.safety_frames:
                here = self._power_target(lanes=get_affected_lanes())
                if here is not None:
                    key = self._key_towards(here, True)
                    if key is not None:
                        return key
            # Bounce the closest bird that has fallen far enough (falling birds first)
            ready = [t for t in targets if t[3]]
            if ready:
                _slack, lane, _bird, _ready = min(ready, key=lambda t: (self._travel_frames(t[1]), t[0]))
                return self._key_towards(self._hub_lane(lane), True)
            # Nothing to bounce yet: a power worth the trip if there is plenty of time,
            # else wait under the bird that will need the cursor first
            power_lane = self._power_target() if self.skill.power_travel else None
            if power_lane is not None and self._travel_frames(power_lane) * 2 + self.skill.safety_frames < slack:
                key = self._key_towards(power_lane, True)
                if key is not None:
                    return key
            return self._key_towards(lane, False)

        power_lane = self._power_target(lanes=None if self.skill.power_travel else get_affected_lanes())
        if power_lane is not None:
            key = self._key_towards(power_lane, True)
            if key is not None:
                return key

        lane, press = self._idle_lane()
        if lane is None:
            return None
        return self._key_towards(lane, press)

    # ------------------------------------------------------------------ what it sees

    def _perceive(self):
        """What the bot sees this frame: what the player would (dark, fog), plus memory."""
        self.lit = hazards.darkness_levels()  # (lane, row) -> darkness, None in lit worlds
        self.view = {}
        horizon = self.skill.memory * 60
        for i in range(constants.layout.num_balls):
            if state.birds.lost[i]:
                self.memory.pop(i, None)
                continue
            y, vy = state.birds.y[i], state.birds.vy[i]
            if y >= 999 or hazards.visible(state.birds.random_lanes[i], y, self.lit):
                self.view[i] = (y, vy)
                self.memory[i] = (y, vy, self.frame, self._frames_per_cell(i))
                continue
            seen = self.memory.get(i)
            if seen is None or self.frame - seen[2] > horizon:
                continue
            last_y, last_vy, frame, per_cell = seen
            guess = last_y + last_vy * (self.frame - frame) / max(1, per_cell)
            if last_vy == -1 and guess < 1:
                guess, last_vy = 2 - guess, 1  # it reached the ceiling and fell again
            self.view[i] = (min(constants.layout.height - 1, int(guess)), last_vy)

    def _sees(self, lane, y):
        return hazards.visible(lane, y, self.lit)

    def _y(self, i):
        return self.view[i][0]

    def _vy(self, i):
        return self.view[i][1] if i in self.view else 0

    def _sweep_up(self):
        """Is there a falling bird under the cursor to bounce? (any height: the cursor is there)"""
        if self.plan is not None or self._harmful_press():
            return False
        cursor_lanes = set(get_affected_lanes())
        return any(t[1] in cursor_lanes for t in self._urgent_targets())

    def press(self):
        """Keys pressed this frame, respecting the key rate of each hand.

        With two hands, the UP hand bounces whatever falls under the cursor while
        the other hand moves it (sweep: arrow + UP is one decision, not two).
        Swaps are a combo (SPACE, arrows, SPACE) played at ``combo_interval``.
        """
        self.frame += 1
        self.cooldown = max(0, self.cooldown - 1)
        self.up_cooldown = max(0, self.up_cooldown - 1)
        self._perceive()
        up = self._bindings()[2]
        two_hands = self.skill.two_hands and state.choice.active is None
        keys = []
        if two_hands and self.skill.sweep and self.up_cooldown == 0 and self._sweep_up():
            keys.append(up)
            self.up_cooldown = self.skill.key_interval
            self.counts['sweep bounces'] += 1
        if self.cooldown == 0 or (two_hands and self.up_cooldown == 0):
            plan = self.plan
            key = self.decide()
            if key is not None:
                if two_hands and key == up:
                    if self.up_cooldown == 0:
                        keys.append(up)
                        self.up_cooldown = self.skill.key_interval
                elif self.cooldown == 0:
                    keys.append(key)
                    combo = self.plan is not None or plan is not None
                    self.cooldown = self.skill.combo_interval if combo else self.skill.key_interval
                    if not two_hands:
                        self.up_cooldown = self.cooldown
                else:
                    self.plan = plan  # the moving hand is busy: the key waits
        pressed = []
        for key in keys:
            self.keys_pressed += 1
            if self.rng.random() >= self.skill.miss_rate:
                pressed.append(key)  # else: fumbled the key, time spent, nothing happens
        return pressed
