#!/usr/bin/env python3
"""What matters in a run, and which choice is best in which situation.

Two analyses, both on games played by the bot:

  factors    Every game draws each factor at random (bot strategy, play style,
             card and pact policy, configuration values given with --factor).
             Because the factors are drawn independently, the mean outcome for
             each value of a factor is a fair comparison. Factors are ranked by
             how much of the variation in the outcome they explain (eta²) and
             by the gap between their best and worst value.

  decisions  The bot takes egg cards and pacts at random, and every choice is
             recorded with its situation (level, lives, birds alive, scared
             birds, boss, prestige...) and with what happened in the next two
             minutes. For each card, and for each situation, the tool compares
             the games where it was taken with those where it was offered and
             not taken: the difference is what that choice is worth there.
             The best choices per situation become rules ("when lives <= 3,
             take Feather Brake").

    python3 tools/analyze.py factors --runs 200
    python3 tools/analyze.py factors --runs 200 --factor "cards.drop_chance.bat=[0.5, 1.0]"
    python3 tools/analyze.py decisions --runs 200
    python3 tools/analyze.py decisions --runs 200 --by lives,birds

Outcomes: level reached, minutes survived, log10 of the score (factors);
levels gained, birds kept and deaths in the next 2 minutes (decisions).
"""

import argparse
import json
import math
import os
import random
import statistics
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Bot fields drawn at random in the factors analysis: name -> possible values
BOT_FACTORS = {
    'max_gear': [0, 6, 7, 8],
    'formation': ['none', 'red_battery', 'yellow_guard', 'white_center'],
    'keep_birds': [9, 7, 5],
    'use_powers': [True, False],
    'bounce_from': [0.2, 0.35, 0.6],
    'dodge': [True, False],
    'card_policy': ['smart', 'adaptive', 'random'],
    'pact_policy': ['smart', 'adaptive', 'refuse'],
}

# Situation buckets for the decisions analysis: name -> (label, function of the context)
BUCKETS = {
    'phase': lambda c: 'early (levels 1-6)' if c['level'] <= 6 else 'late (levels 7+)',
    'lives': lambda c: 'lives <= 3' if c['lives'] <= 3 else 'lives > 3',
    'birds': lambda c: 'birds <= 6' if c['birds'] <= 6 else 'birds > 6',
    'scared': lambda c: 'some scared' if c['scared'] > 0 else 'none scared',
    'boss': lambda c: 'boss fight' if c['boss'] else 'no boss',
    'gear': lambda c: 'gear <= 6' if c['gear'] <= 6 else 'gear > 6',
}


# Decisions outcome: a single score (levels gained, birds kept, a death is a heavy loss)
def decision_score(d):
    return d['levels_after'] + 0.3 * d['birds_after'] - 3.0 * d['died_after']


# ---------------------------------------------------------------------- running


def setup():
    sys.argv = sys.argv[:1]
    os.environ['HOME'] = os.environ['USERPROFILE'] = tempfile.mkdtemp(prefix='bvb-analyze-')
    os.chdir(ROOT)


def play(configs, jobs):
    from src.sim.runner import run_many

    print(f'Playing {len(configs)} games on {jobs} processes...', flush=True)
    return run_many(configs, jobs=jobs)


def parse_factor(text):
    """'a.b=[1, 2, 3]' -> ('a.b', [1, 2, 3])."""
    import yaml

    key, _, values = text.partition('=')
    values = yaml.safe_load(values)
    if not isinstance(values, list) or len(values) < 2:
        raise SystemExit(f'--factor needs a list of at least two values: {text!r}')
    return key.strip(), values


def nested(key, value):
    out = node = {}
    *parents, leaf = key.split('.')
    for name in parents:
        node = node.setdefault(name, {})
    node[leaf] = value
    return out


# ---------------------------------------------------------------------- statistics


def mean(values):
    return statistics.fmean(values) if values else float('nan')


