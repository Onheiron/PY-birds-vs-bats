"""Meta progression: what carries over from one run to the next.

The **profile** (saved in the player's save folder, see save_manager) holds
the gold, the upgrades bought, the global achievements unlocked and lifetime
counters.

**Gold** comes two ways:

- every run pays a **reward** when it ends (``run_reward`` in config.yml):
  so much per level reached, per boss, per bats killed, × the difficulty and
  × the Gold Digger upgrade;
- **achievements** (``achievements.global``) pay once, the first time. A goal
  is ``all: {counter: minimum, ...}`` and optionally ``most: {counter:
  maximum, ...}``, over every run played (lifetime counters add up; ``level``,
  ``score`` and ``max_gear`` keep the best), or within one run (``in_a_run``).

Run counters (``RUN_COUNTERS``) are counted from game events. **Upgrades** (``upgrades`` in config.yml) are
bought with it from the title menu and apply from the start of every new
run: they are a tree, each node needing some levels of others first.
"""

import copy

from src.core import constants, state
from src.engine import cards, events
from src.engine.notifications import notify

RUN_COUNTERS = (
    'level',
    'score',
    'bats',
    'elites',
    'mini_bats',
    'bosses',
    'eggs',
    'rare_eggs',
    'epic_eggs',
    'legendary_eggs',
    'mythical_eggs',
    'hatched',
    'pacts',
    'swaps',
    'powers',
    'double_powers',
    'battery_shots',
    'full_charges',
    'birds_lost',
    'max_gear',
    'won',
    'won_survival',
    'won_legendary',
    'evolved_gold',
    'evolved_white',
    'evolved_orange',
    'full_house_worlds',
    'clean_worlds',
    'swapless_worlds',
    'clean_bosses',
    'adventure_world4',  # reached the fourth world on ADVENTURE (unlocks SURVIVAL)
    'spent',  # gold spent at the merchant: it comes off the run's reward
)
# Lifetime counters that keep the best run instead of adding up
BEST_COUNTERS = ('level', 'score', 'max_gear')
# Difficulty indexes (state.settings.difficulty): PEACEFUL, ADVENTURE, SURVIVAL, LEGENDARY
SURVIVAL, LEGENDARY = 2, 3


def new_profile():
    return {
        'gold': 0,
        'gold_earned': 0,
        'runs': 0,
        'upgrades': {},
        'achievements': [],
        'lifetime': {},
        'boss_kinds': [],
    }


def _cfg(section):
    node = getattr(constants, section, None)
    return node if isinstance(node, dict) else vars(node) if node is not None else {}


def _as_dict(node):
    if node is None:
        return {}
    return node if isinstance(node, dict) else vars(node)


def profile():
    return state.meta.profile


# ---------------------------------------------------------------------- run


def start_run():
    """A new run begins: reset the run counters and apply the upgrades (once per run)."""
    meta = state.meta
    meta.run = dict.fromkeys(RUN_COUNTERS, 0)
    meta.run['level'] = state.game.level
    # A continued game was already paid up to here when it was left: only new levels pay
    meta.paid_level = state.game.level if getattr(state.game, 'meta_applied', False) else 0
    meta.run_gold = 0
    meta.run_achievements = []
    meta.finished = False
    _start_world()
    if not getattr(state.game, 'meta_applied', False):
        apply_upgrades()
        state.game.meta_applied = True


def end_run(save=True):
    """The run is over: bank its gold, add its counters to the lifetime ones."""
    meta = state.meta
    if meta.finished or meta.run is None:
        return 0
    meta.finished = True
    prof = meta.profile
    life = prof.setdefault('lifetime', {})
    for name, value in meta.run.items():
        if name in BEST_COUNTERS:
            life[name] = max(life.get(name, 0), value)
        else:
            life[name] = life.get(name, 0) + value
    prof['runs'] = prof.get('runs', 0) + 1
    _check_global(run=dict(meta.run))
    gold = meta.run_gold = run_gold()
    base, factor, digger = run_reward_parts()
    prof['last_run'] = {  # what the run paid and why (TITLE > FLOCK > FEATHERS)
        'level': meta.run.get('level', 0),
        'bosses': meta.run.get('bosses', 0),
        'bats': meta.run.get('bats', 0),
        'difficulty': factor,
        'digger': round(digger, 2),
        'spent': meta.run.get('spent', 0),
        'reward': gold,
    }
    prof['gold'] = prof.get('gold', 0) + gold
    prof['gold_earned'] = prof.get('gold_earned', 0) + gold
    if save:
        from src.services import save_manager

        save_manager.save_profile(prof)
    return gold


