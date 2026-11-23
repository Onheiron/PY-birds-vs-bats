"""FLOCK menu pages: each bird's stats (base, power-ups, total) and the flock's.

A bird's base is its type and grade (bird_stats); the "±" column is what the
cards, pacts and upgrades of this run add (stats modifiers); the last column
is the value now.
"""

from src.core import constants, state
from src.engine import choices, stats
from src.engine.grades import compute_grade_from_xp
from src.engine.progression import compute_prestige

GREEN = '\x1b[92m'
RED = '\x1b[91m'
RESET = '\x1b[0m'
MAX_STAT_LINES = 17  # what fits on screen under the header


def _num(value):
    if isinstance(value, float) and not value.is_integer():
        return f'{value:.2f}'.rstrip('0').rstrip('.')
    return str(int(value))


def _delta(value):
    if abs(value) < 1e-9:
        return '    '
    text = ('+' if value > 0 else '') + _num(round(value, 2))
    return f'{GREEN if value > 0 else RED}{text:>5}{RESET}'


def _row(name, base, now):
    delta = now - base
    label = name.replace('_', ' ')[:17]
    return f'{label:<17}{_num(round(base, 2)):>6} {_delta(delta)} {_num(round(now, 2)):>6}'


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
    lines = [
        f'{kind}  grade {grade}  lane {birds.random_lanes[i] + 1}',
        f'XP {int(birds.per_bird_xp[i])}' + (f'   {", ".join(status)}' if status else ''),
        '',
        f'{"stat":<17}{"base":>6} {"  ±  "} {"now":>6}',
    ]
    changed, other = [], []
    for name, definition in stats.BIRD_STATS.items():
        base, now = stats.base(i, name), stats.bird(i, name)
        if abs(now - base) > 1e-9:
            changed.append(_row(name, base, now))
        elif abs(base - definition.default) > 1e-9 or name in ('speed', 'damage'):
            other.append(_row(name, base, now))
    rows = changed + other
    if len(rows) > MAX_STAT_LINES:
        rows = rows[: MAX_STAT_LINES - 1] + [f'... and {len(rows) - MAX_STAT_LINES + 1} more']
    return {'title': f'FLOCK: {kind}', 'lines': lines + rows}


def flock_page():
    lines = [f'{"stat":<17}{"base":>6} {"  ±  "} {"now":>6}']
    for name, definition in stats.FLOCK_STATS.items():
        lines.append(_row(name, definition.default, stats.flock(name)))
    lines += [
        f'{"prestige (total)":<17}{"":>6}       {_num(round(compute_prestige(), 2)):>6}',
        '',
        f'Rerolls left {choices.rerolls_left()}   skips left {choices.skips_left()}',
        '',
    ]
    taken = state.choice.taken
    cards = [t for t in taken if t['kind'] != 'pact']
    pacts = [t for t in taken if t['kind'] == 'pact']
    counts = {}
    for card in cards:
        counts[card['name']] = counts.get(card['name'], 0) + 1
    lines.append(f'Cards taken: {len(cards)}')
    names = [f'{name} x{n}' if n > 1 else name for name, n in sorted(counts.items(), key=lambda kv: -kv[1])]
    line = ' '
    for name in names:
        if len(line) + len(name) + 2 > 36:
            lines.append(line)
            line = ' '
        line += name + ', '
    if line.strip():
        lines.append(line.rstrip(', '))
    lines.append(f'Pacts: {", ".join(p["name"] for p in pacts) or "none"}')
    return {'title': 'FLOCK STATS', 'lines': lines[:24]}


def bird_label(i):
    """Menu line of a bird slot: its lane, type and grade (or "lost")."""
    birds = state.birds
    if i >= len(birds.lost) or birds.lost[i]:
        lane = birds.random_lanes[i] + 1 if i < len(birds.random_lanes) else i + 1
        return f'{lane}. (lost)'
    grade, _ = compute_grade_from_xp(birds.per_bird_xp[i])
    return f'{birds.random_lanes[i] + 1}. {stats.type_of(i) or "?"} {grade}'


def bird_slots():
    """Every bird slot, by lane (lost birds included, so every page can be reached)."""
    birds = state.birds
    slots = list(range(constants.layout.num_balls))
    return sorted(slots, key=lambda i: birds.random_lanes[i] if i < len(birds.random_lanes) else i)
