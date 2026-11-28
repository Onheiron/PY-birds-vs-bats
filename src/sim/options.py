"""Command-line options shared by the simulator and the watch mode."""

import yaml

DIFFICULTIES = {
    'peaceful': 0,
    'easy': 0,
    'adventure': 1,
    'normal': 1,
    'survival': 2,
    'hard': 2,
    'legendary': 3,
    'hell': 3,
}


def parse_assignments(text):
    """'a.b=1; c=[1,2]' -> {'a': {'b': 1}, 'c': [1, 2]} (values parsed as YAML)."""
    result = {}
    for part in filter(None, (p.strip() for p in text.split(';'))):
        if '=' not in part:
            raise SystemExit(f'expected key=value, got {part!r}')
        key, value = part.split('=', 1)
        node = result
        *parents, leaf = key.strip().split('.')
        for name in parents:
            node = node.setdefault(name, {})
        node[leaf] = yaml.safe_load(value)
    return result


def merge(base, extra):
    out = dict(base)
    for key, value in extra.items():
        out[key] = merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def add_game_options(parser, bot_default='expert'):
    """Options that describe one game and the bot playing it."""
    parser.add_argument(
        '--bot',
        default=bot_default,
        metavar='PROFILE',
        help=f'bot skill: perfect, expert, average, novice, me (plays like you: tools/fit_bot.py) '
        f'(default {bot_default})',
    )
    parser.add_argument(
        '--bot-set',
        action='append',
        default=[],
        metavar='FIELD=VALUE',
        help='change one skill field, e.g. key_interval=3 (repeatable)',
    )
    parser.add_argument(
        '--strategy',
        metavar='NAME',
        help='bot strategy from src/sim/strategy.py: brake, red_battery, yellow_guard, white_center, '
        'few_birds, favorites, adaptive, cautious...',
    )
    parser.add_argument('--seed', type=int, default=1, help='game seed (default 1)')
    parser.add_argument('--difficulty', default='adventure', choices=sorted(DIFFICULTIES))
    parser.add_argument(
        '--set',
        action='append',
        default=[],
        metavar='KEY=VALUE',
        help='configuration override, e.g. speed.mph_per_level=60 (repeatable)',
    )
    parser.add_argument('--formation', help='starting flock, e.g. RED,RED,BLUE,...')
    parser.add_argument('--start-level', type=int, default=1, help='level to start from (1-18)')


def skill_from(args):
    from src.sim.bot import PROFILES, profile

    if args.bot not in PROFILES:
        raise SystemExit(f'unknown bot profile {args.bot!r}; choose from {", ".join(PROFILES)}')
    from src.sim.strategy import STRATEGIES

    changes = {}
    strategy = getattr(args, 'strategy', None)
    if strategy:
        if strategy not in STRATEGIES:
            raise SystemExit(f'unknown strategy {strategy!r}; choose from {", ".join(STRATEGIES)}')
        changes.update(STRATEGIES[strategy])
    for item in args.bot_set:
        changes.update(parse_assignments(item))
    for name in ('favorites', 'build_stats'):
        if name in changes:
            changes[name] = tuple(changes[name])
    return profile(args.bot, **changes)


def overrides_from(args):
    overrides = {}
    for item in args.set:
        overrides = merge(overrides, parse_assignments(item))
    return overrides


def formation_from(args):
    return [bird.strip().upper() for bird in args.formation.split(',')] if args.formation else None