def run_reward_parts():
    """(base gold of the run so far, difficulty multiplier, Gold Digger multiplier)."""
    cfg = _as_dict(_cfg('run_reward'))
    run = state.meta.run or {}
    base = (
        max(0, run.get('level', 0) - getattr(state.meta, 'paid_level', 0)) * float(cfg.get('per_level', 1))
        + run.get('bosses', 0) * float(cfg.get('per_boss', 4))
        + run.get('bats', 0) // max(1, int(cfg.get('bats_per_gold', 25)))
    )
    table = list(cfg.get('difficulty') or [1.0])
    difficulty = float(table[min(max(0, state.settings.difficulty), len(table) - 1)])
    return base, difficulty, 1 + upgrade_value('gold_pct') / 100


def run_gold():
    """Gold this run pays when it ends (its reward × difficulty × Gold Digger, less what the
    merchant was paid)."""
    base, difficulty, digger = run_reward_parts()
    return max(0, int(round(base * difficulty * digger)) - (state.meta.run or {}).get('spent', 0))


def difficulty_factor():
    """The difficulty's factor of the run reward (merchant prices follow it)."""
    return run_reward_parts()[1]


def spend(amount):
    """Pay ``amount`` of the run's gold (the merchant); False if the run has not earned it."""
    run = state.meta.run
    if run is None or amount > run_gold():
        return False
    run['spent'] = run.get('spent', 0) + amount
    return True


# ---------------------------------------------------------------------- difficulties


def unlocks():
    return _as_dict(_cfg('unlocks'))


def difficulty_unlocked(name):
    """Is the difficulty ``name`` open? (those not in ``unlocks`` always are)"""
    entry = unlocks().get(name)
    if entry is None or state.meta.profile is None:
        return True
    life = dict(profile().get('lifetime', {}))
    return _met(entry, life)


def unlock_goal(name):
    entry = unlocks().get(name)
    return _as_dict(entry).get('desc', '') if entry is not None else ''


# ---------------------------------------------------------------------- formation


FORMATION_EXCLUDED = ('WHITE', 'GOLD', 'ORANGE', 'ZOMBIE')  # evolved or undead: never in a formation


def formation_unlocked():
    return state.meta.profile is not None and upgrade_value('formation') > 0


def formation_choices():
    """Bird types a formation may hold: the ones discovered (Yellow, Red and Blue always)."""
    from src.entities.bird_types import BirdType

    names = [n for n in dir(BirdType) if n.isupper() and n not in FORMATION_EXCLUDED]
    known = set(state.discovery.birds) | {BirdType.YELLOW, BirdType.RED, BirdType.BLUE}
    order = ['YELLOW', 'RED', 'BLUE', 'PURPLE']
    names.sort(key=lambda n: (order.index(n) if n in order else len(order), n))
    return [getattr(BirdType, n) for n in names if getattr(BirdType, n) in known]


def default_flock():
    """The birds every run starts with (birds.default_formation), one per lane."""
    birds = list(constants.birds.default_formation[: constants.layout.num_balls])
    return birds + ['YELLOW'] * (constants.layout.num_balls - len(birds))


def formation():
    """The bird of each lane the player set (profile['formation'], lane by lane), or None: the
    default flock in random lanes. Anyone may place the default birds; the Formation upgrade
    lets them choose which birds too, among the ones discovered."""
    chosen = profile().get('formation') if state.meta.profile is not None else None
    if not chosen or len(chosen) != constants.layout.num_balls:
        return None
    if formation_unlocked():
        allowed = set(formation_choices())
        return list(chosen) if all(bird in allowed for bird in chosen) else None
    return list(chosen) if sorted(chosen) == sorted(default_flock()) else None