def eta_squared(groups):
    """Share of the variance of the outcome explained by the grouping (0..1)."""
    values = [v for g in groups.values() for v in g]
    if len(values) < 2:
        return 0.0
    grand = mean(values)
    total = sum((v - grand) ** 2 for v in values)
    if total == 0:
        return 0.0
    between = sum(len(g) * (mean(g) - grand) ** 2 for g in groups.values() if g)
    return between / total


def stderr(values):
    return statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else float('nan')


# ---------------------------------------------------------------------- factors


def outcomes(run):
    return {
        'level': run['level'],
        'minutes': run['minutes'],
        'log score': math.log10(max(1, run['score'])),
    }


def factors(args):
    setup()
    from dataclasses import replace

    from src.sim.bot import profile
    from src.sim.options import DIFFICULTIES
    from src.sim.runner import RunConfig

    rng = random.Random(args.seed)
    space = {f'bot.{k}': v for k, v in BOT_FACTORS.items() if not args.only or k in args.only}
    for text in args.factor:
        key, values = parse_factor(text)
        space[key] = values

    base = profile(args.bot)
    configs, drawn = [], []
    for k in range(args.runs):
        choice = {name: rng.choice(values) for name, values in space.items()}
        bot_fields = {name[4:]: v for name, v in choice.items() if name.startswith('bot.')}
        overrides = {}
        for name, value in choice.items():
            if not name.startswith('bot.'):
                overrides = merge(overrides, nested(name, value))
        configs.append(
            RunConfig(
                seed=args.seed + k,
                difficulty=DIFFICULTIES[args.difficulty],
                skill=replace(base, **bot_fields),
                overrides=overrides,
                max_minutes=args.max_minutes,
            )
        )
        drawn.append(choice)

    runs = play(configs, args.jobs or os.cpu_count() or 1)
    rows = []
    for name, values in space.items():
        for metric in ('level', 'minutes', 'log score'):
            groups = {repr(v): [outcomes(r)[metric] for r, c in zip(runs, drawn) if c[name] == v] for v in values}
            rows.append((name, metric, eta_squared(groups), groups))

    print(factor_report(rows, len(runs)))
    if args.json:
        Path(args.json).write_text(
            json.dumps([{'factors': c, **outcomes(r)} for c, r in zip(drawn, runs)], indent=1, default=str)
        )
        print(f'\nGames written to {args.json}')


def merge(base, extra):
    out = dict(base)
    for key, value in extra.items():
        out[key] = merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def factor_report(rows, n):
    lines = [f'# What matters ({n} games, every factor drawn at random)\n']
    lines.append('## Ranking by level reached\n')
    lines.append('| Factor | Explains | Best value | Worst value | Gap (levels) |')
    lines.append('|---|--:|---|---|--:|')
    level_rows = sorted((r for r in rows if r[1] == 'level'), key=lambda r: -r[2])
    for name, _metric, eta, groups in level_rows:
        means = {v: mean(g) for v, g in groups.items() if g}
        best = max(means, key=means.get)
        worst = min(means, key=means.get)
        lines.append(
            f'| {name} | {100 * eta:.1f}% | {best} ({means[best]:.2f}) | {worst} ({means[worst]:.2f}) | '
            f'{means[best] - means[worst]:+.2f} |'
        )
    lines.append('\n## Every value\n')
    for name, metric, _eta, groups in rows:
        if metric != 'level':
            continue
        lines.append(f'**{name}**')
        lines.append('')
        lines.append('| Value | Games | Level | ± | Minutes | log10 score |')
        lines.append('|---|--:|--:|--:|--:|--:|')
        others = {m: g for (nm, m, _e, g) in rows if nm == name}
        for value, group in groups.items():
            minutes = others['minutes'][value]
            score = others['log score'][value]
            lines.append(
                f'| {value} | {len(group)} | {mean(group):.2f} | {stderr(group):.2f} | '
                f'{mean(minutes):.1f} | {mean(score):.2f} |'
            )
        lines.append('')
    lines.append('"Explains" is the share of the variation in the level reached that the factor accounts for')
    lines.append('(eta²); "±" is the standard error of the mean. Differences smaller than about twice the')
    lines.append('standard error can be noise.')
    return '\n'.join(lines)


