#!/usr/bin/env python3
"""Play many headless games with the bot and report balance numbers.

Examples:

  # 40 games with the default (expert) bot, 4 processes
  python3 tools/simulate.py --runs 40 --jobs 4

  # The frame-perfect bot on LEGENDARY, starting from biome 4
  python3 tools/simulate.py --bot perfect --difficulty legendary --start-level 10

  # A/B test of a config change, same seeds for both sides
  python3 tools/simulate.py --runs 60 \\
      --variant "base:" \\
      --variant "slower divers: enemy_stats.bats.kinds.diver.ability_chance=0.1"

  # A different player: 20 keys per second, slower reactions
  python3 tools/simulate.py --bot expert --bot-set key_interval=3 --bot-set reaction_frames=15

  # Everything as JSON for your own analysis
  python3 tools/simulate.py --runs 100 --json results.json

Bot profiles: perfect (60 keys/s, no delay), expert (15 keys/s, 150 ms),
average (10 keys/s, 250 ms), novice (6 keys/s, 400 ms, no powers).
Values given with --set / --variant are YAML, so lists and numbers work.
"""

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RARITIES = ('common', 'uncommon', 'rare', 'epic', 'legendary', 'mythical')


def build_parser():
    from src.sim.options import add_game_options

    parser = argparse.ArgumentParser(
        description=__doc__.split('\n\n')[0],
        epilog=__doc__.split('\n\n', 1)[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--runs', type=int, default=20, help='games per variant (default 20)')
    parser.add_argument('--jobs', type=int, default=0, help='parallel processes (default: all CPUs)')
    add_game_options(parser)
    parser.add_argument('--base', metavar='FILE', help='configuration merged over config.yml (e.g. hardmode.yml)')
    parser.add_argument(
        '--variant',
        action='append',
        default=[],
        metavar='"NAME: KEY=VALUE; ..."',
        help='compare configurations (repeatable); every variant uses the same seeds',
    )
    parser.add_argument(
        '--strategies',
        metavar='NAME,NAME',
        help='compare bot strategies (src/sim/strategy.py STRATEGIES): '
        'default, brake, red_battery, yellow_guard, white_center, few_birds, favorites, adaptive, cautious',
    )
    parser.add_argument('--stop-at-level', type=int)
    parser.add_argument('--max-minutes', type=float, default=180.0, help='game-time limit per run')
    parser.add_argument('--json', metavar='FILE', help='write every run summary to this file')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    # The game reads the command line at import time: hide ours from it
    sys.argv = sys.argv[:1]
    # Discoveries and settings are saved under HOME: keep the player's untouched
    import os
    import tempfile

    os.environ['HOME'] = os.environ['USERPROFILE'] = tempfile.mkdtemp(prefix='bvb-sim-')
    from src.core.config import load_config
    from src.sim.options import DIFFICULTIES, formation_from, merge, overrides_from, parse_assignments, skill_from
    from src.sim.runner import RunConfig, run_many

    skill = skill_from(args)
    base = load_config(args.base) if args.base else None
    common = overrides_from(args)

    from dataclasses import replace

    from src.sim.strategy import STRATEGIES

    def split_bot(assignments):
        """Config overrides and bot fields (keys starting with 'bot.') of a variant."""
        values = parse_assignments(assignments)
        bot_fields = values.pop('bot', {})
        if 'strategy' in bot_fields:
            bot_fields = {**STRATEGIES[bot_fields.pop('strategy')], **bot_fields}
        for key in ('favorites',):
            if key in bot_fields:
                bot_fields[key] = tuple(bot_fields[key])
        return values, bot_fields

    variants = []
    specs = list(args.variant)
    if args.strategies:
        for name in args.strategies.split(','):
            if name.strip() not in STRATEGIES:
                raise SystemExit(f'unknown strategy {name!r}; choose from {", ".join(STRATEGIES)}')
            specs.append(f'{name.strip()}: bot.strategy={name.strip()}')
    for spec in specs or ['default:']:
        name, _, assignments = spec.partition(':')
        overrides, bot_fields = split_bot(assignments)
        variants.append((name.strip() or 'default', merge(common, overrides), replace(skill, **bot_fields)))

    jobs = args.jobs or __import__('os').cpu_count() or 1
    formation = formation_from(args)
    configs = []
    for _name, overrides, variant_skill in variants:
        for k in range(args.runs):
            configs.append(
                RunConfig(
                    seed=args.seed + k,
                    difficulty=DIFFICULTIES[args.difficulty],
                    skill=variant_skill,
                    overrides=overrides,
                    base_config=base,
                    formation=formation,
                    start_level=args.start_level,
                    max_minutes=args.max_minutes,
                    stop_at_level=args.stop_at_level,
                )
            )

    started = time.time()
    print(f'Playing {len(configs)} games ({args.bot} bot, {args.difficulty}, {jobs} processes)...', flush=True)
    summaries = run_many(configs, jobs=jobs)
    print(f'done in {time.time() - started:.0f} s\n')

    results = {}
    for index, (name, overrides, _skill) in enumerate(variants):
        runs = summaries[index * args.runs : (index + 1) * args.runs]
        results[name] = {'overrides': overrides, 'runs': runs}
    print(report(results))

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1, default=str), encoding='utf-8')
        print(f'\nRun summaries written to {args.json}')


