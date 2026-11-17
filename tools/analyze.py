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


# ---------------------------------------------------------------------- main


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.split('\n\n')[0],
        epilog=__doc__.split('\n\n', 1)[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest='analysis', required=True)
    for name in ('factors', 'decisions'):
        p = sub.add_parser(name)
        p.add_argument('--runs', type=int, default=120, help='games to play (default 120)')
        p.add_argument('--jobs', type=int, default=0, help='parallel processes (default: all CPUs)')
        p.add_argument('--seed', type=int, default=1)
        p.add_argument('--bot', default='expert')
        p.add_argument('--difficulty', default='adventure')
        p.add_argument('--max-minutes', type=float, default=12.0, help='game-time limit per run (default 12)')
        p.add_argument('--json', metavar='FILE', help='write the raw data to this file')
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
    args = parser.parse_args(argv)
    {'factors': factors, 'decisions': decisions}[args.analysis](args)


if __name__ == '__main__':
    main()
