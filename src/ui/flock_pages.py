"""FLOCK menu pages: each bird's stats (base, power-ups, total) and the flock's.

A bird's base is its type and grade (bird_stats); the "±" column is what the
cards, pacts and upgrades of this run add (stats modifiers); the last column
is the value now.
"""

from src.core import constants, state
from src.engine import choices, stats
from src.engine.grades import _GRADE_LABELS, compute_grade_from_xp, grade_progress
from src.engine.progression import compute_prestige


def xp_bar(xp, cells):
    """▰▰▰▱▱: the way from the current grade to the next one."""
    filled = int(grade_progress(xp) * cells + 1e-9)
    return '▰' * filled + '▱' * (cells - filled)


def _next_grade(grade):
    order = ('D',) + tuple(_GRADE_LABELS)
    return order[order.index(grade) + 1] if grade in order and grade != order[-1] else None


def _num(value):
    value = round(value, 2)
    if isinstance(value, float) and not value.is_integer():
        return f'{value:.2f}'.rstrip('0').rstrip('.')
    return str(int(value))


def _row(name, base, now):
    """A stat line: name, base value, value now (fits the pause panel)."""
    return f'{name.replace("_", " ")[:16]:<16}{_num(base):>6}{_num(now):>6}'


HEADER = f'{"stat":<16}{"base":>6}{"now":>6}'


def bird_page(i):
    birds = state.birds
    if i >= len(birds.colors) or birds.lost[i]:
        return {'title': 'FLOCK', 'lines': ['This bird is lost.']}
    kind = stats.type_of(i) or '?'
    grade, _ = compute_grade_from_xp(birds.per_bird_xp[i])
    status = []
    special = state.special
    for flag, table in (
        ('scared', special.scared_birds),
        ('stunned', special.stunned_birds),
        ('poisoned', special.poisoned_birds),
        ('bleeding', special.bleeding_birds),
        ('frozen', special.frozen_birds),
        ('zombie', special.zombies),
    ):
        if i in table:
            status.append(flag)
    xp = birds.per_bird_xp[i]
    nxt = _next_grade(grade)
    progress = f'{int(grade_progress(xp) * 100)}% to {nxt}' if nxt else 'top grade'
    lines = [
        f'{kind} {grade}, lane {birds.random_lanes[i] + 1}',
        f'XP {int(xp)}  {progress}',
        xp_bar(xp, 20),
    ]
    if status:
        lines.append(', '.join(status))
    lines += ['', HEADER]
    changed, other = [], []
    for name, definition in stats.BIRD_STATS.items():
        base, now = stats.base(i, name), stats.bird(i, name)
        if abs(now - base) > 1e-9:
            changed.append(_row(name, base, now))  # power-ups first
        elif abs(base - definition.default) > 1e-9 or name in ('speed', 'damage'):
            other.append(_row(name, base, now))
    return {'title': f'FLOCK: {kind}', 'lines': lines + changed + other}


def _flock_card_effects():
    """Bird stats the cards and pacts change for every bird: (name, base, now) with base = default."""
    totals = {}
    for mod in state.stats.modifiers:
        if mod['target'] == 'flock' and mod['stat'] in stats.BIRD_STATS:
            add, mul = totals.get(mod['stat'], (0.0, 1.0))
            totals[mod['stat']] = (add + mod.get('add', 0), mul * mod.get('mul', 1))
    out = []
    for name, (add, mul) in totals.items():
        default = stats.BIRD_STATS[name].default
        out.append((name, default, (default + add) * mul))
    return out


def flock_page():
    lines = [HEADER]
    for name, definition in stats.FLOCK_STATS.items():
        lines.append(_row(name, definition.default, stats.flock(name)))
    lines.append(f'{"prestige now":<16}{"":>6}{_num(compute_prestige()):>6}')
    effects = _flock_card_effects()
    if effects:
        lines += ['', 'Every bird (cards, pacts):', HEADER]
        lines += [_row(name, base, now) for name, base, now in effects]
    lines += ['', f'Rerolls {choices.rerolls_left()}, skips {choices.skips_left()}', '']
    taken = state.choice.taken
    cards = [t for t in taken if t['kind'] != 'pact']
    pacts = [t for t in taken if t['kind'] == 'pact']
    counts = {}
    for card in cards:
        counts[card['name']] = counts.get(card['name'], 0) + 1
    lines.append(f'Cards taken: {len(cards)}')
    lines += [f' {name} x{n}' if n > 1 else f' {name}' for name, n in sorted(counts.items(), key=lambda kv: -kv[1])]
    lines.append('Pacts:' + ('' if pacts else ' none'))
    lines += [f' {p["name"]}' for p in pacts]
    return {'title': 'FLOCK STATS', 'lines': lines}


def bird_label(i):
    """Menu line of a bird slot: its lane, type and grade (or "lost")."""
    birds = state.birds
    if i >= len(birds.lost) or birds.lost[i]:
        lane = birds.random_lanes[i] + 1 if i < len(birds.random_lanes) else i + 1
        return f'{lane}. (lost)'
    grade, _ = compute_grade_from_xp(birds.per_bird_xp[i])
    return f'{birds.random_lanes[i] + 1}. {stats.type_of(i) or "?"} {grade} {xp_bar(birds.per_bird_xp[i], 4)}'


def bird_slots():
    """Every bird slot, by lane (lost birds included, so every page can be reached)."""
    birds = state.birds
    slots = list(range(constants.layout.num_balls))
    return sorted(slots, key=lambda i: birds.random_lanes[i] if i < len(birds.random_lanes) else i)
