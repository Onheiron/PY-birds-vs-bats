"""Configuration files, schema validation and difficulty presets."""

import subprocess
import sys

import pytest

from src.core import config, constants
from tests.conftest import ROOT

SHIPPED_CONFIGS = [
    'config.yml',
    'config.sample.yml',
    'config_easy.yml',
    'config_hard.yml',
    'config_hell.yml',
    'hardmode.yml',
]


@pytest.fixture
def normal_difficulty():
    yield
    constants.reload_for_difficulty(1)


@pytest.mark.parametrize('name', SHIPPED_CONFIGS)
def test_shipped_config_loads_and_validates(name):
    loaded = config.load_config(name)
    # Partial files are merged over the defaults, so every section is present
    assert {'layout', 'birds', 'timing', 'bat_enemy', 'obstacle', 'speed', 'levels', 'boss'} <= set(loaded)
    assert loaded['layout']['width'] > 0


def test_schema_is_up_to_date():
    result = subprocess.run(
        [sys.executable, str(ROOT / 'tools' / 'gen_config_schema.py'), '--check'], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_deep_merge_overrides_nested_values_without_touching_base():
    base = {'a': {'x': 1, 'y': 2}, 'b': [1, 2]}
    merged = config.deep_merge(base, {'a': {'y': 3}, 'b': [9]})
    assert merged == {'a': {'x': 1, 'y': 3}, 'b': [9]}
    assert base == {'a': {'x': 1, 'y': 2}, 'b': [1, 2]}


@pytest.mark.parametrize(
    'override, expected',
    [
        ({'layuot': {'width': 10}}, 'layuot'),
        ({'layout': {'width': 'wide'}}, 'layout -> width'),
        ({'bat_enemy': {'hp_by_tier': {1: 'lots'}}}, 'hp_by_tier'),
    ],
)
def test_invalid_config_is_rejected_with_location(override, expected):
    broken = config.deep_merge(config.load_config('config.yml'), override)
    with pytest.raises(config.ConfigError, match=expected):
        config.validate(broken)


def test_custom_config_is_merged_over_defaults(tmp_path):
    custom = tmp_path / 'mine.yml'
    custom.write_text('bat_enemy:\n  max_on_screen: 1\n', encoding='utf-8')
    loaded = config.load_config(str(custom))
    assert loaded['bat_enemy']['max_on_screen'] == 1
    assert loaded['bat_enemy']['hp_by_tier'] == config.load_config('config.yml')['bat_enemy']['hp_by_tier']


def test_missing_and_malformed_config_raise(tmp_path):
    with pytest.raises(config.ConfigError, match='not found'):
        config.load_config(str(tmp_path / 'nope.yml'))
    bad = tmp_path / 'bad.yml'
    bad.write_text('layout: [unclosed', encoding='utf-8')
    with pytest.raises(config.ConfigError, match='not valid YAML'):
        config.load_config(str(bad))


def test_unknown_cli_options_are_ignored():
    args = config.parse_args(['--config', 'x.yml', '--co', '-q', 'tests'])
    assert args.config == 'x.yml'
    assert args.theme == 'theme.yml'


def test_namespace_conversion_keeps_numeric_tables_as_dicts():
    from types import SimpleNamespace

    ns = SimpleNamespace()
    config.apply_to_namespace(ns, {'a': {'b': 1}, 'tiers': {1: 10, 2: 20}})
    assert ns.a.b == 1
    assert ns.tiers == {1: 10, 2: 20}


def test_difficulty_presets_apply_and_revert(normal_difficulty):
    layout = constants.layout
    normal_hp = dict(constants.bat_enemy.hp_by_tier)
    assert constants.game.life_recovery_on_spawn is True

    constants.reload_for_difficulty(2)  # HARD = SURVIVAL: no life recovery
    assert constants.game.life_recovery_on_spawn is False
    assert constants.bat_enemy.hp_by_tier == normal_hp

    constants.reload_for_difficulty(3)  # HELL
    assert constants.game.difficulty_name == 'LEGENDARY'
    assert constants.bat_enemy.hp_by_tier[1] > normal_hp[1]

    constants.reload_for_difficulty(0)  # EASY
    assert constants.bat_enemy.hp_by_tier[1] < normal_hp[1]

    constants.reload_for_difficulty(1)
    assert constants.bat_enemy.hp_by_tier == normal_hp
    assert constants.game.life_recovery_on_spawn is True
    # Namespaces are updated in place: references held by other modules stay valid
    assert constants.layout is layout


def test_difficulty_presets_leave_loot_tables_alone(normal_difficulty):
    eggs = constants.eggs.rarity_candidates
    loot_weights = constants.loot.base_rarity_weights
    constants.reload_for_difficulty(3)
    assert constants.eggs.rarity_candidates == eggs
    assert constants.loot.base_rarity_weights == loot_weights
