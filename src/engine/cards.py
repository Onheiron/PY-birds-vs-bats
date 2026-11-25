"""Cards: what an egg or a pact offers, and what picking one does.

Every enemy drop is an egg of a rarity (common ... mythical). Picking it up
stops the game and offers ``stats.flock('choices')`` cards (3 to start):

- the first card is of the egg's rarity, guaranteed;
- every other card rolls its rarity from ``cards.other_slots.<egg rarity>``,
  so a legendary egg has a legendary card, likely an epic and some rares, and
  never an uncommon or a common one.

Card kinds (``cards.catalog`` in config.yml):

  stat     a permanent bonus for the whole flock (a stat modifier)
  boost    a strong bonus for some seconds
  powerup  one of the old power-ups (tailwind, wide cursor, timelapse)
  training XP for every bird
  cursed   a big bonus with a drawback
  flock    a flock stat (more choices per egg, egg luck...)
  bird     hatch a bird of that rarity (only while a lane is free; from the
           egg tables ``eggs.rarity_candidates``)

Effect values in the catalog are those of a common card; rarer cards scale
them by ``cards.rarity_scale`` unless the effect says ``scale: false``.

Pacts (offered after a boss) use the same effects, with ``boon`` and ``bane``
lists scaled by ``pacts.intensity_by_boss``.
"""

import random

from src.core import constants, state
from src.engine import events, stats
from src.engine.enemy_stats import RARITIES
from src.entities.bird_types import get_bird_type_from_egg, get_color_for_bird_type

UNIQUE_BIRDS = ('WHITE', 'ORANGE', 'GOLD')

# Stats shown as percentages in card texts
_PERCENT = {
    'crit_chance',
    'affliction_chance',
    'fear_resist',
    'fear_immunity',
    'floor_save',
    'luck',
    'vs_bats',
    'vs_obstacles',
    'vs_elites',
    'egg_luck',
    'elite_chance',
}
_LABELS = {
    'speed': 'speed',
    'damage': 'damage',
    'rise_speed_bonus': 'rising speed',
    'fall_speed_bonus': 'falling speed',
    'bounce_sprint': 'bounce sprint',
    'weight': 'weight',
    'damage_bonus': 'damage',
    'damage_mult': 'damage',
    'vs_bats': 'damage vs bats',
    'vs_obstacles': 'damage vs obstacles',
    'vs_elites': 'damage vs elites',
    'armor_pierce': 'armor pierce',
    'crit_chance': 'crit chance',
    'crit_damage': 'crit damage',
    'affliction_chance': 'affliction chance',
    'knockback': 'knockback',
    'impact_stun': 'impact stun',
    'fear_resist': 'fear resistance',
    'fear_duration_mult': 'fear duration',
    'fear_duration_cut': 's of fear',
    'fear_immunity': 'fear immunity',
    'power_uses': 'power use per ascent',
    'power_potency': 'power strength',
    'power_duration': 'power duration',
    'floor_save': 'floor save',
    'prestige': 'prestige',
    'score_mult': 'score',
    'xp_gain': 'XP',
    'pickup_radius': 'pickup radius',
    'luck': 'lucky finds (a collected egg turns rarer)',
    'choices': 'choice per egg',
    'egg_luck': 'luck (rarer drops)',
    'elite_chance': 'elite bats',
    'prestige_bonus': 'prestige',
    'prestige_mult': 'prestige',
}
# Stats where a lower value is better (for colouring the text of a drawback)
_LOWER_IS_BETTER = {'fall_speed_bonus', 'impact_stun', 'fear_duration_mult', 'elite_chance'}
_ENEMY_LABELS = {
    'hp_mult': 'bat HP',
    'defense': 'bat defence',
    'armor': 'bat armor',
    'regen': 'bat regeneration',
    'fear_strength': 'bat fear',
    'speed': 'bat speed',
    'damage_taken': 'damage bats take',
}


def _cfg(section):
    return getattr(constants, section, None)


def _as_dict(node):
    if node is None:
        return {}
    return node if isinstance(node, dict) else vars(node)


def _list(node):
    return list(node) if node is not None else []


def rarity_scale(rarity):
    return float(_as_dict(getattr(_cfg('cards'), 'rarity_scale', None)).get(rarity, 1.0))


# ---------------------------------------------------------------------------
# Effects
# ---------------------------------------------------------------------------


