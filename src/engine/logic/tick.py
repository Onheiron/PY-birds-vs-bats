"""Per-tick orchestration of all game logic."""

from src.core import state
from src.engine.logic.bosses.director import check_bird_boss_collision, check_bird_meteor_collision, should_spawn_boss, spawn_boss, update_boss
from src.engine.logic.collisions import check_bat_obstacle_collision, check_bird_bat_collision, check_bird_ceiling_bounce, check_bird_floor_collision, check_bird_obstacle_collision, check_projectile_collision
from src.engine.logic.effects import update_enemy_debuffs, update_powerup_timers, update_purple_charging, update_special_bird_states, update_spell_effects
from src.engine.logic.flowers import update_obstacle_flowers
from src.engine.logic.loot import check_loot_collection
from src.engine.logic.mini_bats import check_bird_mini_bat_collision, update_mini_bats
from src.engine.logic.portals import update_portals
from src.engine.logic.scoring import update_score_tick
from src.services.sound import sync_active_birds
from src.engine.logic.spawning import despawn_old_entities, process_spawn_queue, spawn_bat, spawn_cloud_bank, spawn_obstacle, update_cloud_banks


def update_all():
    """Run all game logic updates in correct order."""
    # Score tick
    update_score_tick()

    # Boss spawn check
    if should_spawn_boss():
        spawn_boss()

    # Collisions
    check_bird_ceiling_bounce()
    check_bird_obstacle_collision()
    check_bird_bat_collision()
    check_bird_mini_bat_collision()
    check_bird_boss_collision()  # Boss collision
    check_bird_meteor_collision()  # Owl Boss meteors
    check_projectile_collision()
    check_loot_collection()
    check_bat_obstacle_collision()
    check_bird_floor_collision()

    # Spawning (don't spawn enemies while boss is active)
    if state.enemies.boss is None:
        spawn_obstacle()
        spawn_bat()
    spawn_cloud_bank()  # Mountain Range clouds
    process_spawn_queue()

    # Update cloud banks (Mountain Range foreground)
    update_cloud_banks()

    # Update mini bats (animations, hiding logic)
    update_mini_bats()

    # Update obstacle flowers (swamp biome)
    update_obstacle_flowers()

    # Update boss (movement, scream attacks)
    update_boss()

    # Timer updates
    update_powerup_timers()
    update_special_bird_states()
    update_spell_effects()  # Spellcaster bat effects
    update_enemy_debuffs()  # FROSTY/POISON/BERSERK debuffs on enemies
    update_purple_charging()
    update_portals()  # Cave biome portals

    # Cleanup
    despawn_old_entities()

    # Sync bird types with audio (dynamic music)
    sync_active_birds()
