"""Bird stats: defaults, kinds, grades and runtime modifiers."""

from src.engine import clock, stats
from src.engine.birds import get_scared_frames, scare_bird
from src.engine.grades import compute_grade_from_xp
from src.engine.logic.damage import calculate_bird_damage
from src.entities.sprites import DINOSAUR, GLITCH, RED, WHITE, YELLOW
from tests.harness import FRAME_DT, Simulation


def set_grade(state, i, grade):
    xp = 0
    step = 1
    while compute_grade_from_xp(xp)[0] != grade:
        xp += step
        step = max(1, int(step * 1.05))
    state.birds.per_bird_xp[i] = xp


def setup_bird(sim, color, grade='D'):
    state = sim.state
    state.birds.colors[0] = color
    set_grade(state, 0, grade)
    return state


def test_defaults_and_kinds():
    with Simulation(seed=1, key_rate=0) as sim:
        setup_bird(sim, YELLOW)
        assert stats.bird(0, 'power_uses') == 1
        assert stats.bird(0, 'hitbox_height') == 2
        assert stats.bird(0, 'prestige') == 0
        setup_bird(sim, DINOSAUR)
        assert stats.bird(0, 'hitbox_height') == 3
        assert stats.bird(0, 'presses_to_bounce') == 15
        setup_bird(sim, WHITE)
        assert stats.bird(0, 'score_mult') == 1.5
        setup_bird(sim, GLITCH)
        assert stats.bird(0, 'floor_save') == 0.1


def test_grades_raise_stats():
    with Simulation(seed=1, key_rate=0) as sim:
        setup_bird(sim, RED, 'C1')
        assert stats.bird(0, 'fear_duration_cut') == 0
        setup_bird(sim, RED, 'B1')
        assert stats.bird(0, 'fear_duration_cut') == 1
        assert stats.bird(0, 'power_uses') == 1
        setup_bird(sim, RED, 'A1')
        assert stats.bird(0, 'power_uses') == 2
        # Grades never take a bonus away: S keeps the second power
        setup_bird(sim, RED, 'S')
        assert stats.bird(0, 'power_uses') == 2
        assert stats.bird(0, 'prestige') == 5


def test_modifiers_add_multiply_and_expire():
    with Simulation(seed=1, key_rate=0) as sim:
        setup_bird(sim, RED)
        base = stats.bird(0, 'damage_mult')
        stats.add_modifier(0, 'damage_mult', mul=2.0, seconds=1.0)
        stats.add_modifier('flock', 'damage_bonus', add=3)
        assert stats.bird(0, 'damage_mult') == base * 2
        assert stats.bird(1, 'damage_mult') == base
        assert stats.bird(1, 'damage_bonus') == 3
        sim.run(int(1.5 / FRAME_DT) + 10)
        assert stats.bird(0, 'damage_mult') == base, 'the timed modifier expired'
        assert stats.bird(0, 'damage_bonus') == 3, 'the permanent one stays'


def test_stats_are_clamped():
    with Simulation(seed=1, key_rate=0) as sim:
        setup_bird(sim, RED)
        stats.add_modifier(0, 'crit_chance', add=5)
        assert stats.bird(0, 'crit_chance') == 1


def test_damage_follows_attack_stats():
    with Simulation(seed=1, key_rate=0) as sim:
        # Yellow: no critical hits, so damage is deterministic
        state = setup_bird(sim, YELLOW)
        state.special.scared_birds.pop(0, None)
        state.birds.power_used[0] = False
        plain = calculate_bird_damage(0)
        stats.add_modifier(0, 'damage_mult', mul=3.0)
        # Damage is rounded once at the end, so allow the rounding of the unscaled value
        assert abs(calculate_bird_damage(0) - plain * 3) <= 1.5
        stats.add_modifier(0, 'vs_obstacles', add=1.0)
        assert abs(calculate_bird_damage(0, 'obstacle') - 2 * calculate_bird_damage(0, 'bat')) <= 1


def test_fear_stats():
    with Simulation(seed=1, key_rate=0) as sim:
        state = setup_bird(sim, RED)
        two_seconds = get_scared_frames(0, 2.0)
        stats.add_modifier(0, 'fear_duration_mult', mul=0.5)
        assert get_scared_frames(0, 2.0) < two_seconds
        stats.add_modifier(0, 'fear_immunity', add=1.0)
        state.special.scared_birds.pop(0, None)
        assert not scare_bird(0, 2.0)
        assert 0 not in state.special.scared_birds


def test_modifiers_survive_save_and_load(tmp_path, monkeypatch):
    from src.services import save_manager

    monkeypatch.setattr(save_manager, 'get_save_path', lambda slot: tmp_path / f'slot{slot}.json')
    with Simulation(seed=1, key_rate=0) as sim:
        setup_bird(sim, RED)
        before = stats.bird(2, 'luck')
        stats.add_modifier(2, 'luck', add=0.5, seconds=100, source='test')
        assert save_manager.save_game(1)
        sim.state.stats.modifiers.clear()
        assert save_manager.load_game(1)
        assert stats.bird(2, 'luck') == before + 0.5
        mod = sim.state.stats.modifiers[0]
        assert mod['target'] == 2 and mod['until'] > clock.now()
