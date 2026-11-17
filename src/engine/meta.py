"""Meta progression: what carries over from one run to the next.

The **profile** (saved in the player's save folder, see save_manager) holds
the gold, the upgrades bought, the global achievements unlocked and lifetime
counters.

**Achievements** (``achievements`` in config.yml) come in two kinds:

- ``run`` achievements are goals for one run ("reach level 6 losing at most
  3 birds"). They can be met again every run, and pay their gold every time.
- ``global`` achievements are goals over every run played ("kill 2,500 bats
  in all"). Each pays once, the first time.

A goal is ``all: {counter: minimum, ...}`` and optionally
``most: {counter: maximum, ...}``. Run counters (``RUN_COUNTERS``) are
counted from game events; lifetime counters add them up over the runs
(``level`` and ``score`` keep the best value instead).

The gold of a run (its achievements, × the Gold Digger upgrade) is added to
the profile when the run ends. **Upgrades** (``upgrades`` in config.yml) are
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
)
# Lifetime counters that keep the best run instead of adding up
BEST_COUNTERS = ('level', 'score')


def new_profile():
    return {'gold': 0, 'gold_earned': 0, 'runs': 0, 'upgrades': {}, 'achievements': [], 'lifetime': {}}


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
    meta.run_gold = 0
    meta.run_achievements = []
    meta.finished = False
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
    _check_global()
    gold = run_gold()
    prof['gold'] = prof.get('gold', 0) + gold
    prof['gold_earned'] = prof.get('gold_earned', 0) + gold
    if save:
        from src.services import save_manager

        save_manager.save_profile(prof)
    return gold


def run_gold():
    """Gold this run has earned so far (achievements × gold multiplier)."""
    meta = state.meta
    return int(round(meta.run_gold * (1 + upgrade_value('gold_pct') / 100)))


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


def run_achievements():
    return _as_dict(_cfg('achievements').get('run'))


def global_achievements():
    return _as_dict(_cfg('achievements').get('global'))


def _check_run():
    meta = state.meta
    for aid, entry in run_achievements().items():
        if aid in meta.run_achievements or not _met(entry, meta.run):
            continue
        entry = _as_dict(entry)
        meta.run_achievements.append(aid)
        meta.run_gold += entry.get('gold', 0)
        notify(f"{entry.get('name', aid)}  +{entry.get('gold', 0)} gold", title='Achievement!')
        events.emit('achievement', id=aid, kind='run', gold=entry.get('gold', 0))
    _check_global()


def lifetime_with_run():
    """Lifetime counters including the run in progress."""
    life = dict(profile().get('lifetime', {}))
    run = state.meta.run or {}
    if not state.meta.finished:
        for name, value in run.items():
            life[name] = max(life.get(name, 0), value) if name in BEST_COUNTERS else life.get(name, 0) + value
    life['runs'] = profile().get('runs', 0) + (0 if state.meta.finished else 1)
    return life


def _check_global():
    prof = profile()
    done = prof.setdefault('achievements', [])
    counters = lifetime_with_run()
    for aid, entry in global_achievements().items():
        if aid in done or not _met(entry, counters):
            continue
        entry = _as_dict(entry)
        done.append(aid)
        gold = entry.get('gold', 0)
        prof['gold'] = prof.get('gold', 0) + gold
        prof['gold_earned'] = prof.get('gold_earned', 0) + gold
        notify(f"{entry.get('name', aid)}  +{gold} gold", title='Global achievement!')
        events.emit('achievement', id=aid, kind='global', gold=gold)


# ---------------------------------------------------------------------- events


def _on_level_up(level):
    _set_best('level', level)


def _on_score(score):
    _set_best('score', int(score))


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
    'boss_defeated': lambda boss_type: _count('bosses'),
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


def upgrade_effects(upgrade_id, level=None):
    """The effects of an upgrade at ``level`` (default: the level owned)."""
    entry = _as_dict(upgrades()[upgrade_id])
    level = level_of(upgrade_id) if level is None else level
    if level <= 0:
        return []
    return [cards.scale_effect(e, level) for e in entry.get('effects', [])]


def upgrade_value(key):
    """Sum of a special effect (``gold_pct``, ``lives``) over every upgrade owned."""
    total = 0.0
    for upgrade_id in upgrades():
        for effect in upgrade_effects(upgrade_id):
            total += effect.get(key, 0)
    return total


def apply_upgrades():
    """Apply every upgrade owned to the run that starts."""
    for upgrade_id in upgrades():
        for effect in upgrade_effects(upgrade_id):
            if 'lives' in effect:
                state.game.lives += int(effect['lives'])
            if any(k in effect for k in ('stat', 'rerolls', 'skips')):
                cards.apply_effect(effect, source=f'upgrade:{upgrade_id}')


def describe_upgrade(upgrade_id, level=None):
    """Text of an upgrade's effect at ``level`` (default: the next one)."""
    lvl = level_of(upgrade_id) + 1 if level is None else level
    parts = []
    for effect in upgrade_effects(upgrade_id, lvl):
        if 'lives' in effect:
            parts.append(f"+{int(effect['lives'])} starting lives")
        elif 'gold_pct' in effect:
            parts.append(f"+{effect['gold_pct']:g}% gold")
        else:
            parts.append(cards.describe_effect(effect)[0])
    return ', '.join(parts)


def snapshot():
    """A copy of the profile (for the simulator, which plays many runs in a row)."""
    return copy.deepcopy(profile())
