"""Every lane keeps exactly one bird slot, and a dormant Orange keeps its egg."""

from src.core import constants
from src.engine import stats
from src.engine.birds import is_orange_egg_state
from src.engine.logic.collisions import check_bird_ceiling_bounce
from src.engine.logic.effects import _execute_exile_swap
from src.engine.logic.loot import check_loot_collection, restore_orange_eggs
from src.entities.sprites import ORANGE
from tests.harness import Simulation


def bird_in_lane(state, lane):
    return next(i for i in range(constants.layout.num_balls) if state.birds.random_lanes[i] == lane)


def orange_eggs(state):
    return [loot for loot in state.items.loot_items if loot['type'] == 'orange_egg']


def put_orange_to_sleep(sim, lane):
    state = sim.state
    orange = bird_in_lane(state, lane)
    state.birds.colors[orange] = ORANGE
    state.birds.y[orange] = 1
    check_bird_ceiling_bounce()
    assert is_orange_egg_state(orange) and len(orange_eggs(state)) == 1
    return orange


def test_neighbours_with_a_wide_pickup_do_not_take_the_orange_egg():
    with Simulation(seed=1, key_rate=0) as sim:
        state = sim.state
        put_orange_to_sleep(sim, 8)
        neighbour = bird_in_lane(state, 7)
        stats.add_modifier(neighbour, 'pickup_radius', add=6)
        state.birds.y[neighbour] = constants.layout.starting_line
        check_loot_collection()
        assert len(orange_eggs(state)) == 1


def test_a_missing_orange_egg_is_put_back():
    with Simulation(seed=1, key_rate=0) as sim:
        state = sim.state
        put_orange_to_sleep(sim, 8)
        state.items.loot_items.clear()
        restore_orange_eggs()
        assert [loot['x_pos'] for loot in orange_eggs(state)] == [constants.layout.lane_positions[8]]


def test_exile_into_an_empty_lane_keeps_one_slot_per_lane():
    with Simulation(seed=1, key_rate=0) as sim:
        state = sim.state
        empty = bird_in_lane(state, 2)
        state.birds.lost[empty] = True
        mover = bird_in_lane(state, 6)
        _execute_exile_swap({'bird_a_idx': mover, 'bird_b_idx': None, 'empty_lane': 2})
        assert state.birds.random_lanes[mover] == 2
        assert sorted(state.birds.random_lanes) == list(range(constants.layout.num_lanes))
        assert sorted(state.birds.home_lanes) == list(range(constants.layout.num_lanes))
        assert state.birds.random_lanes[empty] == 6


def test_a_poisoned_bird_is_marked_outside_boss_fights():
    from src.engine.logic.flowers import apply_flower_collision_effect

    with Simulation(seed=1, key_rate=0, level=10) as sim:
        sim.run(40)
        while 3 not in sim.state.special.poisoned_birds:
            apply_flower_collision_effect({'type': 'green'}, 3)
        sim.run(4)
        assert sim.state.enemies.boss is None
        assert '☠' in sim.screen.text()
        assert 'Poisoned!' in sim.screen.text()


def living_lanes(state):
    return sorted(state.birds.random_lanes[i] for i in range(constants.layout.num_balls) if not state.birds.lost[i])


def test_exile_then_a_swap_keeps_one_bird_per_lane():
    from src.engine import actions

    with Simulation(seed=1, key_rate=0) as sim:
        state = sim.state
        a, b = bird_in_lane(state, 2), bird_in_lane(state, 5)
        _execute_exile_swap({'bird_a_idx': a, 'bird_b_idx': b, 'empty_lane': None})
        state.game.momentum = 1e9
        state.player.selected_lane, state.player.lane = 2, 3
        actions._execute_swap()
        assert living_lanes(state) == list(range(constants.layout.num_lanes))


def test_a_hatch_never_lands_on_a_living_bird():
    from src.engine.logic.loot import _spawn_bird_from_egg

    with Simulation(seed=1, key_rate=0) as sim:
        state = sim.state
        lost = bird_in_lane(state, 4)
        state.birds.lost[lost] = True
        state.birds.random_lanes[bird_in_lane(state, 3)] = 4  # a living bird moved into its lane
        _spawn_bird_from_egg('yellow_egg')
        assert not state.birds.lost[lost]
        assert len(set(living_lanes(state))) == constants.layout.num_balls


def test_a_beaten_boss_does_not_come_back_when_the_game_is_loaded():
    from src.engine.logic.bosses.director import should_spawn_boss
    from src.services import save_manager

    with Simulation(seed=1, key_rate=0, level=9) as sim:
        state = sim.state
        state.enemies.boss_spawned = state.enemies.boss_defeated = True
        state.enemies.boss = None
        data = save_manager.snapshot()
        assert save_manager.apply_save_data(data)
        assert state.enemies.boss_defeated and not should_spawn_boss()


def test_a_swap_takes_the_birds_the_player_sees_even_with_wrong_homes():
    from src.engine import actions

    with Simulation(seed=1, key_rate=0) as sim:
        state = sim.state
        n = constants.layout.num_balls
        state.birds.home_lanes[:] = [(lane + 3) % n for lane in state.birds.random_lanes]  # a broken save
        a, b = bird_in_lane(state, 2), bird_in_lane(state, 6)
        state.game.momentum = 1e9
        state.player.selected_lane, state.player.lane = 2, 6
        actions._execute_swap()
        assert state.birds.random_lanes[a] == 6 and state.birds.random_lanes[b] == 2
        assert living_lanes(state) == list(range(constants.layout.num_lanes))
        assert state.birds.home_lanes == state.birds.random_lanes


def test_loading_a_broken_save_puts_one_bird_in_every_lane():
    from src.services import save_manager

    with Simulation(seed=1, key_rate=0) as sim:
        state = sim.state
        state.birds.random_lanes[bird_in_lane(state, 5)] = 2  # two birds in lane 2, none in 5
        assert save_manager.apply_save_data(save_manager.snapshot())
        assert living_lanes(state) == list(range(constants.layout.num_lanes))