def _count(name, amount=1):
    run = state.meta.run
    if run is None:
        return
    run[name] = run.get(name, 0) + amount
    _check_run()


def _set_best(name, value):
    run = state.meta.run
    if run is None:
        return
    if value > run.get(name, 0):
        run[name] = value
        _check_run()


def _met(goal, counters):
    goal = _as_dict(goal)
    for name, minimum in _as_dict(goal.get('all')).items():
        if counters.get(name, 0) < minimum:
            return False
    return all(counters.get(name, 0) <= maximum for name, maximum in _as_dict(goal.get('most')).items())


def global_achievements():
    return _as_dict(_cfg('achievements').get('global'))


def run_achievements():
    """No achievement pays every run any more (the run reward does): kept for old callers."""
    return {}


def _check_run():
    _check_global()


def lifetime_with_run():
    """Lifetime counters including the run in progress."""
    life = dict(profile().get('lifetime', {}))
    run = state.meta.run or {}
    if not state.meta.finished:
        for name, value in run.items():
            life[name] = max(life.get(name, 0), value) if name in BEST_COUNTERS else life.get(name, 0) + value
    life['runs'] = profile().get('runs', 0) + (0 if state.meta.finished else 1)
    life['boss_kinds'] = len(profile().get('boss_kinds', []))
    life['birds_discovered'] = _birds_discovered()
    return life


def _birds_discovered():
    from src.entities.bird_types import BirdType

    names = {getattr(BirdType, n) for n in dir(BirdType) if n.isupper()} - {BirdType.ZOMBIE}
    return len(set(state.discovery.birds) & names)


def _check_global(run=None):
    """Pay the global achievements just reached; ``run``: the counters of the run (in_a_run goals)."""
    prof = profile()
    done = prof.setdefault('achievements', [])
    counters = lifetime_with_run()
    if run is None:
        run = dict(state.meta.run or {}) if not state.meta.finished else {}
    for aid, entry in global_achievements().items():
        if aid in done:
            continue
        if not _met(entry, run if _as_dict(entry).get('in_a_run') else counters):
            continue
        entry = _as_dict(entry)
        done.append(aid)
        state.meta.run_achievements.append(aid)
        gold = entry.get('gold', 0)
        prof['gold'] = prof.get('gold', 0) + gold
        prof['gold_earned'] = prof.get('gold_earned', 0) + gold
        notify(f"{entry.get('name', aid)}  +{gold} ❖", title='Achievement!')
        events.emit('achievement', id=aid, kind='global', gold=gold)


# ---------------------------------------------------------------------- events


def _on_level_up(level):
    _set_best('level', level)
    if state.settings.difficulty == 1 and state.game.level_group >= 4:
        _set_best('adventure_world4', 1)


def _on_score(score):
    _set_best('score', int(score))
    _set_best('max_gear', int(state.game.speed))


def _start_world():
    """Remember where a world starts: birds lost and swaps so far (for the per-world goals)."""
    run = state.meta.run or {}
    state.meta.world_start = {'birds_lost': run.get('birds_lost', 0), 'swaps': run.get('swaps', 0)}
    state.meta.boss_start_lost = None


def _on_boss_spawned(boss_type):
    state.meta.boss_start_lost = (state.meta.run or {}).get('birds_lost', 0)


def _alive_birds():
    from src.entities.sprites import ZOMBIE

    birds = state.birds
    return sum(1 for i in range(len(birds.colors)) if not birds.lost[i] and birds.colors[i] != ZOMBIE)


