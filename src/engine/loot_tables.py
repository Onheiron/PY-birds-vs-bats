"""Loot tables: rarity weights and drop selection."""

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


def choose_loot_type(rarity):
    """What an enemy drops: always a rarity egg, opened by picking it up (see src/engine/cards.py)."""
    return 'egg'