# ---------------------------------------------------------------------- decisions


def decisions(args):
    setup()
    from dataclasses import replace

    from src.sim.bot import profile
    from src.sim.options import DIFFICULTIES
    from src.sim.runner import RunConfig

    skill = replace(profile(args.bot), card_policy='random', pact_policy='random')
    configs = [
        RunConfig(
            seed=args.seed + k, difficulty=DIFFICULTIES[args.difficulty], skill=skill, max_minutes=args.max_minutes
        )
        for k in range(args.runs)
    ]
    runs = play(configs, args.jobs or os.cpu_count() or 1)
    all_decisions = [d for r in runs for d in r.get('decisions', [])]
    print(decision_report(all_decisions, [b.strip() for b in args.by.split(',') if b.strip()], args.min_samples))
    if args.json:
        Path(args.json).write_text(json.dumps(all_decisions, indent=1, default=str))
        print(f'\nDecisions written to {args.json}')


def _effects(items, key):
    """{option: (score when taken, score when offered and not taken, n taken, n passed)}."""
    taken, passed = defaultdict(list), defaultdict(list)
    for d in items:
        score = decision_score(d)
        chosen = key(d, d['card'])
        taken[chosen].append(score)
        for other in set(d['offered']) - {d['card']}:
            passed[key(d, other)].append(score)
    out = {}
    for option in taken:
        if option in passed:
            t, p = taken[option], passed[option]
            se = math.sqrt(_var(t) / len(t) + _var(p) / len(p)) if len(t) > 1 and len(p) > 1 else float('inf')
            out[option] = (mean(t), mean(p), len(t), len(p), se)
    return out


def _var(values):
    return statistics.variance(values) if len(values) > 1 else 0.0


def _card_name(_d, card_id):
    return card_id