def scale_effect(effect, factor):
    """An effect with its values multiplied by ``factor`` (``pct`` and ``add``; not when scale is false)."""
    effect = dict(_as_dict(effect))
    if effect.get('scale', True) is False or factor == 1:
        return effect
    for key in ('add', 'pct', 'xp'):
        if key in effect:
            effect[key] = effect[key] * factor
    if 'enemy' in effect:
        effect['enemy'] = {k: v * factor for k, v in _as_dict(effect['enemy']).items()}
    return effect


def _enemy_layer(changes):
    """Pact changes to enemies: ``pct`` for multiplier stats, plain numbers otherwise."""
    from src.engine.enemy_stats import MULTIPLIERS

    layer = {}
    for name, value in _as_dict(changes).items():
        layer[name] = 1 + value / 100 if name in MULTIPLIERS else value
    return layer


def apply_effect(effect, source=''):
    """Apply one effect to the flock (or to the enemies, for an ``enemy`` effect)."""
    if 'stat' in effect:
        mul = 1 + effect['pct'] / 100 if 'pct' in effect else 1.0
        seconds = effect.get('seconds')
        if seconds:
            seconds *= stats.duration_mult()  # power duration lengthens timed cards too
        stats.add_modifier('flock', effect['stat'], add=effect.get('add', 0.0), mul=mul, seconds=seconds, source=source)
    if 'enemy' in effect:
        state.stats.enemy_layers.append(_enemy_layer(effect['enemy']))
    if 'xp' in effect:
        from src.engine.progression import award_xp

        for i in range(constants.layout.num_balls):
            if not state.birds.lost[i]:
                award_xp(i, effect['xp'])
    if 'powerup' in effect:
        from src.engine.logic.loot import apply_powerup

        apply_powerup(effect['powerup'])
    for allowance in ('rerolls', 'skips'):
        if allowance in effect:
            from src.engine import choices

            getattr(choices, f'{allowance}_left')()
            setattr(state.choice, allowance, getattr(state.choice, allowance) + int(effect[allowance]))


def _number(value):
    value = round(value, 2)
    return f'{value:g}'


def describe_effect(effect):
    """('text', good) for one effect, e.g. ('+12% damage', True)."""
    if 'powerup' in effect:
        return _POWERUP_TEXT.get(effect['powerup'].rstrip('+').replace('_max', ''), effect['powerup']), True
    if 'xp' in effect:
        return f"+{_number(effect['xp'])} XP to every bird", True
    for allowance, label in (('rerolls', 'reroll'), ('skips', 'skip')):
        if allowance in effect:
            n = int(effect[allowance])
            return f"+{n} egg {label}{'s' if n != 1 else ''} this run", True
    if 'enemy' in effect:
        parts = []
        good = True
        for name, value in _as_dict(effect['enemy']).items():
            from src.engine.enemy_stats import MULTIPLIERS

            sign = '+' if value >= 0 else '−'
            unit = '%' if name in MULTIPLIERS else ''
            parts.append(f'{sign}{_number(abs(value))}{unit} {_ENEMY_LABELS.get(name, name)}')
            good = good and (value < 0) != (name == 'damage_taken')
        return ', '.join(parts), good
    stat = effect['stat']
    label = _LABELS.get(stat, stat.replace('_', ' '))
    if 'pct' in effect:
        value, unit = effect['pct'], '%'
    elif stat in _PERCENT:
        value, unit = effect.get('add', 0) * 100, '%'
    else:
        value, unit = effect.get('add', 0), ''
    sign = '+' if value >= 0 else '−'
    good = (value >= 0) != (stat in _LOWER_IS_BETTER)
    text = f'{sign}{_number(abs(value))}{unit} {label}'
    if effect.get('seconds'):
        text += f" for {_number(effect['seconds'] * stats.duration_mult())} s"
    return text, good


_POWERUP_TEXT = {
    'tailwind': 'Tailwind: the flock rises faster',
    'wide_cursor': 'Wide cursor: bounce more lanes at once',
    'timelapse': 'Timelapse: the game slows down',
}


def _powerup_lines(loot_type):
    from src.engine.logic.loot import powerup_details

    d = powerup_details(loot_type)
    if loot_type.startswith('tailwind'):
        return [
            (f"Rising birds +{_number(d['tailwind_up_bonus'] * 10)} speed", True),
            (f"Falling birds −{_number(d['tailwind_down_penalty'] * 10)} speed", True),
        ]
    if loot_type.startswith('wide_cursor'):
        return [(f"Bounce {d['wide_cursor_lanes']} lanes with one press", True)]
    if loot_type.startswith('timelapse'):
        return [(f"The game runs {_number(d['slowdown'])}× slower", True)]
    return []


