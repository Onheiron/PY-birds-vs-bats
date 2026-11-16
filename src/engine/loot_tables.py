"""Loot tables: rarity weights and drop selection."""

from src.core import constants
from src.core import state
import random
from src.entities.sprites import GOLD, ORANGE, WHITE


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
    """Choose a loot type based on rarity and game state."""
    # Count empty bird slots
    num_empty = sum(1 for i in range(constants.layout.num_balls) if state.birds.lost[i])

    # Get egg probability
    egg_prob = 0.0
    if num_empty > 0:
        if num_empty in constants.eggs.drop_probs:
            egg_prob = float(constants.eggs.drop_probs[num_empty])
        else:
            int_keys = sorted([k for k in constants.eggs.drop_probs.keys() if isinstance(k, int)])
            if int_keys:
                egg_prob = float(constants.eggs.drop_probs[int_keys[-1]])

    # Loot pools
    loot_pools = {
        'common': ['wide_cursor', 'tailwind', 'timelapse'],
        'uncommon': ['wide_cursor+', 'tailwind+', 'timelapse'],
        'rare': ['wide_cursor++', 'tailwind++', 'timelapse+'],
        'epic': ['wide_cursor_max', 'tailwind_max', 'timelapse++']
    }

    # Decide egg or powerup
    if random.random() < egg_prob:
        return _choose_egg(rarity)
    else:
        pool = loot_pools.get(rarity, loot_pools['common'])
        return random.choice(pool)


def _choose_egg(rarity):
    """Choose an egg type based on rarity."""
    rarity_data = constants.eggs.rarity_candidates.get(rarity, {})
    candidates = list(rarity_data.keys()) if isinstance(rarity_data, dict) else []

    if not candidates:
        defaults = {
            'common': ['yellow_egg', 'red_egg', 'blue_egg'],
            'uncommon': ['blue_egg', 'patchwork_egg', 'purple_egg'],
            'rare': ['white_egg', 'orange_egg', 'gold_egg'],
            'epic': ['dinosaur_egg', 'glitch_egg']
        }
        candidates = defaults.get(rarity, ['yellow_egg'])

    raw_weights = rarity_data if isinstance(rarity_data, dict) else {}
    weights = [float(raw_weights.get(e, 1.0)) for e in candidates]

    # Map egg names to bird colors
    egg_to_color = {
        'white_egg': WHITE,
        'orange_egg': ORANGE,
        'gold_egg': GOLD,
    }

    # Filter by spawn limits (max 1 per rare type)
    def allowed(egg_name):
        target_color = egg_to_color.get(egg_name)
        if target_color is None:
            return True  # Not a rare egg, always allowed
        # Check if this rare bird type already exists
        cnt = sum(1 for i in range(constants.layout.num_balls)
                  if not state.birds.lost[i] and state.birds.colors[i] == target_color)
        return cnt < 1  # Max 1 per rare type

    allowed_candidates = [(e, w) for e, w in zip(candidates, weights) if allowed(e)]

    if allowed_candidates:
        eggs, weights = zip(*allowed_candidates)
        return random.choices(list(eggs), weights=list(weights))[0]

    return 'yellow_egg'