def decision_report(items, by, min_samples):
    eggs = [d for d in items if d['offer'] == 'egg']
    pacts = [d for d in items if d['offer'] == 'pact']
    lines = [f'# Which choice is worth what ({len(eggs)} egg choices, {len(pacts)} pact choices)\n']
    lines.append('Score of a choice = levels gained + 0.3 × birds kept − 3 if the game ended, over the next')
    lines.append('2 minutes. "Worth" = mean score when the card was taken − when it was offered and left;')
    lines.append('"±" is its standard error and * marks a worth larger than twice the standard error.\n')

    lines.append('## Egg cards, overall\n')
    lines.append(_table(_effects(eggs, _card_name), min_samples))

    lines.append('\n## Pacts, overall\n')
    lines.append(_table(_effects(pacts, _card_name), max(3, min_samples // 3)))

    rules = []
    for bucket in by:
        if bucket not in BUCKETS:
            raise SystemExit(f'unknown situation {bucket!r}; choose from {", ".join(BUCKETS)}')
        lines.append(f'\n## Egg cards by situation: {bucket}\n')
        label = BUCKETS[bucket]
        for value in sorted({label(d['context']) for d in eggs}):
            subset = [d for d in eggs if label(d['context']) == value]
            effects = _effects(subset, _card_name)
            lines.append(f'### {value} ({len(subset)} choices)\n')
            lines.append(_table(effects, min_samples, limit=8))
            lines.append('')
            # Only differences larger than twice their standard error count as rules
            sure = [
                (t - p, opt, se)
                for opt, (t, p, nt, np_, se) in effects.items()
                if nt >= min_samples and np_ >= min_samples and abs(t - p) > 2 * se
            ]
            sure.sort(reverse=True)
            takes = [r for r in sure if r[0] > 0][:3]
            avoids = [r for r in sure if r[0] < 0][-3:]
            if takes:
                rules.append(
                    f'- When **{value}**: take ' + ', '.join(f'**{o}** ({w:+.2f} ±{e:.2f})' for w, o, e in takes)
                )
            if avoids:
                rules.append(
                    f'- When **{value}**: avoid ' + ', '.join(f'**{o}** ({w:+.2f} ±{e:.2f})' for w, o, e in avoids)
                )

    if rules:
        lines.append('\n## Rules found\n')
        lines += rules
        lines.append('\nOnly differences larger than twice their standard error (±) are listed as rules.')
    return '\n'.join(lines)


def _table(effects, min_samples, limit=None):
    rows = [(t - p, opt, t, p, nt, se) for opt, (t, p, nt, _np, se) in effects.items() if nt >= min_samples]
    rows.sort(reverse=True)
    if limit and len(rows) > limit:
        rows = rows[: limit // 2] + rows[-(limit - limit // 2) :]
    if not rows:
        return '(not enough choices: run more games)'
    lines = ['| Card | Worth | ± | Taken | Left | Times taken |', '|---|--:|--:|--:|--:|--:|']
    for worth, opt, t, p, nt, se in rows:
        flag = ' *' if abs(worth) > 2 * se else ''
        lines.append(f'| {opt}{flag} | {worth:+.2f} | {se:.2f} | {t:.2f} | {p:.2f} | {nt} |')
    return '\n'.join(lines)


# ---------------------------------------------------------------------- levels and powers


def _overrides(args):
    from src.sim.options import merge, parse_assignments

    out = {}
    for item in getattr(args, 'set', []):
        out = merge(out, parse_assignments(item))
    return out


def _simple_runs(args, formation=None):
    from src.sim.bot import PROFILES
    from src.sim.options import DIFFICULTIES
    from src.sim.runner import RunConfig

    configs = [
        RunConfig(
            seed=args.seed + k,
            difficulty=DIFFICULTIES[args.difficulty],
            skill=PROFILES[args.bot],
            max_minutes=args.max_minutes,
            formation=formation,
            overrides=_overrides(args),
        )
        for k in range(args.runs)
    ]
    return play(configs, args.jobs or os.cpu_count() or 1)


def levels(args):
    setup()
    runs = _simple_runs(args)
    print(level_report(runs))


def level_report(runs):
    """Per level: time spent, birds lost per minute (outside / during boss fights), and what they had in common."""
    minutes, boss_minutes = defaultdict(float), defaultdict(float)
    deaths = defaultdict(list)
    reached = defaultdict(int)
    for r in runs:
        for level, sec in r.get('level_seconds', {}).items():
            minutes[int(level)] += sec / 60
        for level, sec in r.get('boss_seconds', {}).items():
            boss_minutes[int(level)] += sec / 60
        for d in r.get('deaths', []):
            deaths[d['level']].append(d)
        for level in range(1, r['level'] + 1):
            reached[level] += 1
    lines = [f'# Difficulty by level ({len(runs)} games)\n']
    lines.append(
        '| Level | Games there | Minutes | Lost / min | outside boss | during boss | scared | stunned | '
        'bats on screen | gear |'
    )
    lines.append('|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|')
    for level in sorted(minutes):
        ds = deaths.get(level, [])
        total = minutes[level]
        boss_t = boss_minutes.get(level, 0.0)
        out_t = max(1e-9, total - boss_t)
        in_boss = [d for d in ds if d['boss']]
        out_boss = [d for d in ds if not d['boss']]

        def share(key, ds=ds):
            return f"{100 * sum(d[key] for d in ds) / len(ds):.0f}%" if ds else '-'

        bats = f"{mean([d['bats'] for d in ds]):.1f}" if ds else '-'
        gear = f"{mean([d['gear'] for d in ds]):.1f}" if ds else '-'
        boss_rate = f'{len(in_boss) / boss_t:.2f}' if boss_t > 0.05 else '-'
        lines.append(
            f'| {level} | {reached[level]} | {total:.1f} | {len(ds) / max(total, 1e-9):.2f} | '
            f'{len(out_boss) / out_t:.2f} | {boss_rate} | {share("scared")} | {share("stunned")} | {bats} | {gear} |'
        )
    lines.append('\n"scared" / "stunned": share of the birds lost that were scared (by a bat) or stunned (by an')
    lines.append('obstacle) when they hit the floor; "bats on screen" and "gear" at the moment of the loss.')
    return '\n'.join(lines)


def powers(args):
    setup()
    formation = [b.strip().upper() for b in args.formation.split(',')] if args.formation else None
    runs = _simple_runs(args, formation)
    print(power_report(runs))


def power_report(runs):
    totals = defaultdict(float)
    for r in runs:
        for key, value in r.get('powers', {}).items():
            totals[key] += value
        for key, value in r.get('shots', {}).items():
            totals[f'shots {key}'] += value
    n = len(runs)
    lines = [f'# How the powers are used ({n} games; per game)\n', '| Count | Per game |', '|---|--:|']
    for key in sorted(totals):
        lines.append(f'| {key.lower()} | {totals[key] / n:.2f} |')
    return '\n'.join(lines)


# ---------------------------------------------------------------------- cards (power-ups)


def cards_analysis(args):
    """What each power-up is worth over a run: cards taken early vs progress made later."""
    setup()
    from dataclasses import replace

    from src.sim.bot import PROFILES
    from src.sim.options import DIFFICULTIES
    from src.sim.runner import RunConfig

    skill = replace(PROFILES[args.bot], card_policy='random', pact_policy='refuse')
    configs = [
        RunConfig(
            seed=args.seed + k,
            difficulty=DIFFICULTIES[args.difficulty],
            skill=skill,
            max_minutes=args.window * 2,
            overrides=_overrides(args),
        )
        for k in range(args.runs)
    ]
    runs = play(configs, args.jobs or os.cpu_count() or 1)
    print(cards_report(runs, args.window * 60))
    if args.json:
        Path(args.json).write_text(json.dumps(runs, indent=1, default=str))


def _level_at(curve, t):
    """(level, birds alive, still playing) at second ``t`` of a run."""
    last = None
    for sec, level, alive in curve:
        if sec > t:
            break
        last = (level, alive)
    playing = bool(curve) and curve[-1][0] >= t
    return (*(last or (1, 0)), playing)


def _ridge(rows, targets, names, alpha=1.0):
    """Ridge regression (pure Python): coefficients and their standard errors."""
    k = len(names)
    n = len(rows)
    # Normal equations (X'X + alpha I) b = X'y, with an intercept (not penalised)
    xtx = [[0.0] * (k + 1) for _ in range(k + 1)]
    xty = [0.0] * (k + 1)
    for row, y in zip(rows, targets):
        x = [1.0] + row
        for i in range(k + 1):
            xty[i] += x[i] * y
            for j in range(k + 1):
                xtx[i][j] += x[i] * x[j]
    for i in range(1, k + 1):
        xtx[i][i] += alpha
    inverse = _invert(xtx)
    beta = [sum(inverse[i][j] * xty[j] for j in range(k + 1)) for i in range(k + 1)]
    residuals = [y - (beta[0] + sum(b * v for b, v in zip(beta[1:], row))) for row, y in zip(rows, targets)]
    sigma2 = sum(r * r for r in residuals) / max(1, n - k - 1)
    se = [math.sqrt(max(0.0, sigma2 * inverse[i][i])) for i in range(k + 1)]
    return {name: (beta[i + 1], se[i + 1]) for i, name in enumerate(names)}


def _invert(matrix):
    n = len(matrix)
    a = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        p = a[col][col] or 1e-12
        a[col] = [v / p for v in a[col]]
        for r in range(n):
            if r != col and a[r][col]:
                f = a[r][col]
                a[r] = [v - f * w for v, w in zip(a[r], a[col])]
    return [row[n:] for row in a]


def _stat_amounts(decision):
    """{stat: amount} a card adds (pct for multipliers, points otherwise), from the catalog."""
    from src.engine import cards

    card_id = decision['card']
    entry = cards._catalog().get(card_id)
    if entry is None:
        return {}
    card = cards._make_card(card_id, entry, decision['rarity'])
    out = {}
    for effect in card['effects'] + card['drawbacks']:
        if 'stat' in effect and not effect.get('seconds'):
            key = effect['stat'] + (' %' if 'pct' in effect else '')
            out[key] = out.get(key, 0) + (effect['pct'] if 'pct' in effect else effect.get('add', 0))
    return out


def cards_report(runs, window):
    """Cards taken in the first ``window`` seconds vs levels gained in the next ``window`` seconds."""
    from src.engine import cards as card_module

    early_runs = []
    for r in runs:
        curve = r.get('curve', [])
        level_mid, alive_mid, playing = _level_at(curve, window)
        if not playing:
            continue
        level_end, _alive, still = _level_at(curve, 2 * window)
        if not still:
            level_end = r['level']
        taken = [d for d in r.get('decisions', []) if d['offer'] == 'egg' and d['t'] <= window]
        early_runs.append((r, taken, level_mid, alive_mid, level_end - level_mid, r['end'] == 'game over'))
    if len(early_runs) < 20:
        return '(not enough games alive at the half-way point: run more)'

    card_ids = sorted({d['card'] for _r, taken, *_ in early_runs for d in taken})
    names = [f'card {c}' for c in card_ids] + ['eggs opened', 'level at half-time', 'birds at half-time']
    rows, gains, deaths = [], [], []
    stat_rows = []
    for _r, taken, level_mid, alive_mid, gain, died in early_runs:
        counts = defaultdict(float)
        for d in taken:
            # A rarer card counts more: weight = its rarity scale
            counts[d['card']] += card_module.rarity_scale(d['rarity']) if not d['card'].startswith('bird:') else 1
        rows.append([counts.get(c, 0.0) for c in card_ids] + [len(taken), level_mid, alive_mid])
        gains.append(gain)
        deaths.append(1.0 if died else 0.0)
        amounts = defaultdict(float)
        for d in taken:
            for stat, value in _stat_amounts(d).items():
                amounts[stat] += value
        stat_rows.append(amounts)

    fit = _ridge(rows, gains, names, alpha=2.0)
    lines = [f'# Power-ups: what each is worth ({len(early_runs)} games alive at {window // 60} min)\n']
    lines.append(f'Cards taken (at random) in the first {window // 60} minutes against the levels gained in the next')
    lines.append(
        f'{window // 60}; one "card" = one common copy (rarer copies count their rarity scale: an epic is 3.5).'
    )
    lines.append('The level reached, birds alive and eggs opened at half-time are held constant.\n')
    lines.append('| Power-up | Levels per common copy | ± | Times taken |')
    lines.append('|---|--:|--:|--:|')
    taken_count = defaultdict(int)
    for _r, taken, *_ in early_runs:
        for d in taken:
            taken_count[d['card']] += 1
    ranked = sorted(((fit[f'card {c}'][0], c) for c in card_ids), reverse=True)
    for _value, c in ranked:
        b, se = fit[f'card {c}']
        mark = ' *' if abs(b) > 2 * se else ''
        lines.append(f'| {c}{mark} | {b:+.3f} | {se:.3f} | {taken_count[c]} |')

    stats = sorted({k for row in stat_rows for k in row})
    units = {
        s: (
            10
            if s.endswith('%')
            else 0.1
            if s
            in (
                'crit_chance',
                'fear_resist',
                'fear_immunity',
                'floor_save',
                'luck',
                'egg_luck',
                'vs_bats',
                'vs_obstacles',
                'vs_elites',
            )
            else 1
        )
        for s in stats
    }
    srows = [
        [row.get(s, 0.0) / units[s] for s in stats] + [base[-3], base[-2], base[-1]]
        for row, base in zip(stat_rows, rows)
    ]
    sfit = _ridge(srows, gains, stats + ['eggs', 'level', 'alive'], alpha=2.0)
    lines.append('\n## By stat (every card that raises it, added up)\n')
    lines.append('| Stat | Unit | Levels per unit | ± |')
    lines.append('|---|--:|--:|--:|')
    for s in sorted(stats, key=lambda s: -sfit[s][0]):
        b, se = sfit[s]
        mark = ' *' if abs(b) > 2 * se else ''
        unit = f'+{units[s]:g}%' if s.endswith('%') else f'+{units[s]:g}'
        lines.append(f'| {s.replace(" %", "")}{mark} | {unit} | {b:+.3f} | {se:.3f} |')

    # Stacking: levels gained by how much damage the flock got
    lines.append('\n## Stacking (levels gained by total bonus taken)\n')
    for s in [x for x in stats if sum(1 for row in stat_rows if row.get(x)) >= 20][:8]:
        lo = [g for row, g in zip(stat_rows, gains) if row.get(s, 0.0) == 0]
        mid = [g for row, g in zip(stat_rows, gains) if 0 < row.get(s, 0.0) <= units[s] * 2]
        hi = [g for row, g in zip(stat_rows, gains) if row.get(s, 0.0) > units[s] * 2]
        lines.append(
            f'- **{s}**: none {mean(lo):.2f} ({len(lo)} games), up to 2 units {mean(mid):.2f} ({len(mid)}), '
            f'more {mean(hi):.2f} ({len(hi)})'
        )
    lines.append('\n* = larger than twice its standard error. Rare cards are taken too seldom for a clear value.')
    return '\n'.join(lines)


# ---------------------------------------------------------------------- main


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.split('\n\n')[0],
        epilog=__doc__.split('\n\n', 1)[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest='analysis', required=True)
    for name in ('factors', 'decisions', 'levels', 'powers', 'cards'):
        p = sub.add_parser(name)
        p.add_argument('--runs', type=int, default=120, help='games to play (default 120)')
        p.add_argument('--jobs', type=int, default=0, help='parallel processes (default: all CPUs)')
        p.add_argument('--seed', type=int, default=1)
        p.add_argument('--bot', default='expert')
        p.add_argument('--difficulty', default='adventure')
        p.add_argument('--max-minutes', type=float, default=12.0, help='game-time limit per run (default 12)')
        p.add_argument('--json', metavar='FILE', help='write the raw data to this file')
        p.add_argument('--set', action='append', default=[], metavar='KEY=VALUE', help='configuration override')
    sub.choices['factors'].add_argument(
        '--factor',
        action='append',
        default=[],
        metavar='KEY=[A, B]',
        help='a configuration value to draw at random too, e.g. "cards.drop_chance.bat=[0.5, 1.0]"',
    )
    sub.choices['factors'].add_argument(
        '--only', type=lambda s: s.split(','), default=None, help='bot factors to draw (default: all)'
    )
    sub.choices['decisions'].add_argument(
        '--by', default='phase,lives,birds,scared,boss', help=f'situations to split by: {", ".join(BUCKETS)}'
    )
    sub.choices['decisions'].add_argument(
        '--min-samples', type=int, default=15, help='times a card must be taken to be reported (default 15)'
    )
    sub.choices['powers'].add_argument(
        '--formation',
        default='YELLOW,PATCHWORK,YELLOW,RED,PURPLE,RED,BLUE,WHITE,BLUE',
        help='starting flock (default: one with every synergy)',
    )
    sub.choices['cards'].add_argument('--window', type=int, default=6, help='minutes of each half (default 6)')
    args = parser.parse_args(argv)
    analyses = {'factors': factors, 'decisions': decisions, 'levels': levels, 'powers': powers, 'cards': cards_analysis}
    analyses[args.analysis](args)


if __name__ == '__main__':
    main()
