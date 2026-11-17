#!/usr/bin/env python3
"""Play campaigns: runs one after the other, with the gold spent on upgrades in between.

Each campaign starts from a new profile. After every run the bot spends its
gold on upgrades (``--buy``), and the next run starts with them. The report
shows, run by run, how far players get and how often they pass each world:
this is how the meta progression is tuned ("the first runs rarely pass the
second world").

    python3 tools/campaign.py --campaigns 12 --runs 15 --bot average
    python3 tools/campaign.py --campaigns 12 --runs 15 --bot expert --buy talons

Buying policies: cheapest (cheapest upgrade it can buy, again and again),
balanced (the branch with the fewest levels first), or a branch name
(talons, wings, nerve, nest, fortune) to buy first.
"""

import argparse
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

WORLD_LEVELS = {2: 4, 3: 7, 4: 10, 5: 13, 6: 16}  # world -> first level of it


def spend(profile_meta, policy):
    """Spend the profile's gold on upgrades with ``policy``; returns what was bought."""
    meta = profile_meta
    bought = []
    while True:
        options = [u for u in meta.upgrades() if meta.can_buy(u)]
        if not options:
            return bought

        def branch(u):
            entry = meta.upgrades()[u]
            return (entry if isinstance(entry, dict) else vars(entry)).get('branch', '').lower()

        if policy == 'balanced':
            levels = {}
            for u in meta.upgrades():
                levels[branch(u)] = levels.get(branch(u), 0) + meta.level_of(u)
            choice = min(options, key=lambda u: (levels[branch(u)], meta.cost(u)))
        elif policy == 'cheapest':
            choice = min(options, key=meta.cost)
        else:
            choice = min(options, key=lambda u: (branch(u) != policy, meta.cost(u)))
        meta.buy(choice, save=False)
        bought.append(choice)


def play_campaign(args):
    seed, runs, bot_name, policy, max_minutes, overrides = args
    os.environ['HOME'] = os.environ['USERPROFILE'] = tempfile.mkdtemp(prefix='bvb-campaign-')
    sys.argv = sys.argv[:1]
    from src.core import state
    from src.engine import meta
    from src.sim.bot import PROFILES
    from src.sim.runner import RunConfig, run

    profile = meta.new_profile()
    history = []
    for k in range(runs):
        summary = run(
            RunConfig(
                seed=seed * 1000 + k,
                skill=PROFILES[bot_name],
                max_minutes=max_minutes,
                profile=profile,
                overrides=overrides,
            )
        ).summary()
        profile = summary['profile']
        state.meta.profile = profile
        bought = spend(meta, policy)
        profile = meta.snapshot()
        history.append(
            {
                'run': k + 1,
                'level': summary['level'],
                'minutes': summary['minutes'],
                'gold': summary['gold'],
                'gold_total': profile.get('gold_earned', 0),
                'upgrades': sum(profile.get('upgrades', {}).values()),
                'bought': bought,
            }
        )
    return history


def report(campaigns, runs):
    lines = [f'# Campaigns ({len(campaigns)} players, {runs} runs each)\n']
    head = (
        '| Run | Median level | Best | '
        + ' | '.join(f'World {w}+' for w in WORLD_LEVELS)
        + ' | Gold (run) | Upgrade levels |'
    )
    lines += [head, '|' + '---|' * (5 + len(WORLD_LEVELS))]
    for k in range(runs):
        at = [c[k] for c in campaigns if len(c) > k]
        levels = [r['level'] for r in at]
        worlds = ' | '.join(
            f'{100 * sum(lv >= first for lv in levels) / len(levels):.0f}%' for first in WORLD_LEVELS.values()
        )
        lines.append(
            f'| {k + 1} | {statistics.median(levels):g} | {max(levels)} | {worlds} | '
            f'{statistics.median(r["gold"] for r in at):g} | {statistics.median(r["upgrades"] for r in at):g} |'
        )
    first = {}
    for world, level in WORLD_LEVELS.items():
        reached = [next((r['run'] for r in c if r['level'] >= level), None) for c in campaigns]
        done = [x for x in reached if x is not None]
        first[world] = (len(done), statistics.median(done) if done else None)
    lines.append('\nFirst run that reaches each world (players who did / median run):\n')
    for world, (n, med) in first.items():
        lines.append(f'- World {world}: {n}/{len(campaigns)} players, median run {med if med is not None else "-"}')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.split('\n\n')[0],
        epilog=__doc__.split('\n\n', 1)[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--campaigns', type=int, default=12, help='players (default 12)')
    parser.add_argument('--runs', type=int, default=15, help='runs per player (default 15)')
    parser.add_argument('--bot', default='average', help='bot skill (default average)')
    parser.add_argument('--buy', default='balanced', help='upgrade policy (default balanced)')
    parser.add_argument('--max-minutes', type=float, default=30.0, help='game-time limit per run (default 30)')
    parser.add_argument('--set', action='append', default=[], metavar='KEY=VALUE', help='configuration override')
    parser.add_argument('--jobs', type=int, default=0)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--json', metavar='FILE')
    args = parser.parse_args(argv)
    os.chdir(ROOT)
    from src.sim.options import parse_assignments

    overrides = {}
    for item in args.set:
        overrides.update(parse_assignments(item))
    jobs = args.jobs or os.cpu_count() or 1
    tasks = [(args.seed + c, args.runs, args.bot, args.buy, args.max_minutes, overrides) for c in range(args.campaigns)]
    print(f'Playing {args.campaigns} campaigns of {args.runs} runs ({args.bot} bot) on {jobs} processes...', flush=True)
    import multiprocessing

    with multiprocessing.get_context('spawn').Pool(jobs) as pool:
        campaigns = pool.map(play_campaign, tasks, chunksize=1)
    print(report(campaigns, args.runs))
    if args.json:
        Path(args.json).write_text(json.dumps(campaigns, indent=1))
        print(f'\nCampaigns written to {args.json}')


if __name__ == '__main__':
    main()
