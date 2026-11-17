"""
Bird type definitions for BVB.
Centralizes all bird-related data: colors, stats, limits, eggs, etc.
"""

# Import theme from src (not src.core to avoid circular imports)
import src.theme as theme

# ============================================================================
# BIRD TYPE ENUM
# ============================================================================


class BirdType:
    """Enum-like class for bird types."""

    YELLOW = 'YELLOW'
    RED = 'RED'
    BLUE = 'BLUE'
    PATCHWORK = 'PATCHWORK'
    PURPLE = 'PURPLE'
    CLOCKWORK = 'CLOCKWORK'
    WHITE = 'WHITE'
    ORANGE = 'ORANGE'
    GOLD = 'GOLD'
    COOKIE = 'COOKIE'
    STEALTH = 'STEALTH'
    DINOSAUR = 'DINOSAUR'
    GLITCH = 'GLITCH'
    # New birds
    RAINBOW = 'RAINBOW'
    TWISTER = 'TWISTER'
    FROSTY = 'FROSTY'
    POISON = 'POISON'
    BERSERK = 'BERSERK'
    ROCK = 'ROCK'


# ============================================================================
# BIRD TYPE CONFIGURATIONS
# ============================================================================

BIRD_TYPES = {
    BirdType.YELLOW: {
        'name': 'Yellow',
        'display_name': 'Yellow',
        'color': theme.get_color('birds', 'yellow', 220),
        'speed': 2,
        'damage': 2,
        'description': 'Standard bird, bounces adjacent yellow birds',
        'egg_type': 'yellow_egg',
    },
    BirdType.RED: {
        'name': 'Red',
        'display_name': 'Red',
        'color': theme.get_color('birds', 'red', -1),
        'speed': 3,
        'damage': 3,
        'description': 'Shoots projectiles, damage scales with adjacent reds',
        'egg_type': 'red_egg',
    },
    BirdType.BLUE: {
        'name': 'Blue',
        'display_name': 'Blue',
        'color': theme.get_color('birds', 'blue', -3),
        'speed': 4,
        'damage': 4,
        'description': 'Speed boost ability, cures adjacent scared birds',
        'egg_type': 'blue_egg',
    },
    BirdType.PATCHWORK: {
        'name': 'Patchwork',
        'display_name': 'Patchwork',
        'color': theme.get_color('birds', 'patchwork', 202),
        'speed': 3,
        'damage': 3,
        'description': 'Can transform and use multiple bird abilities',
        'egg_type': 'patchwork_egg',
    },
    BirdType.PURPLE: {
        'name': 'Purple',
        'display_name': 'Purple',
        'color': theme.get_color('birds', 'purple', 201),
        'speed': 3,
        'damage': 3,
        'description': 'Charges powerful shots, damage increases with charge time',
        'egg_type': 'purple_egg',
    },
    BirdType.CLOCKWORK: {
        'name': 'Clockwork',
        'display_name': 'Clockwork',
        'color': theme.get_color('birds', 'clockwork', 244),
        'speed': 2,
        'damage': 2,
        'description': 'Auto-bounces at floor, has charge system that decays',
        'egg_type': 'clockwork_egg',
    },
    BirdType.WHITE: {
        'name': 'White',
        'display_name': 'Templar',
        'color': theme.get_color('birds', 'white', -5),
        'speed': 4,
        'damage': 4,
        'description': 'Activates abilities of adjacent birds',
        'egg_type': 'white_egg',
    },
    BirdType.ORANGE: {
        'name': 'Orange',
        'display_name': 'Phoenix',
        'color': theme.get_color('birds', 'orange', 208),
        'speed': 5,
        'damage': 5,
        'description': 'One-hit kills enemies, goes out of play after',
        'egg_type': 'orange_egg',
    },
    BirdType.GOLD: {
        'name': 'Gold',
        'display_name': 'Gold',
        'color': theme.get_color('birds', 'gold', 228),
        'speed': 5,
        'damage': 1,
        'description': 'Generates massive score per frame',
        'egg_type': 'gold_egg',
    },
    BirdType.COOKIE: {
        'name': 'Cookie',
        'display_name': 'Cookie',
        'color': theme.get_color('birds', 'cookie', 180),
        'speed': 3,
        'damage': 3,
        'description': 'Drops XP crumbs, dies after 5 crumbs',
        'egg_type': 'cookie_egg',
    },
    BirdType.STEALTH: {
        'name': 'Stealth',
        'display_name': 'Stealth',
        'color': 'STEALTH',  # Special rendering
        'speed': 3,
        'damage': 24,
        'description': 'Can phase through enemies dealing massive damage',
        'egg_type': 'stealth_egg',
    },
    BirdType.DINOSAUR: {
        'name': 'Dinosaur',
        'display_name': 'Dinosaur',
        'color': theme.get_color('birds', 'dinosaur', 46),
        'speed': 4,
        'damage': 16,
        'description': 'Requires multiple presses to bounce, high damage',
        'egg_type': 'dinosaur_egg',
    },
    BirdType.GLITCH: {
        'name': 'Glitch',
        'display_name': 'Glitch',
        'color': theme.get_color('birds', 'glitch', 205),
        'speed': 3,  # Varies randomly
        'damage': 16,  # Varies randomly
        'description': 'Unpredictable: random speed, damage, can swap lanes, duplicate',
        'egg_type': 'glitch_egg',
    },
    # New birds
    BirdType.RAINBOW: {
        'name': 'Rainbow',
        'display_name': 'Rainbow',
        'color': 'RAINBOW',  # Special sentinel for animated multicolor
        'speed': 6,  # Decreases with charge
        'damage': 3,
        'description': 'Warps between ceiling/floor, colors fade over time, recharge with UP',
        'egg_type': 'rainbow_egg',
    },
    BirdType.TWISTER: {
        'name': 'Twister',
        'display_name': 'Twister',
        'color': 'TWISTER',  # Special sentinel for gray body + cyan wings
        'speed': 4,
        'damage': 5,
        'description': 'Creates tailwind in current lane and 2 adjacent lanes',
        'egg_type': 'twister_egg',
    },
    BirdType.FROSTY: {
        'name': 'Frosty',
        'display_name': 'Frosty',
        'color': theme.get_color('birds', 'frosty', 159),
        'speed': 3,
        'damage': 3,
        'description': '30% chance to freeze enemies on hit, power boosts to 60%',
        'egg_type': 'frosty_egg',
    },
    BirdType.POISON: {
        'name': 'Poison',
        'display_name': 'Poison',
        'color': theme.get_color('birds', 'poison', 118),
        'speed': 3,
        'damage': 3,
        'description': '30% chance to poison bats (2HP/s), power boosts to 60%',
        'egg_type': 'poison_egg',
    },
    BirdType.BERSERK: {
        'name': 'Berserk',
        'display_name': 'Berserk',
        'color': theme.get_color('birds', 'berserk', 124),
        'speed': 3,
        'damage': 4,
        'description': '30% chance to cause bleeding (1HP/s, -1 armor), power boosts to 60%',
        'egg_type': 'berserk_egg',
    },
    BirdType.ROCK: {
        'name': 'Rock',
        'display_name': 'Rock',
        'color': theme.get_color('birds', 'rock', 94),
        'speed': 2,
        'damage': 3,
        'description': 'Pushes enemies up 1 row on hit, power boosts to 2 rows + speed 3',
        'egg_type': 'rock_egg',
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

_TYPE_BY_COLOR = {}
for _bird_type, _data in BIRD_TYPES.items():
    _TYPE_BY_COLOR.setdefault(_data['color'], _bird_type)


def get_bird_type_by_color(ansi_color: str):
    """Get bird type (e.g. 'YELLOW') from the colour stored in state.birds.colors."""
    return _TYPE_BY_COLOR.get(ansi_color)


def get_color_for_bird_type(bird_type: str, dynamic: bool = True) -> str:
    """Get ANSI color code for a bird type.

    Args:
        bird_type: The bird type string (e.g., 'YELLOW', 'RED')
        dynamic: If True, reads from current theme (respects accessibility mode).
                 If False, returns the cached color from import time.

    Returns:
        ANSI escape sequence string for the color
    """
    # Special sentinel types - return string, not ANSI code
    if bird_type == BirdType.STEALTH:
        return "STEALTH"
    if bird_type == BirdType.RAINBOW:
        return "RAINBOW"
    if bird_type == BirdType.TWISTER:
        return "TWISTER"

    if dynamic:
        # Map bird type to theme color name
        color_names = {
            BirdType.YELLOW: 'yellow',
            BirdType.RED: 'red',
            BirdType.BLUE: 'blue',
            BirdType.WHITE: 'white',
            BirdType.PATCHWORK: 'patchwork',
            BirdType.PURPLE: 'purple',
            BirdType.CLOCKWORK: 'clockwork',
            BirdType.ORANGE: 'orange',
            BirdType.GOLD: 'gold',
            BirdType.COOKIE: 'cookie',
            BirdType.DINOSAUR: 'dinosaur',
            BirdType.GLITCH: 'glitch',
            BirdType.FROSTY: 'frosty',
            BirdType.POISON: 'poison',
            BirdType.BERSERK: 'berserk',
            BirdType.ROCK: 'rock',
        }
        color_name = color_names.get(bird_type)
        if color_name:
            return theme.get_color('birds', color_name, -5)

    # Fallback to cached color
    return BIRD_TYPES.get(bird_type, {}).get('color', "\033[0m")


def get_bird_type_from_egg(egg_type: str):
    """Get bird type from egg type."""
    for bird_type, data in BIRD_TYPES.items():
        if data['egg_type'] == egg_type:
            return bird_type
    return None


def get_default_speed(bird_type: str) -> float:
    """Starting speed of a bird type, in movement points (its ``speed`` stat / 10)."""
    from src.engine import stats

    return stats.speed_points(bird_type)


# ============================================================================
# FORMATION HELPERS
# ============================================================================
