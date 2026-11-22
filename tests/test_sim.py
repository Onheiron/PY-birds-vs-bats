"""The simulation bot and the run tooling."""

import importlib.util

import pytest

from src.engine import events
from src.sim.bot import PROFILES, profile
from src.sim.runner import RunConfig, run, run_many
from tests.conftest import ROOT


def load_cli():
    spec = importlib.util.spec_from_file_location('simulate', ROOT / 'tools' / 'simulate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runs_are_reproducible():
    config = RunConfig(seed=3, skill=PROFILES['expert'], max_minutes=1.5)
    assert run(config).summary() == run(config).summary()


def test_perfect_bot_keeps_the_flock_alive_early_on():
    summary = run(RunConfig(seed=5, skill=PROFILES['perfect'], max_minutes=3)).summary()
    assert summary['end'] == 'time limit'
    assert summary.get('birds_lost', {}).get('floor', 0) == 0
    assert summary['gear_max'] >= 5, 'a high flock should build momentum'


@pytest.mark.parametrize('name', ['perfect', 'expert', 'novice'])
def test_bot_respects_its_key_rate(name):
    skill = PROFILES[name]
    summary = run(RunConfig(seed=2, skill=skill, max_minutes=1)).summary()
    hands = 2 if skill.two_hands else 1  # moves and UP each at the key rate
    assert 0 < summary['keys_per_second'] <= hands * 60 / skill.key_interval + 0.01


def test_better_players_last_longer():
    def minutes(skill):
        runs = run_many([RunConfig(seed=s, skill=skill, max_minutes=6) for s in (1, 2)])
        return sum(r['minutes'] for r in runs)

    assert minutes(PROFILES['perfect']) > minutes(PROFILES['novice'])


def test_overrides_reach_the_game():
    fast = run(RunConfig(seed=1, skill=PROFILES['perfect'], max_minutes=2, overrides={'speed': {'mph_per_level': 120}}))
    slow = run(RunConfig(seed=1, skill=PROFILES['perfect'], max_minutes=2))
    assert fast.summary()['miles'] > slow.summary()['miles']


def test_run_leaves_no_event_listeners_behind():
    before = {name: list(handlers) for name, handlers in events._handlers.items()}
    run(RunConfig(seed=1, max_minutes=0.2))
    after = {name: list(handlers) for name, handlers in events._handlers.items() if handlers}
    assert after == {name: handlers for name, handlers in before.items() if handlers}


def test_skill_profiles_can_be_adjusted():
    assert profile('expert', key_interval=2).key_interval == 2
    assert profile('expert', key_interval=2).reaction_frames == PROFILES['expert'].reaction_frames


def test_cli_parses_overrides():
    from src.sim.options import parse_assignments

    parsed = parse_assignments('bat_enemy.max_bats_by_level.level_4_6=2; speed.mph_per_level=60; birds.x=[1, 2]')
    assert parsed == {
        'bat_enemy': {'max_bats_by_level': {'level_4_6': 2}},
        'speed': {'mph_per_level': 60},
        'birds': {'x': [1, 2]},
    }


def test_cli_end_to_end(tmp_path, capsys):
    cli = load_cli()
    out = tmp_path / 'runs.json'
    cli.main(
        [
            '--runs',
            '2',
            '--jobs',
            '1',
            '--max-minutes',
            '0.5',
            '--variant',
            'a:',
            '--variant',
            'b: speed.mph_per_level=80',
            '--json',
            str(out),
        ]
    )
    text = capsys.readouterr().out
    assert 'level reached, median' in text and 'Birds lost per game' in text
    assert out.exists()