def _on_boss_defeated(boss_type):
    """A boss ends its world: count the boss, the world's goals, and the win after the last one."""
    run = state.meta.run
    if run is None:
        return
    lost = run.get('birds_lost', 0)
    start = getattr(state.meta, 'world_start', None) or {'birds_lost': 0, 'swaps': 0}
    if getattr(state.meta, 'boss_start_lost', None) is not None and lost == state.meta.boss_start_lost:
        run['clean_bosses'] = run.get('clean_bosses', 0) + 1
    if lost == start['birds_lost']:
        run['clean_worlds'] = run.get('clean_worlds', 0) + 1
    if run.get('swaps', 0) == start['swaps']:
        run['swapless_worlds'] = run.get('swapless_worlds', 0) + 1
    if _alive_birds() >= constants.layout.num_balls:
        run['full_house_worlds'] = run.get('full_house_worlds', 0) + 1
    kinds = profile().setdefault('boss_kinds', [])
    if boss_type not in kinds:
        kinds.append(boss_type)
    if state.game.level_group >= 6:
        run['won'] = 1
        run['won_survival'] = int(state.settings.difficulty >= SURVIVAL)
        run['won_legendary'] = int(state.settings.difficulty >= LEGENDARY)
    _start_world()
    _count('bosses')


def _on_bird_evolved(bird, into):
    name = f'evolved_{str(into).lower()}'
    if name in RUN_COUNTERS:
        _count(name)


def _on_bat_killed(bat, tier, killer):
    _count('bats')
    if bat.get('elite'):
        _count('elites')


def _on_choice_offered(offer):
    if offer['kind'] != 'egg':
        return
    _count('eggs')
    if offer.get('rarity') in ('rare', 'epic', 'legendary', 'mythical'):
        _count(f"{offer['rarity']}_eggs")


def _on_power_fired(bird, kind, use):
    _count('powers')
    if use > 1:
        _count('double_powers')


def _on_shot_fired(bird, kind, bonus):
    if kind == 'RED' and bonus >= 2:
        _count('battery_shots')
    elif kind == 'PURPLE' and bonus >= 3:
        _count('full_charges')


_HANDLERS = {
    'level_up': _on_level_up,
    'score_changed': _on_score,
    'bat_killed': _on_bat_killed,
    'mini_bat_killed': lambda bat, killer: _count('mini_bats'),
    'boss_spawned': _on_boss_spawned,
    'boss_defeated': _on_boss_defeated,
    'bird_evolved': _on_bird_evolved,
    'choice_offered': _on_choice_offered,
    'bird_hatched': lambda bird, egg, loot: _count('hatched'),
    'pact_made': lambda pact: _count('pacts'),
    'swap': lambda swaps: _count('swaps'),
    'power_fired': _on_power_fired,
    'shot_fired': _on_shot_fired,
    'bird_lost': lambda bird, color, cause: _count('birds_lost'),
}


def subscribe():
    for name, handler in _HANDLERS.items():
        events.on(name, handler)


def unsubscribe():
    for name, handler in _HANDLERS.items():
        events.off(name, handler)


# ---------------------------------------------------------------------- upgrades


def upgrades():
    return _as_dict(_cfg('upgrades').get('tree'))


def level_of(upgrade_id):
    return profile().get('upgrades', {}).get(upgrade_id, 0)


def cost(upgrade_id):
    """Gold for the next level of an upgrade, or None at its maximum."""
    entry = _as_dict(upgrades()[upgrade_id])
    costs = list(entry.get('costs', []))
    level = level_of(upgrade_id)
    return costs[level] if level < len(costs) else None


def missing_requirements(upgrade_id):
    entry = _as_dict(upgrades()[upgrade_id])
    needs = _as_dict(entry.get('requires'))
    return {name: lvl for name, lvl in needs.items() if level_of(name) < lvl}


def can_buy(upgrade_id):
    price = cost(upgrade_id)
    return price is not None and not missing_requirements(upgrade_id) and profile().get('gold', 0) >= price


def buy(upgrade_id, save=True):
    """Buy the next level of an upgrade; False if it cannot be bought."""
    if not can_buy(upgrade_id):
        return False
    prof = profile()
    prof['gold'] -= cost(upgrade_id)
    prof.setdefault('upgrades', {})[upgrade_id] = level_of(upgrade_id) + 1
    if save:
        from src.services import save_manager

        save_manager.save_profile(prof)
    return True


