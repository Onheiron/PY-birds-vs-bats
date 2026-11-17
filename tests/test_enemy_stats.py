"""Enemy stats and elite bats."""

from src.core import constants
from src.engine import clock, enemy_stats, stats
from src.engine.logic.spawning import process_spawn_queue, spawn_bat
from tests.harness import FRAME_DT, Simulation


def bat(tier=2, hp=20, **flags):
    return {'tier': tier, 'hp': hp, 'max_hp': hp, 'x_pos': 10, 'y_pos': 5, 'target_y': 5, 'direction': 1, **flags}


def test_tier_stats():
    with Simulation(seed=1, key_rate=0):
        b = enemy_stats.equip_bat(bat(tier=1))
        assert b['stats'] == {}
        assert enemy_stats.mitigate(b, 70, 'contact') == 70
        b = enemy_stats.equip_bat(bat(tier=2))
        assert enemy_stats.mitigate(b, 70, 'contact') == 69  # defense 1


def test_armored_bats_have_armor_and_move_slower():
    with Simulation(seed=1, key_rate=0):
        b = enemy_stats.equip_bat(bat(tier=4, armored=True))
        assert enemy_stats.get(b, 'armor') == 20
        assert enemy_stats.get(b, 'speed') == 0.6 * 0.9
        assert enemy_stats.get(b, 'descent_interval') == 6
        assert b['max_hp'] == int(20 * 1.3)
        # 50 − defense 4 − armor 20
        assert enemy_stats.mitigate(b, 50, 'contact') == 26
        assert enemy_stats.mitigate(b, 50, 'contact', armor_cut=20) == 46
        # Armor does not stop projectiles, and armored bats are weak to them
        assert enemy_stats.mitigate(b, 50, 'projectile') == 51


def test_armor_pierce_and_minimum_damage():
    with Simulation(seed=1, key_rate=0):
        b = enemy_stats.equip_bat(bat(tier=4, armored=True))
        pierce = stats.bird(0, 'armor_pierce')
        stats.add_modifier(0, 'armor_pierce', add=5)
        assert enemy_stats.mitigate(b, 50, 'contact', bird=0) == 26 + pierce + 5
        assert enemy_stats.mitigate(b, 1, 'contact') == 1


def test_elites_get_affixes_hp_and_rewards():
    with Simulation(seed=1, key_rate=0):
        b = enemy_stats.equip_bat(bat(tier=1), ['warded', 'hulking'])
        assert b['elite'] and b['affixes'] == ['warded', 'hulking']
        assert b['max_hp'] == int(20 * 2.0 * 1.5)
        assert enemy_stats.get(b, 'xp_mult') == 2.0
        assert enemy_stats.mitigate(b, 100, 'projectile') == 50  # 100 × 0.8 − 30
        assert enemy_stats.affix_names(b['affixes']) == 'Warded Hulking'
        assert enemy_stats.upgrade_rarity('rare', enemy_stats.get(b, 'loot_rarity_bonus')) == 'epic'
        assert enemy_stats.upgrade_rarity('mythical', 3) == 'mythical'


def test_regeneration_heals_over_game_time():
    with Simulation(seed=1, key_rate=0) as sim:
        # Far above the screen, where nothing can hit it
        b = enemy_stats.equip_bat(bat(tier=1, hp=400, y_pos=-50, target_y=-50), ['regenerating'])
        b['hp'] = 10
        sim.state.enemies.bats.append(b)
        enemy_stats.regenerate()
        start = clock.now()
        sim.run(int(3 / FRAME_DT))
        healed = 20 * (clock.now() - start)
        # Regeneration runs on simulation ticks, so it can lag by up to one tick
        assert healed - 8 <= b['hp'] - 10 <= healed


def test_elites_spawn_by_biome_chance(monkeypatch):
    with Simulation(seed=3, key_rate=0) as sim:
        state = sim.state
        state.game.level, state.game.level_group = 16, 6
        monkeypatch.setattr(constants.elites, 'chance_by_biome', [1, 1, 1, 1, 1, 1])
        state.enemies.bats.clear()
        state.enemies.bat_spawn_timer = 0
        spawn_bat()
        process_spawn_queue()
        assert state.enemies.bats and state.enemies.bats[-1]['elite']
        assert len(state.enemies.bats[-1]['affixes']) == 2
