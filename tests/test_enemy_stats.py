"""Enemy stats and elite bats."""

from src.core import constants
from src.engine import clock, enemy_stats, stats
from src.engine.logic.spawning import new_bat, spawn_bat
from tests.harness import FRAME_DT, Simulation


def bat(tier=2, hp=20, **flags):
    return {'tier': tier, 'hp': hp, 'max_hp': hp, 'x_pos': 10, 'y_pos': 5, 'target_y': 5, 'direction': 1, **flags}


def test_tier_stats():
    with Simulation(seed=1, key_rate=0):
        b = enemy_stats.equip_bat(bat(tier=1))
        assert b['stats'] == {}
        assert enemy_stats.mitigate(b, 70, 'contact') == 70
        b = enemy_stats.equip_bat(bat(tier=2))
        assert enemy_stats.mitigate(b, 70, 'contact') == 60  # defense 1 (× hp_scale 10)


def test_armored_bats_have_armor_and_move_slower():
    with Simulation(seed=1, key_rate=0):
        b = enemy_stats.equip_bat(bat(tier=4, armored=True))
        assert enemy_stats.get(b, 'armor') == 20
        assert enemy_stats.get(b, 'speed') == 0.6 * 0.9
        assert enemy_stats.get(b, 'descent_interval') == 6
        assert b['max_hp'] == int(20 * 1.3)
        # 500 − (defense 4 + armor 20) × hp_scale 10
        assert enemy_stats.mitigate(b, 500, 'contact') == 260
        assert enemy_stats.mitigate(b, 500, 'contact', armor_cut=20) == 460
        # Armor does not stop projectiles, and armored bats are weak to them
        assert enemy_stats.mitigate(b, 500, 'projectile') == 510


def test_armor_pierce_and_minimum_damage():
    with Simulation(seed=1, key_rate=0):
        b = enemy_stats.equip_bat(bat(tier=4, armored=True))
        pierce = stats.bird(0, 'armor_pierce')
        stats.add_modifier(0, 'armor_pierce', add=5)
        assert enemy_stats.mitigate(b, 500, 'contact', bird=0) == 260 + (pierce + 5) * 10
        assert enemy_stats.mitigate(b, 1, 'contact') == 1


def test_elites_get_affixes_hp_and_rewards():
    with Simulation(seed=1, key_rate=0):
        b = enemy_stats.equip_bat(bat(tier=1), ['warded', 'hulking'])
        assert b['elite'] and b['affixes'] == ['warded', 'hulking']
        assert b['max_hp'] == int(20 * 2.0 * 1.5)
        assert enemy_stats.get(b, 'xp_mult') == 2.0
        assert enemy_stats.mitigate(b, 100, 'projectile') == 30  # 100 × 0.8 − 5 × hp_scale 10
        assert enemy_stats.affix_names(b['affixes']) == 'Warded Hulking'
        assert enemy_stats.upgrade_rarity('rare', enemy_stats.get(b, 'loot_rarity_bonus')) == 'epic'
        assert enemy_stats.upgrade_rarity('mythical', 3) == 'mythical'
        assert enemy_stats.upgrade_rarity('legendary', 1) == 'legendary'  # luck never makes a mythical
        assert enemy_stats.upgrade_rarity('epic', 3) == 'legendary'


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
        bat = new_bat(enemy_stats.roll_tier(enemy_stats.world_table()))
        assert bat['elite']
        # Plain elites get 2 random affixes in world 6; special kinds get their elite behaviour instead
        assert len(bat['affixes']) == (0 if bat.get('kind') else 2)


# --------------------------------------------------------------------- world tables and layers


def test_the_first_world_has_no_bats_but_mini_bats_at_ten_percent():
    with Simulation(seed=1, key_rate=0) as sim:
        sim.state.game.level_group = 1
        world = enemy_stats.world_table()
        assert world['max_bats'] == 0 and world['mini_bat'] == 0.10
        sim.state.enemies.bat_spawn_timer = 1
        spawn_bat()
        assert not sim.state.enemies.spawn_queue


def test_kinds_respect_their_lowest_tier():
    with Simulation(seed=1, key_rate=0):
        world = {'kinds': {'armored': 1.0}}
        assert enemy_stats.roll_kind(1, world) is None  # armored from tier 2
        assert enemy_stats.roll_kind(2, world) == 'armored'


def test_armored_bats_linger_longer_and_push_scared_birds_down_harder():
    with Simulation(seed=1, key_rate=0):
        b = enemy_stats.make_bat(2, 'armored', 10, 5, 5, 480)
        assert enemy_stats.get(b, 'linger') == 150
        assert enemy_stats.get(b, 'fear_push') == 2
        assert enemy_stats.get(b, 'armor') == 10


def test_world_layers_change_a_kind_world_by_world():
    with Simulation(seed=1, key_rate=0) as sim:
        sim.state.game.level_group = 3
        caster = enemy_stats.make_bat(4, 'spellcaster', 10, 5, 5, 1920)
        assert caster['known_spells'] == ['silence']  # world 3: silence only
        sim.state.game.level_group = 6
        caster = enemy_stats.make_bat(4, 'spellcaster', 10, 5, 5, 1920)
        assert caster['known_spells'] == ['silence', 'repugnant_wind', 'exile']
        assert abs(enemy_stats.get(caster, 'ability_chance') - 0.3) < 1e-9


def test_elites_of_a_kind_get_their_kind_layer(monkeypatch):
    with Simulation(seed=1, key_rate=0):
        monkeypatch.setattr(constants.enemy_stats.bats, 'elite_kinds', {'diver': {'dive_rows': 5}}, raising=False)
        plain = enemy_stats.make_bat(2, 'diver', 10, 5, 5, 480)
        elite = enemy_stats.make_bat(2, 'diver', 10, 5, 5, 480, affixes=['swift'])
        assert enemy_stats.get(plain, 'dive_rows') == 10
        assert enemy_stats.get(elite, 'dive_rows') == 15
