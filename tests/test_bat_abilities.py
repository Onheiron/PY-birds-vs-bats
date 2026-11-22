"""Special bats: healer, bomber, plague, necromancer."""

from src.core import state as game_state
from src.engine import clock, enemy_stats
from src.engine.logic import bat_abilities
from tests.harness import Simulation


def bat(kind, tier=3, x=20, **extra):
    b = enemy_stats.make_bat(tier, kind, x, 6, 6, 1000, **extra)
    b['ability_ready'] = 0
    return b


def always(monkeypatch):
    monkeypatch.setattr(bat_abilities, '_per_tick', lambda chance: 1.0 if chance > 0 else 0.0)


def test_a_healer_heals_the_bats_around_it(monkeypatch):
    with Simulation(seed=1, key_rate=0) as sim:
        always(monkeypatch)
        healer, near, far = bat('healer'), bat(None, x=26), bat(None, x=60)
        near['hp'] = far['hp'] = 100
        sim.state.enemies.bats[:] = [healer, near, far]
        bat_abilities.healer(healer)
        assert near['hp'] == 100 + int(near['max_hp'] * 0.10)
        assert far['hp'] == 100
        assert healer['ability_ready'] > clock.now()


def test_a_bomber_drops_fast_stones(monkeypatch):
    with Simulation(seed=1, key_rate=0) as sim:
        always(monkeypatch)
        bomber = bat('bomber')
        sim.state.enemies.obstacles[:] = []
        bat_abilities.bomber(bomber)
        stone = sim.state.enemies.obstacles[-1]
        assert stone['kind'] == 'stone' and stone['hp'] == 30
        assert enemy_stats.get(stone, 'fall_interval') == 2
        assert enemy_stats.get(stone, 'stun') == 0.5


def test_the_plague_needs_three_presses_and_spreads_to_neighbours(monkeypatch):
    with Simulation(seed=1, key_rate=0):
        birds = game_state.birds
        for i in range(len(birds.colors)):
            birds.random_lanes[i] = i
            birds.lost[i] = False
        plague = bat('plague')
        assert bat_abilities.infect(4, plague)
        info = game_state.special.poisoned_birds[4]
        assert info['cure_attempts_needed'] == 3
        assert info['death_time'] - clock.now() == 15.0
        monkeypatch.setattr(bat_abilities, '_per_tick', lambda chance: 1.0)
        bat_abilities.spread_plague()
        infected = set(game_state.special.poisoned_birds)
        assert len(infected) == 2 and infected - {4} <= {3, 5}


def test_a_necromancer_raises_zombies_in_empty_lanes_and_they_die_with_it(monkeypatch):
    with Simulation(seed=1, key_rate=0) as sim:
        always(monkeypatch)
        birds = game_state.birds
        for i in range(len(birds.colors)):
            birds.random_lanes[i] = i
            birds.lost[i] = i in (2, 6)
        necro = bat('necromancer')
        sim.state.enemies.bats[:] = [necro]
        for _ in range(5):
            necro['ability_ready'] = 0
            bat_abilities.necromancer(necro)
        assert sorted(z['lane'] for z in sim.state.enemies.zombies) == [2, 6]  # 2 at most, in empty lanes
        sim.state.enemies.bats[:] = []
        bat_abilities.update_zombies()
        assert not sim.state.enemies.zombies


def test_an_elite_necromancer_keeps_three_zombies():
    with Simulation(seed=1, key_rate=0):
        elite = enemy_stats.make_bat(3, 'necromancer', 20, 6, 6, 1000, affixes=['swift'])
        assert enemy_stats.get(elite, 'zombies') == 3


def test_zombies_scare_a_falling_bird_they_pass():
    with Simulation(seed=1, key_rate=0) as sim:
        birds = game_state.birds
        for i in range(len(birds.colors)):
            birds.random_lanes[i] = i
            birds.lost[i] = i == 2
        necro = bat('necromancer')
        sim.state.enemies.bats[:] = [necro]
        birds.vy[3], birds.y[3] = 1, 10
        sim.state.enemies.zombies[:] = [{'lane': 2, 'y': 11, 'vy': -1, 'owner': necro['uid'], 'fear': 1.5, 'scared': []}]
        sim.state.game.frame_count = 0
        bat_abilities.update_zombies()
        assert 3 in game_state.special.scared_birds