def card_lines(card):
    """The effect lines of a card: [(text, good), ...]."""
    if card['kind'] == 'bird':
        speed = stats.type_value(card['bird'], 'speed')
        damage = stats.type_value(card['bird'], 'damage')
        return [(f'Speed {_number(speed)} · Damage {_number(damage)}', True)]
    lines = []
    for effect in card['effects'] + card.get('drawbacks', []):
        if 'powerup' in effect:
            lines += _powerup_lines(effect['powerup'])
        else:
            text, good = describe_effect(effect)
            if effect.get('seconds'):
                text = text.rsplit(' for ', 1)[0]
            lines.append((text, good))
    return lines


_KIND_LABELS = {
    'stat': 'Flock bonus',
    'boost': 'Boost',
    'powerup': 'Power-up',
    'training': 'Training',
    'cursed': 'Cursed',
    'flock': 'Nest',
    'bird': 'New bird',
    'pact': 'Pact',
    'refuse': '',
}

# One line about what each bird does, for bird cards
BIRD_BLURBS = {
    'YELLOW': 'Its power bounces falling neighbours.',
    'RED': 'Its power fires a shot up its lane.',
    'BLUE': 'Its power is a 3 s sprint.',
    'PATCHWORK': 'Counts as a Yellow and as a Red.',
    'PURPLE': 'Charged shot, up to 64× damage.',
    'CLOCKWORK': 'Bounces by itself while charged.',
    'WHITE': "Fires its neighbours' powers.",
    'ORANGE': 'Kills anything in one hit.',
    'GOLD': 'Scores 100 per move.',
    'COOKIE': 'Drops XP crumbs for the others.',
    'STEALTH': 'Passes through everything.',
    'DINOSAUR': 'Huge and tough: 15 presses to bounce.',
    'GLITCH': 'Random speed, damage and prestige.',
    'RAINBOW': 'Wraps from the floor to the ceiling.',
    'TWISTER': 'Tailwind for nearby lanes.',
    'FROSTY': 'Freezes the bats it hits.',
    'POISON': 'Poisons the bats it hits.',
    'BERSERK': 'Makes the bats it hits bleed.',
    'ROCK': 'Pushes bats back up.',
}


def _seconds_of(card):
    for effect in card['effects']:
        if effect.get('seconds'):
            return effect['seconds'] * stats.duration_mult()
        if 'powerup' in effect:
            from src.engine.logic.loot import powerup_details

            return powerup_details(effect['powerup']).get('seconds')
    return None


def card_info(card):
    """Everything a card shows: {'name', 'rarity', 'kind', 'duration', 'text', 'lines'}."""
    kind = card['kind']
    if kind == 'ware':  # the merchant's (src/engine/merchant.py)
        from src.engine import meta

        affordable = card['price'] <= meta.run_gold()
        return {
            'name': card['name'],
            'rarity': card['rarity'],
            'kind': 'Merchant',
            'duration': '',
            'text': card.get('desc', ''),
            'lines': [(f"Price {card['price']} ❖ (this run has {meta.run_gold()})", affordable)],
        }
    seconds = _seconds_of(card)
    if kind == 'bird':
        duration = 'Hatches now'
    elif kind == 'training':
        duration = 'Instant'
    elif kind == 'refuse':
        duration = ''
    elif seconds:
        duration = f'{_number(seconds)} s'
    else:
        duration = 'Permanent'
    if kind == 'bird':
        text = BIRD_BLURBS.get(card['bird'], '')
    elif kind == 'refuse':
        text = 'Keep things as they are.'
    else:
        text = card.get('desc', '')
    if limited(card) and card.get('id'):
        # Which level this pick reaches, of the most the run allows
        duration = f"Lv {state.choice.levels.get(card['id'], 0) + 1}/{max_level()} · {duration}"
    return {
        'name': card['name'],
        'rarity': card['rarity'],
        'kind': _KIND_LABELS.get(kind, kind.title()),
        'duration': duration,
        'text': text,
        'lines': [] if kind == 'refuse' else card_lines(card),
    }


# ---------------------------------------------------------------------------
# Egg offers
# ---------------------------------------------------------------------------


def _catalog():
    return _as_dict(getattr(_cfg('cards'), 'catalog', None))


def _allowed(entry, rarity):
    entry = _as_dict(entry)
    index = RARITIES.index(rarity)
    low = RARITIES.index(entry.get('min_rarity', 'common'))
    high = RARITIES.index(entry.get('max_rarity', 'mythical'))
    return low <= index <= high