# ---------------------------------------------------------------------- report


def pct(values, q):
    if not values:
        return 0
    values = sorted(values)
    return values[min(len(values) - 1, int(q * len(values)))]


def mean(values):
    return statistics.fmean(values) if values else 0.0


def report(results):
    names = list(results)
    rows = []

    def row(label, fn, fmt='{:.1f}'):
        rows.append((label, [fmt.format(fn(results[n]['runs'])) if results[n]['runs'] else '-' for n in names]))

    def section(title):
        rows.append((title, None))

    section('Runs')
    row('games', len, '{}')
    row('completed (all 18 levels)', lambda r: 100 * mean([x['end'] == 'completed' for x in r]), '{:.0f}%')
    row('ended by game over', lambda r: 100 * mean([x['end'] == 'game over' for x in r]), '{:.0f}%')
    row('minutes played, median', lambda r: statistics.median(x['minutes'] for x in r))
    row('level reached, median', lambda r: statistics.median(x['level'] for x in r), '{:.0f}')
    row('level reached, worst 10%', lambda r: pct([x['level'] for x in r], 0.1), '{:.0f}')
    row('score, median', lambda r: statistics.median(x['score'] for x in r), '{:,.0f}')
    row('gear, mean', lambda r: mean([x['gear_mean'] for x in r]))
    row('prestige, mean over the run', lambda r: mean([x['prestige_mean'] for x in r]))
    row('prestige, best of the run (median)', lambda r: statistics.median(x['prestige_max'] for x in r))
    row('bot keys per second', lambda r: mean([x['keys_per_second'] for x in r]))

    section('Strategy (per game)')
    row('swaps', lambda r: mean([x.get('swaps', 0) for x in r]))
    actions = sorted({a for n in names for x in results[n]['runs'] for a in x.get('strategy', {})})
    for action in actions:
        row(f'  {action}', lambda r, a=action: mean([x.get('strategy', {}).get(a, 0) for x in r]))

    section('Powers per game')
    powers = sorted({p for n in names for x in results[n]['runs'] for p in x.get('powers', {})})
    for power in powers:
        row(f'  {power.lower()}', lambda r, p=power: mean([x.get('powers', {}).get(p, 0) for x in r]), '{:.2f}')
    shots = sorted({s for n in names for x in results[n]['runs'] for s in x.get('shots', {})})
    for shot in shots:
        row(f'  shots {shot.lower()}', lambda r, s=shot: mean([x.get('shots', {}).get(s, 0) for x in r]), '{:.2f}')

    section('Birds lost per game')
    causes = sorted({c for n in names for x in results[n]['runs'] for c in x['birds_lost']})
    for cause in causes:
        row(f'  {cause}', lambda r, c=cause: mean([x['birds_lost'].get(c, 0) for x in r]), '{:.2f}')

    section('Enemies killed per game')
    kinds = sorted({k for n in names for x in results[n]['runs'] for k in x.get('kills', {})})
    for kind in kinds:
        row(f'  {kind}', lambda r, k=kind: mean([x.get('kills', {}).get(k, 0) for x in r]), '{:.2f}')

    section('Loot dropped per game')
    sources = sorted({s for n in names for x in results[n]['runs'] for s in x['drops_by_source']})
    for source in sources:
        row(f'  from {source}', lambda r, s=source: mean([x['drops_by_source'].get(s, 0) for x in r]))
    rows.append(('  by rarity (enemy drops only: Orange eggs and Cookie crumbs are fixed)', None))
    for rarity in RARITIES:
        row(f'  {rarity}', lambda r, k=rarity: mean([x['drops_by_rarity'][k] for x in r]), '{:.2f}')

    section('Eggs and cards per game')
    row('  eggs opened (game stopped to choose)', lambda r: mean([x.get('eggs_opened', 0) for x in r]), '{:.2f}')
    rows.append(('  cards taken, by rarity', None))
    for rarity in RARITIES:
        row(f'    {rarity}', lambda r, k=rarity: mean([x.get('cards_by_rarity', {}).get(k, 0) for x in r]), '{:.2f}')
    rows.append(('  cards taken, by kind', None))
    kinds = sorted({k for n in names for x in results[n]['runs'] for k in x.get('cards_by_kind', {})})
    for kind in kinds:
        row(f'    {kind}', lambda r, k=kind: mean([x.get('cards_by_kind', {}).get(k, 0) for x in r]), '{:.2f}')
    row('  pacts offered', lambda r: mean([x.get('pacts_offered', 0) for x in r]), '{:.2f}')
    row('  pacts made', lambda r: mean([len([p for p in x.get('pacts', []) if p != 'refuse']) for x in r]), '{:.2f}')

    section('Birds hatched from cards per game, by rarity (Orange eggs excluded)')
    for rarity in RARITIES:
        row(f'  {rarity}', lambda r, k=rarity: mean([x['hatched_by_rarity'][k] for x in r]), '{:.2f}')
    for rarity in RARITIES[2:]:
        row(
            f'  games with a {rarity} hatch',
            lambda r, k=rarity: 100 * mean([x['hatched_by_rarity'][k] > 0 for x in r]),
            '{:.0f}%',
        )

    row('  Orange re-hatching its own egg', lambda r: mean([x['hatched_from_orange'] for x in r]), '{:.2f}')

    section('Birds hatched (all games, Orange re-hatching included)')
    totals = {n: Counter(egg for x in results[n]['runs'] for egg in x['hatched']) for n in names}
    for egg in sorted({e for c in totals.values() for e in c}, key=lambda e: -sum(c[e] for c in totals.values())):
        rows.append((f'  {egg.replace("_egg", "")}', [str(totals[n][egg]) for n in names]))

    section('Bosses defeated (share of games that met them)')
    bosses = sorted(
        {b for n in names for x in results[n]['runs'] for b in x['bosses']}, key=lambda b: int(b.split('@')[1])
    )
    for boss in bosses:

        def beaten(r, b=boss):
            met = [x['bosses'][b] for x in r if b in x['bosses']]
            return 100 * mean([m['defeated'] is not None for m in met]) if met else 0

        row(f'  {boss.replace("@", " (level ")})', beaten, '{:.0f}%')

    width = max(len(label) for label, _ in rows) + 2
    columns = [max(len(n), 10) for n in names]
    lines = [' ' * width + '  '.join(n.rjust(w) for n, w in zip(names, columns))]
    for label, values in rows:
        if values is None:
            lines.append(label if label.startswith('  ') else f'\n{label}')
        else:
            lines.append(label.ljust(width) + '  '.join(v.rjust(w) for v, w in zip(values, columns)))
    return '\n'.join(lines)


if __name__ == '__main__':
    main()
