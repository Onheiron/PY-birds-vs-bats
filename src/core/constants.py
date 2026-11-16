"""Game constants, loaded from the configuration.

Each top-level section of the config becomes a namespace of this module:
``constants.layout.width``, ``constants.bat_enemy.hp_by_tier`` and so on.
Namespaces are updated in place when the difficulty changes, so modules may
keep references to them.
"""

from types import SimpleNamespace

from src.core import config as config_loader
from src.core import paths

# Load configuration (exits with a message if it cannot be used).
# This must happen before bird_types is imported: it selects the theme file.
config, args = config_loader.init_config()

from src.entities.bird_types import BirdType, get_color_for_bird_type  # noqa: E402

SECTIONS = (
    'layout',
    'birds',
    'timing',
    'notifications',
    'limits',
    'physics',
    'eggs',
    'bat_enemy',
    'obstacle',
    'powers',
    'wide_cursor',
    'bounce_boost',
    'suction',
    'tailwind',
    'dinosaur',
    'stealth',
    'gold',
    'clockwork',
    'glitch',
    'rainbow',
    'twister',
    'frosty',
    'poison',
    'berserk',
    'rock',
    'orange',
    'shuffle',
    'timelapse',
    'progression',
    'combo',
    'combat',
    'loot',
    'collision',
    'rendering',
    'despawn',
    'game_over',
    'controls',
    'game',
    'synergy',
    'prestige',
    'bat',
    'colors',
    'speed',
    'score',
    'levels',
    'background',
    'boss',
    'wind_boss',
    'jelly_boss',
    'tree_boss',
    'owl_boss',
    'difficulty',
)

# Sections that have defaults when the config omits them
_SECTION_DEFAULTS = {
    'background': {'enabled': True, 'parallax': True},
}

# Tables looked up with .get(): they must stay dicts even if their keys are strings
_DICT_ATTRIBUTES = (
    ('prestige', 'modifiers'),
    ('bat_enemy', 'loot_base_weights'),
    ('bat_enemy', 'hp_by_tier'),
    ('obstacle', 'max_hp_by_tier'),
    ('eggs', 'drop_probs'),
    ('eggs', 'rarity_candidates'),
    ('eggs', 'rarity_weights'),
    ('powers', 'default'),
)

# Difficulty index (0=EASY, 1=NORMAL, 2=HARD, 3=HELL) -> override file.
# NORMAL is the base configuration itself.
DIFFICULTY_CONFIG_FILES = {
    0: 'config_easy.yml',
    2: 'config_hard.yml',
    3: 'config_hell.yml',
}

# Sections a difficulty preset may override. The presets also carry "eggs" and
# "loot" tables written for the old four-rarity loot system: those were never
# applied and would not fit the current six-rarity tables, so they stay ignored.
DIFFICULTY_SECTIONS = ('game', 'bat_enemy', 'obstacle', 'progression', 'speed', 'score')

# Fallback transform limits when the config has no transform.limits table
_DEFAULT_TRANSFORM_LIMITS = {BirdType.YELLOW: 5, BirdType.RED: 3, BirdType.BLUE: 2}

# Colour limits are keyed by bird colour code, not by config key
transform = SimpleNamespace(limits={})

for _name in SECTIONS:
    globals()[_name] = SimpleNamespace()


def _namespace_to_dict(value):
    """Plain-dict view of a namespace (or of namespaces nested one level in a dict)."""
    if isinstance(value, SimpleNamespace):
        return dict(vars(value))
    if isinstance(value, dict):
        return {k: dict(vars(v)) if isinstance(v, SimpleNamespace) else v for k, v in value.items()}
    return value


def _apply(merged):
    """Populate every namespace from a full configuration mapping."""
    module = globals()
    for name in SECTIONS:
        config_loader.reset_namespace(module[name], merged.get(name, _SECTION_DEFAULTS.get(name, {})))

    for section, attr in _DICT_ATTRIBUTES:
        namespace = module[section]
        if hasattr(namespace, attr):
            setattr(namespace, attr, _namespace_to_dict(getattr(namespace, attr)))

    # YAML has no tuples: colours arrive as lists
    colors = module['colors']
    for attr in ('bats_base_rgb', 'obstacles_base_rgb'):
        if isinstance(getattr(colors, attr, None), list):
            setattr(colors, attr, tuple(getattr(colors, attr)))

    limits = merged.get('transform', {}).get('limits') or _DEFAULT_TRANSFORM_LIMITS
    transform.limits = {
        get_color_for_bird_type(getattr(BirdType, bird_type)): limit
        for bird_type, limit in limits.items()
        if hasattr(BirdType, bird_type)
    }


def reload_for_difficulty(difficulty_index):
    """Re-apply the configuration with the overrides of a difficulty preset.

    Args:
        difficulty_index: 0=EASY, 1=NORMAL, 2=HARD, 3=HELL
    """
    merged = config
    override_file = DIFFICULTY_CONFIG_FILES.get(difficulty_index)
    if override_file:
        path = paths.find(override_file)
        if path:
            overrides = config_loader.load_yaml(path)
            merged = config_loader.deep_merge(config, {k: v for k, v in overrides.items() if k in DIFFICULTY_SECTIONS})
    _apply(merged)


_apply(config)