def _make_card(card_id, entry, rarity):
    entry = _as_dict(entry)
    factor = rarity_scale(rarity)
    card = {
        'id': card_id,
        'name': entry.get('name', card_id.replace('_', ' ').title()),
        'kind': entry.get('kind', 'stat'),
        'rarity': rarity,
        'effects': [scale_effect(e, factor) for e in _list(entry.get('effects'))],
        'drawbacks': [scale_effect(e, factor) for e in _list(entry.get('drawbacks'))],
        'desc': entry.get('desc', ''),
    }
    if card['kind'] == 'powerup':
        # Rarer cards give a stronger tier of the power-up
        top = '++' if entry['powerup'] == 'timelapse' else '_max'
        suffix = {'common': '', 'uncommon': '+', 'rare': '++'}.get(rarity, top)
        card['effects'] = [{'powerup': entry['powerup'] + suffix}]
    return card


def free_slots():
    return sum(1 for lost in state.birds.lost if lost)


def _bird_candidates(rarity):
    """Bird types that can hatch from a card of ``rarity`` now, with their weights."""
    if free_slots() <= 0:
        return {}
    table = _as_dict(_as_dict(getattr(_cfg('eggs'), 'rarity_candidates', None)).get(rarity))
    living = {state.birds.colors[i] for i in range(constants.layout.num_balls) if not state.birds.lost[i]}
    out = {}
    for egg, weight in table.items():
        bird_type = get_bird_type_from_egg(egg)
        if bird_type is None:
            continue
        if bird_type in UNIQUE_BIRDS and get_color_for_bird_type(bird_type) in living:
            continue
        out[bird_type] = float(weight)
    return out


# ---------------------------------------------------------------------------
# Card levels: a card type can be taken card_max_level times a run, and a run
# follows at most card_types types (flock stats: upgrades raise them). Timed
# boosts, power-ups, training and birds are not limited.
# ---------------------------------------------------------------------------

UNLIMITED_KINDS = ('boost', 'powerup', 'training', 'bird', 'refuse', 'pact')


def limited(entry_or_card):
    return _as_dict(entry_or_card).get('kind', 'stat') not in UNLIMITED_KINDS


def max_level():
    return int(stats.flock('card_max_level'))


def max_types():
    return int(stats.flock('card_types'))


def can_take(card_id, entry):
    """Can a card of this type still be offered (below its max level; a new type only if there is room)?"""
    if not limited(entry):
        return True
    levels = state.choice.levels
    if card_id in levels:
        return levels[card_id] < max_level()
    return len(levels) < max_types()


def took(card):
    """Count a picked card towards its type's level."""
    if limited(card) and card.get('id'):
        state.choice.levels[card['id']] = state.choice.levels.get(card['id'], 0) + 1


def anything_to_offer():
    """Is there still a lasting card or a bird to offer? (else enemies drop no eggs)"""
    if any(limited(e) and can_take(cid, e) for cid, e in _catalog().items()):
        return True
    return any(_bird_candidates(r) for r in RARITIES)


def _roll_bird(rarity, taken, rng):
    """A bird card of ``rarity`` (a free slot and a bird of that rarity needed), or None."""
    birds = {b: w for b, w in _bird_candidates(rarity).items() if f'bird:{b}' not in taken}
    if not birds:
        return None
    names = sorted(birds)
    bird_type = rng.choices(names, weights=[birds[n] for n in names])[0]
    return {
        'id': f'bird:{bird_type}',
        'name': f'{bird_type.title()} Egg',
        'kind': 'bird',
        'rarity': rarity,
        'bird': bird_type,
        'effects': [],
        'drawbacks': [],
    }


def _roll_card(rarity, taken, rng):
    """One card of ``rarity`` not already in ``taken`` (ids), or None.

    Mythical cards are birds only: power-ups stop at legendary.
    """
    cfg = _cfg('cards')
    pool = [(cid, e) for cid, e in _catalog().items() if cid not in taken and _allowed(e, rarity) and can_take(cid, e)]
    if rarity == 'mythical':
        pool = []
    weights = [float(_as_dict(e).get('weight', 1)) for _, e in pool]
    birds = {b: w for b, w in _bird_candidates(rarity).items() if f'bird:{b}' not in taken}
    if birds:
        # Birds as a whole weigh bird_weight against the other cards of this rarity
        bird_total = float(getattr(cfg, 'bird_weight', 3)) if pool else 1.0
        pool.append(('bird', None))
        weights.append(bird_total)
    if not pool:
        return None
    card_id, entry = rng.choices(pool, weights=weights)[0]
    if card_id == 'bird':
        return _roll_bird(rarity, taken, rng)
    return _make_card(card_id, entry, rarity)


