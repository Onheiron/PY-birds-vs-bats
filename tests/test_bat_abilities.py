"""Special bats: healer, bomber, plague, necromancer."""

from src.core import state as game_state
from src.engine import clock, enemy_stats
from src.engine.logic import bat_abilities
from src.entities.sprites import ZOMBIE
from tests.harness import Simulation


def bat(kind, tier=3, x=20, elite=None, **extra):
    b = enemy_stats.make_bat(tier, kind, x, 6, 6, 1000, elite=elite, **extra)
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


def lanes_by_slot(lost=()):
    birds = game_state.birds
    for i in range(len(birds.colors)):
        birds.random_lanes[i] = i
        birds.lost[i] = i in lost


def test_a_necromancer_raises_zombie_birds_in_empty_lanes(monkeypatch):
    with Simulation(seed=1, key_rate=0) as sim:
        always(monkeypatch)
        lanes_by_slot(lost=(2, 6, 7))
        necro = bat('necromancer')
        sim.state.enemies.bats[:] = [necro]
        for _ in range(5):
            necro['ability_ready'] = 0
            bat_abilities.necromancer(necro)
        zombies = [i for i in range(9) if game_state.birds.colors[i] == ZOMBIE and not game_state.birds.lost[i]]
        assert len(zombies) == 2 and set(zombies) <= {2, 6, 7}  # 2 at most, in empty lanes


def test_zombies_bounce_by_themselves_only_while_a_necromancer_lives():
    with Simulation(seed=1, key_rate=0) as sim:
        lanes_by_slot()
        necro = bat('necromancer')
        sim.state.enemies.bats[:] = [necro]
        bat_abilities._bite(4, {'fear': 1.5, 'bite': 0.0})
        birds = game_state.birds
        birds.vy[4], birds.y[4] = 1, sim.constants.layout.starting_line
        bat_abilities.update_zombies()
        assert birds.vy[4] == -1
        sim.state.enemies.bats[:] = []
        birds.vy[4] = 1
        bat_abilities.update_zombies()
        assert birds.vy[4] == 1  # no necromancer: up to you


def test_a_zombie_scares_and_may_bite_a_falling_neighbour(monkeypatch):
    with Simulation(seed=1, key_rate=0) as sim:
        lanes_by_slot()
        sim.state.enemies.bats[:] = []
        bat_abilities._bite(2, {'fear': 1.5, 'bite': 1.0})
        birds = game_state.birds
        birds.vy[2], birds.y[2] = -1, 10
        birds.vy[3], birds.y[3] = 1, 11
        bat_abilities.update_zombies()
        assert 3 in game_state.special.scared_birds
        assert birds.colors[3] == ZOMBIE and not birds.lost[3]  # still in the flock


def test_losing_a_raised_zombie_costs_no_life(monkeypatch):
    with Simulation(seed=1, key_rate=0) as sim:
        always(monkeypatch)
        lanes_by_slot(lost=(5,))
        necro = bat('necromancer')
        sim.state.enemies.bats[:] = [necro]
        bat_abilities.necromancer(necro)
        assert game_state.birds.colors[5] == ZOMBIE
        sim.state.enemies.bats[:] = []
        lives = game_state.game.lives
        game_state.birds.y[5], game_state.birds.vy[5] = sim.constants.layout.height - 1, 1
        from src.engine.logic.collisions import check_bird_floor_collision

        check_bird_floor_collision()
        assert game_state.birds.lost[5] and game_state.game.lives == lives


def test_an_elite_necromancer_keeps_three_zombies():
    with Simulation(seed=1, key_rate=0):
        elite = enemy_stats.make_bat(3, 'necromancer', 20, 6, 6, 1000, elite=True)
        assert enemy_stats.get(elite, 'zombies') == 3


# ------------------------------------------------------------------ elites of each kind


def test_special_elites_get_their_kind_and_no_random_affixes(monkeypatch):
    with Simulation(seed=1, key_rate=0) as sim:
        monkeypatch.setattr(enemy_stats, 'elite_chance', lambda: 1.0)
        assert enemy_stats.roll_elite('bomber') == (True, [])
        elite, affixes = enemy_stats.roll_elite(None)
        assert elite and affixes
        sim.state.game.level_group = 6
        healer = enemy_stats.make_bat(3, 'healer', 20, 6, 6, 1000, elite=True)
        assert abs(enemy_stats.get(healer, 'overheal') - 0.20) < 1e-9
        assert abs(enemy_stats.get(healer, 'heal_pct') - 0.15) < 1e-9


def test_an_elite_healer_heals_above_max_hp(monkeypatch):
    with Simulation(seed=1, key_rate=0) as sim:
        always(monkeypatch)
        sim.state.game.level_group = 6
        healer = bat('healer', elite=True)
        other = bat(None, x=24)
        other['hp'] = other['max_hp']
        sim.state.enemies.bats[:] = [healer, other]
        for _ in range(5):
            healer['ability_ready'] = 0
            bat_abilities.healer(healer)
        assert other['hp'] == int(other['max_hp'] * 1.2)


def test_an_elite_spellcaster_knows_every_spell_and_may_cast_two(monkeypatch):
    from src.engine import bat_ai

    with Simulation(seed=1, key_rate=0) as sim:
        sim.state.game.level_group = 3
        caster = enemy_stats.make_bat(2, 'spellcaster', 20, 6, 6, 500, elite=True)
        assert caster['known_spells'] == ['silence', 'repugnant_wind', 'exile']
        monkeypatch.setattr(bat_ai, 'per_tick', lambda chance: 1.0)
        monkeypatch.setattr(
            enemy_stats, 'get', lambda b, n, _g=enemy_stats.get: 1.0 if n == 'double_cast' else _g(b, n)
        )
        bat_ai._update_spellcaster_bat(caster)
        assert len(caster['current_spells']) == 2
        assert caster['casting_end_time'] - clock.now() == 1.0


def test_an_elite_bombers_stone_explodes_in_its_lane(monkeypatch):
    with Simulation(seed=1, key_rate=0) as sim:
        always(monkeypatch)
        lanes_by_slot()
        bomber = bat('bomber', elite=True)
        sim.state.enemies.obstacles[:] = []
        bat_abilities.bomber(bomber)
        stone = sim.state.enemies.obstacles[-1]
        assert stone['blast']['push'] == 3
        birds = game_state.birds
        lane = stone['lane']
        birds.vy[lane], birds.y[lane] = -1, stone['y_pos'] + 1
        bat_abilities.stone_blast(stone)  # broken by a shot
        assert birds.vy[lane] == 1 and lane in game_state.special.scared_birds


def test_an_elite_plague_bleeds_first_then_poisons():
    from src.engine.logic.effects import update_special_bird_states

    with Simulation(seed=1, key_rate=0):
        lanes_by_slot()
        plague = bat('plague', elite=True)
        bat_abilities.infect(4, plague)
        assert 4 in game_state.special.bleeding_birds and 4 not in game_state.special.poisoned_birds
        game_state.special.bleeding_birds[4]['end_time'] = clock.now() - 1
        update_special_bird_states()
        assert 4 not in game_state.special.bleeding_birds
        assert game_state.special.poisoned_birds[4]['cure_attempts_needed'] == 3
