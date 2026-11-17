"""What happened during a simulated run, gathered from game events and samples."""

import random
from collections import Counter
from contextlib import contextmanager

from src.core import state
from src.engine import events
from src.engine.progression import compute_prestige

RARITIES = ('common', 'uncommon', 'rare', 'epic', 'legendary', 'mythical')
# Drops rolled on the rarity tables (Orange eggs and Cookie crumbs are fixed)
ENEMY_SOURCES = ('bat', 'mini_bat', 'boss')


def prestige_now():
    """Current prestige without consuming the game's random numbers."""
    saved = random.getstate()
    try:
        return compute_prestige()
    finally:
        random.setstate(saved)


# Seconds after a decision over which its outcome is measured
DECISION_HORIZON = 120


def decision_context():
    """The situation when a choice is made: what a rule "when X, take Y" can look at."""
    game = state.game
    living = [i for i, lost in enumerate(state.birds.lost) if not lost]
    return {
        'level': game.level,
        'lives': game.lives,
        'birds': len(living),
        'gear': game.speed,
        'prestige': round(prestige_now(), 2),
        'scared': sum(1 for i in living if i in state.special.scared_birds),
        'boss': state.enemies.boss is not None,
        'bats': len(state.enemies.bats),
    }


class RunStats:
    def __init__(self, config, milestones):
        self.config = config
        self.milestones = milestones
        self.drops = []  # (seconds, source, rarity, loot type)
        self.collected = []  # (rarity, loot type)
        self.hatched = []  # (seconds, egg, rarity of its drop, source of its drop)
        self._drop_source = {}  # id(loot) -> source
        self.lost = Counter()
        self.kills = Counter()
        self.picks = []  # (offer kind, card kind, card rarity, card id)
        self.powers = Counter()  # 'RED', 'RED second use'...
        self.shots = Counter()  # 'RED +2' (bonus), 'PURPLE tier 3', 'hits'
        self.offers = Counter()  # offer kind ('egg', 'pact') -> count
        self.decisions = []  # every card / pact taken, with its context (see decision_context)
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
        self._drop_source[id(loot)] = source

    def _on_loot_collected(self, loot, bird):
        self.collected.append((loot.get('rarity', 'common'), loot['type']))

    def _on_bird_hatched(self, bird, egg, loot):
        loot = loot or {}
        rarity = loot.get('rarity', '?')
        source = self._drop_source.get(id(loot), 'card')
        self.hatched.append((self._now(), egg, rarity, source))

    def _on_choice_offered(self, offer):
        self.offers[offer['kind']] += 1

    def _on_choice_made(self, offer, card):
        self.picks.append((offer['kind'], card['kind'], card['rarity'], card['id']))
        self.decisions.append(
            {
                't': self._now(),
                'offer': offer['kind'],
                'egg': offer.get('rarity'),
                'card': card['id'],
                'card_kind': card['kind'],
                'rarity': card['rarity'],
                'offered': [c['id'] for c in offer['cards']],
                'context': decision_context(),
            }
        )

    def _on_power_fired(self, bird, kind, use):
        self.powers[kind] += 1
        if use > 1:
            self.powers[f'{kind} use {use}'] += 1

    def _on_shot_fired(self, bird, kind, bonus):
        self.shots[f'{kind} +{bonus}' if kind == 'RED' else f'{kind} tier {bonus}'] += 1

    def _on_shot_hit(self, bird, kind, damage):
        self.shots['hits'] += 1

    def _on_bird_lost(self, bird, color, cause):
        self.lost[cause] += 1

    def _on_bat_killed(self, bat, tier, killer):
        self.kills[f'bat tier {tier}'] += 1
        if bat.get('elite'):
            self.kills['elite bat'] += 1

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
            'choice_offered': self._on_choice_offered,
            'choice_made': self._on_choice_made,
            'power_fired': self._on_power_fired,
            'shot_fired': self._on_shot_fired,
            'shot_hit': self._on_shot_hit,
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
        self.strategy_counts = dict(getattr(bot, 'counts', {}))
        # The game state is global: keep the final values before the next run reuses it
        game = state.game
        self.final = {
            'level': game.level,
            'miles': round(game.miles, 2),
            'score': int(game.score),
            'lives_left': game.lives,
            'swaps': game.swaps_used,
        }

    # ------------------------------------------------------------------ summary

    def _decision_outcomes(self):
        """Each decision with what followed it within DECISION_HORIZON seconds."""
        samples = self.samples
        out = []
        for decision in self.decisions:
            t = decision['t']
            later = [s for s in samples if t <= s[0] <= t + DECISION_HORIZON]
            start = next((s for s in samples if s[0] >= t), samples[-1] if samples else None)
            if not later or start is None:
                continue
            end = later[-1]
            ended_early = self.end == 'game over' and self.seconds <= t + DECISION_HORIZON
            out.append(
                {
                    **decision,
                    'levels_after': end[1] - start[1],
                    'birds_after': end[4] - start[4],
                    'died_after': ended_early,
                }
            )
        return out

    def summary(self):
        """A JSON-friendly digest of the run."""
        prestiges = [s[3] for s in self.samples]
        gears = [s[2] for s in self.samples]
        drop_rarity = Counter(rarity for _t, src, rarity, _type in self.drops if src in ENEMY_SOURCES)
        egg_drops = Counter(rarity for _t, src, rarity, loot in self.drops if src in ENEMY_SOURCES and loot == 'egg')
        hatched = Counter(rarity for _t, _egg, rarity, src in self.hatched if src != 'orange')
        egg_picks = [p for p in self.picks if p[0] == 'egg']
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
            'hatched': [egg for _t, egg, _r, _src in self.hatched],
            'hatched_from_orange': sum(1 for *_rest, src in self.hatched if src == 'orange'),
            'birds_lost': dict(self.lost),
            'strategy': getattr(self, 'strategy_counts', {}),
            'decisions': self._decision_outcomes(),
            'powers': dict(self.powers),
            'shots': dict(self.shots),
            'eggs_opened': self.offers.get('egg', 0),
            'cards_by_kind': dict(Counter(kind for _o, kind, _r, _id in egg_picks)),
            'cards_by_rarity': {r: sum(1 for p in egg_picks if p[2] == r) for r in RARITIES},
            'pacts_offered': self.offers.get('pact', 0),
            'pacts': [cid for offer, _k, _r, cid in self.picks if offer == 'pact'],
            'kills': dict(self.kills),
            'bosses': self.bosses,
            'level_minutes': {level: round(t / 60, 2) for level, t in sorted(self.level_times.items())},
        }