def _bird_wanted(rng):
    """Should this egg offer a bird? (cards.bird_chance_by_free_slots: 1 free slot, 2, 3 or more)"""
    free = free_slots()
    if free <= 0:
        return False
    table = _list(getattr(_cfg('cards'), 'bird_chance_by_free_slots', None)) or [0.6, 0.6, 1.0]
    chance = float(table[min(free, len(table)) - 1])
    return chance >= 1 or rng.random() < chance


def other_slot_rarity(egg_rarity, rng):
    """Rarity of a non-guaranteed card of an egg of ``egg_rarity``."""
    table = _as_dict(getattr(_cfg('cards'), 'other_slots', None))
    weights = _list(table.get(egg_rarity)) or [1, 0, 0, 0, 0, 0]
    return rng.choices(RARITIES, weights=weights)[0]


def roll_offer(egg_rarity, rng=random):
    """The cards an egg of ``egg_rarity`` offers (the first one of that rarity)."""
    count = int(stats.flock('choices'))
    cards, taken = [], set()
    rarities = [egg_rarity] + [other_slot_rarity(egg_rarity, rng) for _ in range(count - 1)]
    # Rarest first, so the guaranteed card leads
    rarities.sort(key=RARITIES.index, reverse=True)
    for rarity in rarities:
        card = None
        # Fall back to a commoner rarity when nothing of this one is left
        for r in RARITIES[RARITIES.index(rarity) :: -1]:
            card = _roll_card(r, taken, rng)
            if card:
                break
        if card:
            cards.append(card)
            taken.add(card['id'])
    # With free slots in the flock, an egg offers a bird often (always with 3 or more)
    if cards and not any(c['kind'] == 'bird' for c in cards) and _bird_wanted(rng):
        for r in RARITIES[RARITIES.index(egg_rarity) :: -1]:
            bird = _roll_bird(r, taken, rng)
            if bird:
                cards[-1] = bird
                break
    return cards


def roll_birds(egg_rarity, rng=random):
    """Only bird cards (the merchant's brood): as many as an egg offers, of ``egg_rarity`` or
    commoner, while there are free slots and birds to hatch."""
    cards, taken = [], set()
    for _ in range(int(stats.flock('choices'))):
        for r in RARITIES[RARITIES.index(egg_rarity) :: -1]:
            bird = _roll_bird(r, taken, rng)
            if bird:
                cards.append(bird)
                taken.add(bird['id'])
                break
    return cards


def apply_card(card):
    """Do what the picked card says."""
    source = f"card:{card['id']}"
    if card['kind'] == 'bird':
        from src.engine.logic.loot import hatch_bird

        hatch_bird(card['bird'], {'type': f"{card['bird'].lower()}_egg", 'rarity': card['rarity']})
        return
    for effect in card['effects'] + card.get('drawbacks', []):
        apply_effect(effect, source)
    events.emit('card_picked', card=card)


# ---------------------------------------------------------------------------
# Pacts
# ---------------------------------------------------------------------------


def _pact_cfg():
    return _cfg('pacts')


def pact_intensity(boss_number):
    table = _list(getattr(_pact_cfg(), 'intensity_by_boss', None)) or [1]
    return float(table[min(max(1, boss_number), len(table)) - 1])


def roll_pacts(boss_number, rng=random):
    """The pacts offered after the ``boss_number``-th biome boss (1-6)."""
    cfg = _pact_cfg()
    by_boss = _as_dict(getattr(cfg, 'by_boss', None))
    ids = _list(by_boss.get(boss_number, by_boss.get(str(boss_number))))
    catalog = _as_dict(getattr(cfg, 'catalog', None))
    ids = [i for i in ids if i in catalog and i not in state.stats.pacts]
    count = min(len(ids), int(getattr(cfg, 'offered', 3)))
    factor = pact_intensity(boss_number)
    pacts = []
    for pact_id in rng.sample(ids, count):
        entry = _as_dict(catalog[pact_id])
        pacts.append(
            {
                'id': pact_id,
                'name': entry.get('name', pact_id.replace('_', ' ').title()),
                'kind': 'pact',
                'rarity': RARITIES[min(len(RARITIES) - 1, boss_number - 1)],
                'effects': [scale_effect(e, factor) for e in _list(entry.get('boon'))],
                'drawbacks': [scale_effect(e, factor) for e in _list(entry.get('bane'))],
                'desc': entry.get('desc', ''),
            }
        )
    return pacts


def apply_pact(pact):
    source = f"pact:{pact['id']}"
    for effect in pact['effects'] + pact['drawbacks']:
        apply_effect(effect, source)
    state.stats.pacts.append(pact['id'])
    events.emit('pact_made', pact=pact)