# Effects of the meta progression that add up level by level (stats scale through cards.scale_effect)
LEVELLED = (
    'lives',
    'gold_pct',
    'rerolls',
    'skips',
    'start_grade',
    'merchant_stock',
    'merchant_discount',
    'opening_eggs',
)


def upgrade_effects(upgrade_id, level=None):
    """The effects of an upgrade at ``level`` (default: the level owned)."""
    entry = _as_dict(upgrades()[upgrade_id])
    level = level_of(upgrade_id) if level is None else level
    if level <= 0:
        return []
    out = []
    for effect in entry.get('effects', []):
        effect = cards.scale_effect(effect, level)
        for key in LEVELLED:
            if key in effect:
                effect[key] = effect[key] * level
        out.append(effect)
    return out


def upgrade_value(key):
    """Sum of a special effect (``gold_pct``, ``lives``) over every upgrade owned."""
    total = 0.0
    for upgrade_id in upgrades():
        for effect in upgrade_effects(upgrade_id):
            total += effect.get(key, 0)
    return total


def apply_upgrades():
    """Apply every upgrade owned to the run that starts."""
    grades = {}  # bird type (None: every bird) -> grades more at the start
    opening = 0
    for upgrade_id in upgrades():
        for effect in upgrade_effects(upgrade_id):
            if 'lives' in effect:
                state.game.lives += int(effect['lives'])
            if any(k in effect for k in ('stat', 'rerolls', 'skips')):
                cards.apply_effect(effect, source=f'upgrade:{upgrade_id}')
            if 'start_grade' in effect:
                grades[effect.get('bird')] = grades.get(effect.get('bird'), 0) + int(effect['start_grade'])
            opening += int(effect.get('opening_eggs', 0))
    _start_grades(grades)
    if opening:
        from src.engine import choices

        for _ in range(opening):
            choices.offer_egg('common')


def _start_grades(grades):
    """Birds start that many grades up (Training for all, a Veteran upgrade for its type)."""
    if not grades:
        return
    from src.engine import grades as grade_table
    from src.entities.bird_types import get_bird_type_by_color

    steps = grade_table.grade_steps()
    for i, color in enumerate(state.birds.colors):
        n = grades.get(None, 0) + grades.get(get_bird_type_by_color(color), 0)
        if n > 0:
            state.birds.per_bird_xp[i] = max(state.birds.per_bird_xp[i], steps[min(n, len(steps) - 1)])


def describe_upgrade(upgrade_id, level=None):
    """Text of an upgrade's effect at ``level`` (default: the next one)."""
    lvl = level_of(upgrade_id) + 1 if level is None else level
    parts = []
    for effect in upgrade_effects(upgrade_id, lvl):
        if 'lives' in effect:
            parts.append(f"+{int(effect['lives'])} starting lives")
        elif 'gold_pct' in effect:
            parts.append(f"+{effect['gold_pct']:g}% gold")
        elif 'start_grade' in effect:
            who = str(effect['bird']).title() + ' birds' if effect.get('bird') else 'every bird'
            parts.append(f"{who} start {int(effect['start_grade'])} grade{'s' if effect['start_grade'] > 1 else ''} up")
        elif 'formation' in effect:
            parts.append('choose the starting flock (NEW GAME > FORMATION)')
        elif 'opening_eggs' in effect:
            parts.append(f"{int(effect['opening_eggs'])} common egg at the start")
        elif 'merchant_stock' in effect:
            parts.append(f"+{int(effect['merchant_stock'])} merchant ware")
        elif 'merchant_discount' in effect:
            parts.append(f"-{effect['merchant_discount']:g}% merchant prices")
        else:
            parts.append(cards.describe_effect(effect)[0])
    return ', '.join(parts)


def snapshot():
    """A copy of the profile (for the simulator, which plays many runs in a row)."""
    return copy.deepcopy(profile())
