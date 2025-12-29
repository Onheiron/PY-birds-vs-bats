#!/usr/bin/env python3
"""
Global game constants loaded from configuration.
All values are loaded from config.yml (or specified --config file).
"""
from . import init
from types import SimpleNamespace

# Load configuration (required - will exit if not found)
config, args = init.init_config()

# Import necessary functions for transform limits
from src.entities.bird_types import BirdType, get_color_for_bird_type

# Create all namespace objects from config
layout = init.dict_to_namespace(config.get('layout', {}))
birds = init.dict_to_namespace(config.get('birds', {}))
timing = init.dict_to_namespace(config.get('timing', {}))
limits = init.dict_to_namespace(config.get('limits', {}))
physics = init.dict_to_namespace(config.get('physics', {}))
eggs = init.dict_to_namespace(config.get('eggs', {}))
bat_enemy = init.dict_to_namespace(config.get('bat_enemy', {}))
obstacle = init.dict_to_namespace(config.get('obstacle', {}))
powers = init.dict_to_namespace(config.get('powers', {}))
wide_cursor = init.dict_to_namespace(config.get('wide_cursor', {}))
bounce_boost = init.dict_to_namespace(config.get('bounce_boost', {}))
suction = init.dict_to_namespace(config.get('suction', {}))
tailwind = init.dict_to_namespace(config.get('tailwind', {}))
dinosaur = init.dict_to_namespace(config.get('dinosaur', {}))
stealth = init.dict_to_namespace(config.get('stealth', {}))
gold = init.dict_to_namespace(config.get('gold', {}))
clockwork = init.dict_to_namespace(config.get('clockwork', {}))
glitch = init.dict_to_namespace(config.get('glitch', {}))
orange = init.dict_to_namespace(config.get('orange', {}))
shuffle = init.dict_to_namespace(config.get('shuffle', {}))
progression = init.dict_to_namespace(config.get('progression', {}))
combo = init.dict_to_namespace(config.get('combo', {}))
combat = init.dict_to_namespace(config.get('combat', {}))
collision = init.dict_to_namespace(config.get('collision', {}))
rendering = init.dict_to_namespace(config.get('rendering', {}))
despawn = init.dict_to_namespace(config.get('despawn', {}))
game_over = init.dict_to_namespace(config.get('game_over', {}))
controls = init.dict_to_namespace(config.get('controls', {}))
game = init.dict_to_namespace(config.get('game', {}))
synergy = init.dict_to_namespace(config.get('synergy', {}))
prestige = init.dict_to_namespace(config.get('prestige', {}))
bat = init.dict_to_namespace(config.get('bat', {}))
colors = init.dict_to_namespace(config.get('colors', {}))
speed = init.dict_to_namespace(config.get('speed', {}))
levels = init.dict_to_namespace(config.get('levels', {}))

# Special handling for transform limits (uses color codes as keys)
# This is built from config if 'transform' section exists, otherwise use reasonable defaults
if 'transform' in config and 'limits' in config['transform']:
    # Load limits from config (assuming they use bird type names as keys)
    transform_config = config['transform']['limits']
    transform = SimpleNamespace(
        limits={
            get_color_for_bird_type(getattr(BirdType, bird_type)): limit
            for bird_type, limit in transform_config.items()
            if hasattr(BirdType, bird_type)
        }
    )
else:
    # Fallback to reasonable defaults
    transform = SimpleNamespace(
        limits={
            get_color_for_bird_type(BirdType.YELLOW): 5,
            get_color_for_bird_type(BirdType.RED): 3,
            get_color_for_bird_type(BirdType.BLUE): 2,
        }
    )

# Convert colors tuples if they come as lists from YAML
if hasattr(colors, 'bats_base_rgb') and isinstance(colors.bats_base_rgb, list):
    colors.bats_base_rgb = tuple(colors.bats_base_rgb)
if hasattr(colors, 'obstacles_base_rgb') and isinstance(colors.obstacles_base_rgb, list):
    colors.obstacles_base_rgb = tuple(colors.obstacles_base_rgb)

# Fix: Keep dicts that are used with .get() method as dicts, not SimpleNamespace
# These need to remain as dicts because the code uses .get() on them
dict_attributes = [
    (prestige, 'modifiers'),
    (bat_enemy, 'loot_base_weights'),
    (bat_enemy, 'hp_by_tier'),
    (obstacle, 'max_hp_by_tier'),
    (eggs, 'drop_probs'),
    (eggs, 'rarity_candidates'),
    (eggs, 'rarity_weights'),
    (powers, 'default'),
]

for obj, attr_name in dict_attributes:
    if hasattr(obj, attr_name):
        attr = getattr(obj, attr_name)
        if isinstance(attr, SimpleNamespace):
            # Convert SimpleNamespace back to dict
            setattr(obj, attr_name, {k: v for k, v in vars(attr).items() if not k.startswith('_')})
        elif isinstance(attr, dict):
            # If it's already a dict, check for nested SimpleNamespace objects
            for key, value in attr.items():
                if isinstance(value, SimpleNamespace):
                    attr[key] = {k: v for k, v in vars(value).items() if not k.startswith('_')}
