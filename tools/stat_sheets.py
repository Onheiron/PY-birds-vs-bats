#!/usr/bin/env python3
"""Print the stat sheet of every bird and every enemy, as Markdown tables.

The values are read from the game itself (config.yml through the stat
engine), so the output is always what the game uses.

    python3 tools/stat_sheets.py                 # all sheets
    python3 tools/stat_sheets.py --grade A1      # birds at another grade
    python3 tools/stat_sheets.py --config my.yml
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BIRD_GROUPS = [
    (
        'Base and movement',
        [
            ('speed', 'Speed'),
            ('rise_speed_bonus', 'Rise +'),
            ('fall_speed_bonus', 'Fall +'),
            ('bounce_sprint', 'Bounce sprint'),
            ('bounce_sprint_seconds', 'Sprint s'),
            ('weight', 'Weight'),
            ('presses_to_bounce', 'Presses'),
            ('hitbox_width', 'Width'),
            ('hitbox_height', 'Height'),
        ],
    ),
    (
        'Attack',
        [
            ('damage', 'Damage'),
            ('damage_bonus', 'Dmg +'),
            ('damage_mult', 'Dmg ×'),
            ('speed_damage', 'Speed weight'),
            ('vs_bats', 'vs bats'),
            ('vs_obstacles', 'vs obstacles'),
            ('vs_elites', 'vs elites'),
            ('armor_pierce', 'Pierce'),
            ('crit_chance', 'Crit %'),
            ('crit_damage', 'Crit ×'),
            ('affliction_chance', 'Affliction %'),
            ('knockback', 'Knockback'),
            ('impact_stun', 'Impact stun ×'),
        ],
    ),
    (
        'Fear, power and survival',
        [
            ('fear_resist', 'Fear resist %'),
            ('fear_duration_mult', 'Fear time ×'),
            ('fear_duration_cut', 'Fear −s'),
            ('fear_immunity', 'Fear immunity %'),
            ('power_uses', 'Power uses'),
            ('power_potency', 'Potency ×'),
            ('power_duration', 'Power time ×'),
            ('floor_save', 'Floor save %'),
        ],
    ),
    (
        'Economy',
        [
            ('prestige', 'Prestige'),
            ('score_mult', 'Score ×'),
            ('score_grade_bonus', 'Grade bonus'),
            ('xp_gain', 'XP ×'),
            ('pickup_radius', 'Pickup'),
            ('luck', 'Luck %'),
        ],
    ),
]
PERCENT = {
    'crit_chance',
    'affliction_chance',
    'fear_resist',
    'fear_immunity',
    'floor_save',
    'luck',
    'vs_bats',
    'vs_obstacles',
    'vs_elites',
}
ENEMY_COLUMNS = [
    ('hp', 'HP'),
    ('defense', 'Defence'),
    ('contact_defense', 'Contact def'),
    ('projectile_defense', 'Projectile def'),
    ('armor', 'Armor'),
    ('damage_taken', 'Dmg taken ×'),
    ('regen', 'Regen/s'),
    ('fear_strength', 'Fear ×'),
    ('fear_radius', 'Fear radius'),
    ('speed', 'Speed ×'),
    ('descent_interval', 'Descent'),
    ('fear_push', 'Fear push'),
    ('linger', 'Stays (s)'),
    ('stun', 'Stun (s)'),
    ('knock', 'Knock'),
    ('fall_interval', 'Fall (ticks/row)'),
    ('xp_mult', 'XP ×'),
    ('score_mult', 'Score ×'),
    ('loot_rarity_bonus', 'Drop +'),
]


def fmt(name, value):
    if name in PERCENT:
        pct = round(value * 100, 1)
        return f'{pct:g}%' if name.startswith('vs_') is False else (f'+{pct:g}%' if pct else '0')
    if isinstance(value, float):
        value = round(value, 2)
        return f'{value:g}'
    return str(value)


def table(header, rows):
    lines = ['| ' + ' | '.join(header) + ' |', '|' + '|'.join([':--'] + [':-:'] * (len(header) - 1)) + '|']
    lines += ['| ' + ' | '.join(row) + ' |' for row in rows]
    return '\n'.join(lines)


def bird_sheets(grade):
    from src.engine import stats
    from src.engine.grades import compute_grade_from_xp
    from src.entities import sprites
    from src.entities.bird_types import BIRD_TYPES
    from tests.harness import Simulation

    out = []
    with Simulation(seed=1, key_rate=0) as sim:
        xp = 0
        while compute_grade_from_xp(xp)[0] != grade:
            xp += max(1, xp // 20)
        values = {}
        for bird_type in BIRD_TYPES:
            sim.state.birds.colors[0] = getattr(sprites, bird_type)
            sim.state.birds.per_bird_xp[0] = xp
            values[bird_type] = stats.describe(0)
    for title, columns in BIRD_GROUPS:
        rows = [[t.title()] + [fmt(n, values[t][n]) for n, _ in columns] for t in values]
        out.append(f'#### {title}\n\n' + table(['Bird'] + [label for _, label in columns], rows))
    return '\n\n'.join(out)


def enemy_sheets():
    from src.core import constants
    from src.engine import enemy_stats
    from tests.harness import Simulation

    def hp_of(table_node, tier):
        node = table_node if isinstance(table_node, dict) else vars(table_node)
        return node.get(tier, node.get(str(tier)))

    rows = []
    with Simulation(seed=1, key_rate=0):
        bat_hp = constants.bat_enemy.hp_by_tier
        kinds = [
            ('Mini bat', None, [0]),
            ('Bat', None, [1, 2, 3, 4]),
            ('Armored', 'armored', [2, 3, 4]),
            ('Diver', 'diver', [1, 2, 3, 4]),
            ('Spellcaster', 'spellcaster', [2, 3, 4]),
            ('Healer', 'healer', [2, 3, 4]),
            ('Bomber', 'bomber', [2, 3, 4]),
            ('Plague', 'plague', [2, 3, 4]),
            ('Necromancer', 'necromancer', [3, 4]),
        ]
        ability_rows = []
        for label, kind, tiers in kinds:
            for tier in tiers:
                bat = {'tier': tier, 'hp': hp_of(bat_hp, tier), 'max_hp': hp_of(bat_hp, tier)}
                if kind:
                    bat['kind'] = kind
                enemy_stats.equip_bat(bat)
                row = [f'{label} T{tier}']
                for name, _ in ENEMY_COLUMNS:
                    row.append(str(bat['max_hp']) if name == 'hp' else fmt(name, enemy_stats.get(bat, name)))
                rows.append(row)
                if kind and tier == tiers[-1]:
                    used = list(ABILITY_STATS.get(kind, ()))
                    ability_rows.append([label] + ['; '.join(f'{n} {fmt(n, enemy_stats.get(bat, n))}' for n in used)])
        obs_rows = []
        names = {1: 'Tree', 2: 'Rock', 3: 'Cloud', 4: 'Barrier'}
        specials = [(None, tier) for tier in (1, 2, 3, 4)] + [('stalactite', 1), ('peak', 4)]
        for kind, tier in specials:
            obstacle = {'tier': tier, 'hp': hp_of(constants.obstacle.hp_by_tier, tier)}
            if kind:
                obstacle['kind'] = kind
            enemy_stats.equip_obstacle(obstacle)
            row = [f'{kind.title()} (T{tier} base)' if kind else f'{names[tier]} T{tier}']
            for name, _ in ENEMY_COLUMNS:
                if name == 'hp':
                    row.append(f"{obstacle['hp']} (+10%/level)")
                else:
                    row.append(fmt(name, enemy_stats.get(obstacle, name)))
            obs_rows.append(row)
    header = ['Enemy'] + [label for _, label in ENEMY_COLUMNS]
    return (
        '#### Bats\n\n'
        + table(header, rows)
        + '\n\n#### Bat abilities (highest tier, world 1 values; worlds change them)\n\n'
        + table(['Kind', 'Ability stats'], ability_rows)
        + '\n\n#### Obstacles\n\n'
        + table(header, obs_rows)
    )


# The ability stats each kind uses
ABILITY_STATS = {
    'armored': ('armor', 'fear_push', 'linger', 'move_step'),
    'diver': (
        'ability_chance',
        'ability_interval',
        'dive_rows',
        'dive_interval',
        'dive_stun',
        'return_interval',
        'dive_push',
        'dive_push_time',
    ),
    'spellcaster': (
        'ability_chance',
        'ability_interval',
        'cast_time',
        'spells',
        'silence_time',
        'wind_time',
        'wind_push',
    ),
    'healer': ('ability_chance', 'ability_interval', 'heal_pct', 'heal_range'),
    'bomber': ('ability_chance', 'ability_interval', 'stone_hp', 'stone_interval', 'stone_stun'),
    'plague': ('plague_time', 'plague_presses', 'plague_spread'),
    'necromancer': ('ability_chance', 'ability_interval', 'zombies', 'zombie_fear'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--grade', default='D', help='grade of the birds (D, C1 ... S)')
    parser.add_argument('--config', help='config file to read instead of config.yml')
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.config:
        sys.argv = [sys.argv[0], '--config', args.config]
    else:
        sys.argv = sys.argv[:1]
    print(f'### Birds (grade {args.grade})\n')
    print(bird_sheets(args.grade))
    print('\n### Enemies\n')
    print(enemy_sheets())


if __name__ == '__main__':
    main()
