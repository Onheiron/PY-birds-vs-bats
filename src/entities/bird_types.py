#!/usr/bin/env python3
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
        'ability': 'chain_bounce',
        'description': 'Standard bird, bounces adjacent yellow birds',
        'rarity': 'common',
        'spawn_limit': None,  # Unlimited
        'egg_type': 'yellow_egg',
    },

    BirdType.RED: {
        'name': 'Red',
        'display_name': 'Red',
        'color': theme.get_color('birds', 'red', -1),
        'speed': 3,
        'damage': 3,
        'ability': 'projectile',
        'description': 'Shoots projectiles, damage scales with adjacent reds',
        'rarity': 'common',
        'spawn_limit': None,
        'egg_type': 'red_egg',
    },

    BirdType.BLUE: {
        'name': 'Blue',
        'display_name': 'Blue',
        'color': theme.get_color('birds', 'blue', -3),
        'speed': 4,
        'damage': 4,
        'ability': 'speed_boost',
        'description': 'Speed boost ability, cures adjacent scared birds',
        'rarity': 'common',
        'spawn_limit': None,
        'egg_type': 'blue_egg',
    },

    BirdType.PATCHWORK: {
        'name': 'Patchwork',
        'display_name': 'Patchwork',
        'color': theme.get_color('birds', 'patchwork', 202),
        'speed': 3,
        'damage': 3,
        'ability': 'multicolor',
        'description': 'Can transform and use multiple bird abilities',
        'rarity': 'uncommon',
        'spawn_limit': 2,
        'egg_type': 'patchwork_egg',
    },

    BirdType.PURPLE: {
        'name': 'Purple',
        'display_name': 'Purple',
        'color': theme.get_color('birds', 'purple', 201),
        'speed': 3,
        'damage': 3,
        'ability': 'charged_shot',
        'description': 'Charges powerful shots, damage increases with charge time',
        'rarity': 'uncommon',
        'spawn_limit': 2,
        'egg_type': 'purple_egg',
    },

    BirdType.CLOCKWORK: {
        'name': 'Clockwork',
        'display_name': 'Clockwork',
        'color': theme.get_color('birds', 'clockwork', 244),
        'speed': 2,
        'damage': 2,
        'ability': 'auto_bounce',
        'description': 'Auto-bounces at floor, has charge system that decays',
        'rarity': 'uncommon',
        'spawn_limit': 2,
        'egg_type': 'clockwork_egg',
    },

    BirdType.WHITE: {
        'name': 'White',
        'display_name': 'Templar',
        'color': theme.get_color('birds', 'white', -5),
        'speed': 4,
        'damage': 4,
        'ability': 'battle_cry',
        'description': 'Activates abilities of adjacent birds',
        'rarity': 'rare',
        'spawn_limit': 1,
        'egg_type': 'white_egg',
    },

    BirdType.ORANGE: {
        'name': 'Orange',
        'display_name': 'Phoenix',
        'color': theme.get_color('birds', 'orange', 208),
        'speed': 5,
        'damage': 5,
        'ability': 'one_hit_kill',
        'description': 'One-hit kills enemies, goes out of play after',
        'rarity': 'rare',
        'spawn_limit': 1,
        'egg_type': 'orange_egg',
    },

    BirdType.GOLD: {
        'name': 'Gold',
        'display_name': 'Gold',
        'color': theme.get_color('birds', 'gold', 228),
        'speed': 5,
        'damage': 1,
        'ability': 'score_multiplier',
        'description': 'Generates massive score per frame',
        'rarity': 'rare',
        'spawn_limit': 1,
        'egg_type': 'gold_egg',
    },

    BirdType.COOKIE: {
        'name': 'Cookie',
        'display_name': 'Cookie',
        'color': theme.get_color('birds', 'cookie', 180),
        'speed': 3,
        'damage': 3,
        'ability': 'xp_crumb',
        'description': 'Drops XP crumbs, dies after 5 crumbs',
        'rarity': 'uncommon',
        'spawn_limit': 1,
        'egg_type': 'cookie_egg',
    },

    BirdType.STEALTH: {
        'name': 'Stealth',
        'display_name': 'Stealth',
        'color': 'STEALTH',  # Special rendering
        'speed': 3,
        'damage': 24,
        'ability': 'phase_through',
        'description': 'Can phase through enemies dealing massive damage',
        'rarity': 'uncommon',
        'spawn_limit': 1,
        'egg_type': 'stealth_egg',
    },

    BirdType.DINOSAUR: {
        'name': 'Dinosaur',
        'display_name': 'Dinosaur',
        'color': theme.get_color('birds', 'dinosaur', 46),
        'speed': 4,
        'damage': 16,
        'ability': 'charge_bounce',
        'description': 'Requires multiple presses to bounce, high damage',
        'rarity': 'epic',
        'spawn_limit': 1,
        'egg_type': 'dinosaur_egg',
    },

    BirdType.GLITCH: {
        'name': 'Glitch',
        'display_name': 'Glitch',
        'color': theme.get_color('birds', 'glitch', 205),
        'speed': 3,  # Varies randomly
        'damage': 16,  # Varies randomly
        'ability': 'chaos',
        'description': 'Unpredictable: random speed, damage, can swap lanes, duplicate',
        'rarity': 'epic',
        'spawn_limit': 1,
        'egg_type': 'glitch_egg',
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_bird_type_by_color(ansi_color: str):
    """Get bird type enum from ANSI color code."""
    for bird_type, data in BIRD_TYPES.items():
        if data['color'] == ansi_color:
            return bird_type
    return None


def get_color_for_bird_type(bird_type: str, dynamic: bool = True) -> str:
    """Get ANSI color code for a bird type.

    Args:
        bird_type: The bird type string (e.g., 'YELLOW', 'RED')
        dynamic: If True, reads from current theme (respects accessibility mode).
                 If False, returns the cached color from import time.

    Returns:
        ANSI escape sequence string for the color
    """
    # STEALTH is special - return sentinel string, not ANSI code
    if bird_type == BirdType.STEALTH:
        return "STEALTH"

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
        }
        color_name = color_names.get(bird_type)
        if color_name:
            return theme.get_color('birds', color_name, -5)

    # Fallback to cached color
    return BIRD_TYPES.get(bird_type, {}).get('color', "\033[0m")


def get_display_name(bird_type: str) -> str:
    """Get display name for a bird type."""
    return BIRD_TYPES.get(bird_type, {}).get('display_name', 'Unknown')


def get_egg_type(bird_type: str) -> str:
    """Get egg type for a bird type."""
    return BIRD_TYPES.get(bird_type, {}).get('egg_type', '')


def get_bird_type_from_egg(egg_type: str):
    """Get bird type from egg type."""
    for bird_type, data in BIRD_TYPES.items():
        if data['egg_type'] == egg_type:
            return bird_type
    return None


def get_spawn_limit(bird_type: str) -> int:
    """Get spawn limit for a bird type (None = unlimited)."""
    return BIRD_TYPES.get(bird_type, {}).get('spawn_limit')


def get_default_speed(bird_type: str) -> int:
    """Get default speed for a bird type."""
    return BIRD_TYPES.get(bird_type, {}).get('speed', 2)


# ============================================================================
# FORMATION HELPERS
# ============================================================================

DEFAULT_FORMATION = [
    BirdType.YELLOW,
    BirdType.YELLOW,
    BirdType.YELLOW,
    BirdType.YELLOW,
    BirdType.RED,
    BirdType.RED,
    BirdType.RED,
    BirdType.BLUE,
    BirdType.BLUE,
]
