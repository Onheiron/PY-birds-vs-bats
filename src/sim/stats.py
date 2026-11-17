"""What happened during a simulated run, gathered from game events and samples."""

import random
from collections import Counter
from contextlib import contextmanager

from src.core import constants, state
from src.engine import events
from src.engine.progression import compute_prestige

RARITIES = ('common', 'uncommon', 'rare', 'epic', 'legendary', 'mythical')
# Drops rolled on the rarity tables (Orange eggs and Cookie crumbs are fixed)
ENEMY_SOURCES = ('bat', 'mini_bat', 'boss')


def egg_rarities():
    """egg type -> rarity, from the egg tables of the configuration."""
    table = {}
    for rarity, eggs in (constants.eggs.rarity_candidates or {}).items():
        for egg in eggs if isinstance(eggs, dict) else vars(eggs):
            table.setdefault(egg, rarity)
    return table


def prestige_now():
    """Current prestige without consuming the game's random numbers."""
    saved = random.getstate()
    try:
        return compute_prestige()
    finally:
        random.setstate(saved)


class RunStats:
    def __init__(self, config, milestones):
        self.config = config
        self.milestones = milestones
        self.egg_rarity = egg_rarities()
        self.drops = []  # (seconds, source, rarity, loot type)
        self.collected = []  # (rarity, loot type)
        self.hatched = []  # (seconds, egg, rarity)
        self.lost = Counter()
        self.kills = Counter()
        self.bosses = {}  # boss type -> {'spawned': s, 'defeated': s or None}
        self.level_times = {state.game.level: 0.0}
        self.samples = []  # (seconds, level, gear, prestige, birds alive, score)
        self.seconds = 0.0
        self.end = None
        self.keys = 0

    # ------------------------------------------------------------------ events

    def _now(self):
        return self.seconds

    def _on_loot_dropped(self, loot, source):
        self.drops.append((self._now(), source, loot.get('rarity', 'common'), loot['type']))

    def _on_loot_collected(self, loot, bird):
        self.collected.append((loot.get('rarity', 'common'), loot['type']))

    def _on_bird_hatched(self, bird, egg):
        self.hatched.append((self._now(), egg, self.egg_rarity.get(egg, '?')))

    def _on_bird_lost(self, bird, color, cause):
        self.lost[cause] += 1

    def _on_bat_killed(self, bat, tier, killer):
        self.kills[f'bat tier {tier}'] += 1

    def _on_mini_bat_killed(self, bat, killer):
        self.kills['mini bat'] += 1

    def _on_level_up(self, level):
        self.level_times.setdefault(level, self._now())

    def _on_boss_spawned(self, boss_type):
        self.bosses[f'{boss_type}@{state.game.level}'] = {'spawned': self._now(), 'defeated': None}

    def _on_boss_defeated(self, boss_type):
        key = f'{boss_type}@{state.game.level}'
        if key in self.bosses:
            self.bosses[key]['defeated'] = self._now()

    @contextmanager
    def recording(self):
        handlers = {
            'loot_dropped': self._on_loot_dropped,
            'loot_collected': self._on_loot_collected,
            'bird_hatched': self._on_bird_hatched,
            'bird_lost': self._on_bird_lost,
            'bat_killed': self._on_bat_killed,
            'mini_bat_killed': self._on_mini_bat_killed,
            'level_up': self._on_level_up,
            'boss_spawned': self._on_boss_spawned,
            'boss_defeated': self._on_boss_defeated,
        }
        for name, handler in handlers.items():
            events.on(name, handler)
        try:
            yield self
        finally:
            for name, handler in handlers.items():
                events.off(name, handler)

    # ------------------------------------------------------------------ samples

    def sample(self, seconds):
        self.seconds = seconds
        game = state.game
        alive = sum(1 for lost in state.birds.lost if not lost)
        self.samples.append((seconds, game.level, game.speed, prestige_now(), alive, game.score))

    def finish(self, end, seconds, bot):
        self.seconds = seconds
        self.sample(seconds)
        self.end = end
        self.keys = bot.keys_pressed
        # The game state is global: keep the final values before the next run reuses it
        game = state.game
        self.final = {
            'level': game.level,
            'miles': round(game.miles, 2),
            'score': int(game.score),
            'lives_left': game.lives,
        }

    # ------------------------------------------------------------------ summary

    def summary(self):
        """A JSON-friendly digest of the run."""
        prestiges = [s[3] for s in self.samples]
        gears = [s[2] for s in self.samples]
        drop_rarity = Counter(rarity for _t, src, rarity, _type in self.drops if src in ENEMY_SOURCES)
        egg_drops = Counter(
            rarity for _t, src, rarity, loot in self.drops if src in ENEMY_SOURCES and loot.endswith('_egg')
        )
        hatched = Counter(rarity for _t, _egg, rarity in self.hatched)
        minutes = self.seconds / 60
        return {
            'seed': self.config.seed,
            'difficulty': self.config.difficulty,
            'end': self.end,
            'minutes': round(minutes, 2),
            **self.final,
            'keys_per_second': round(self.keys / self.seconds, 2) if self.seconds else 0,
            'gear_mean': round(sum(gears) / len(gears), 2) if gears else 0,
            'gear_max': max(gears, default=0),
            'prestige_mean': round(sum(prestiges) / len(prestiges), 2) if prestiges else 0,
            'prestige_max': round(max(prestiges, default=0), 2),
            'drops': len(self.drops),
            'drops_by_source': dict(Counter(src for _t, src, _r, _type in self.drops)),
            'drops_by_rarity': {r: drop_rarity.get(r, 0) for r in RARITIES},
            'egg_drops_by_rarity': {r: egg_drops.get(r, 0) for r in RARITIES},
            'collected': len(self.collected),
            'hatched_by_rarity': {r: hatched.get(r, 0) for r in RARITIES},
            'hatched': [egg for _t, egg, _r in self.hatched],
            'birds_lost': dict(self.lost),
            'kills': dict(self.kills),
            'bosses': self.bosses,
            'level_minutes': {level: round(t / 60, 2) for level, t in sorted(self.level_times.items())},
        }
