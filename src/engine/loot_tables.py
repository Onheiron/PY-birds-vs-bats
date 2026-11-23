"""Loot tables: rarity weights and drop selection."""

import random

from src.core import constants


def adjust_rarity_weights(base_weights, prestige):
    """Adjust loot rarity weights based on prestige and difficulty mode.

    Formula: weight[i] = base_weight[i] * base_boost * (1 + prestige * factor * i * tier_scaling)

    Difficulty coefficients from config.yml:
    - tier_scaling: multiplier for prestige effect per tier (higher = more boost to rare)
    - base_rarity_boost: flat multiplier to all rare weights (i > 0)
    - rarity_factor: base prestige factor

    ADVENTURE mode (default): tier_scaling=1.0, base_boost=1.0, factor=0.1
    LEGENDARY mode: tier_scaling=2.0, base_boost=10.0, factor=0.15
    """
    # Get difficulty settings (default to adventure)
    difficulty_name = getattr(constants.game, 'difficulty_name', 'ADVENTURE').lower()
    difficulty_config = getattr(constants, 'difficulty', None)

    if difficulty_config and hasattr(difficulty_config, difficulty_name):
        diff = getattr(difficulty_config, difficulty_name)
        tier_scaling = float(getattr(diff, 'tier_scaling', 1.0))
        base_rarity_boost = float(getattr(diff, 'base_rarity_boost', 1.0))
        rarity_factor = float(getattr(diff, 'rarity_factor', 0.1))
    else:
        # Fallback defaults
        tier_scaling = 1.0
        base_rarity_boost = 1.0
        rarity_factor = float(getattr(constants.prestige, 'rarity_factor', 0.1))

    # Apply tier-scaled multiplier: rarer tiers get bigger boost from prestige
    new = []
    for i, w in enumerate(base_weights):
        # Base boost only applies to non-common (i > 0)
        base_boost = base_rarity_boost if i > 0 else 1.0
        tier_multiplier = 1.0 + float(prestige) * rarity_factor * i * tier_scaling
        new.append(float(w) * base_boost * tier_multiplier)

    # Normalize to percentages
    total = sum(new)
    if total <= 0.0:
        n = len(base_weights)
        return [100.0 / n] * n

    return [w * 100.0 / total for w in new]


RARITIES = ('common', 'uncommon', 'rare', 'epic', 'legendary', 'mythical')


def roll_drop_rarity(source, tier=1):
    """Rarity of the egg an enemy drops.

    Base weights per source (``cards.rarity_weights``: mini_bat, bat, boss),
    shifted towards rarer eggs by the bat's tier (``cards.tier_shift``) and by
    prestige (``cards.prestige_scale`` × the difficulty's prestige rules, see
    adjust_rarity_weights).
    """
    from src.engine.progression import compute_prestige

    cards_cfg = getattr(constants, 'cards', None)
    table = getattr(cards_cfg, 'rarity_weights', None)
    table = table if isinstance(table, dict) else vars(table) if table is not None else {}
    weights = [float(w) for w in table.get(source, [1, 0, 0, 0, 0, 0])]
    weights += [0.0] * (len(RARITIES) - len(weights))
    shift = float(getattr(cards_cfg, 'tier_shift', 0.0)) * max(0, tier - 1)
    if shift:
        weights = [w * (1 + shift * i) for i, w in enumerate(weights)]
    prestige = compute_prestige() * float(getattr(cards_cfg, 'prestige_scale', 1.0))
    rarity = random.choices(RARITIES, weights=adjust_rarity_weights(weights, prestige))[0]
    if rarity == 'mythical':
        # Mythical cards are birds only: without a free slot for one, the egg is legendary
        from src.engine import cards

        if not cards._bird_candidates('mythical'):
            rarity = 'legendary'
    return rarity


def choose_loot_type(rarity):
    """What an enemy drops: always a rarity egg, opened by picking it up (see src/engine/cards.py)."""
    return 'egg'
