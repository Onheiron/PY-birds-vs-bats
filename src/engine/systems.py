"""The simulation tick, as an ordered list of systems grouped in phases.

Each tick runs every system once, phase by phase and in the order listed:

  MOVE      everything that moves advances one step
  PROGRESS  score from the flock's height; the end-of-biome boss appears
  COLLIDE   birds against ceiling, enemies, projectiles, loot and floor
  SPAWN     new obstacles, bats, cloud banks and queued spawns
  ACT       enemies and scenery act: mini bats, flowers, cloud banks, boss
  EFFECTS   timers of power-ups, bird states, spells, debuffs, portals
  CLEANUP   old entities leave, outcomes are announced, music follows the flock

A system may carry a condition: it only runs while the condition holds.
The order is part of the game rules (for example a bird that reaches the floor
in COLLIDE is not hit by a bat spawned in SPAWN of the same tick), and the
replay tests pin it down.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from src.core import state
from src.engine import choices, enemy_stats, events, hazards, stats, synergies
from src.engine.bat_ai import update_bat_positions
from src.engine.glitch import update_glitch_chaos
from src.engine.logic import afflictions
from src.engine.logic.bosses.director import (
    check_bird_boss_collision,
    check_bird_meteor_collision,
    should_spawn_boss,
    spawn_boss,
    update_boss,
)
from src.engine.logic.collisions import (
    check_bat_obstacle_collision,
    check_bird_bat_collision,
    check_bird_ceiling_bounce,
    check_bird_floor_collision,
    check_bird_obstacle_collision,
    check_projectile_collision,
)
from src.engine.logic.effects import (
    update_powerup_timers,
    update_purple_charging,
    update_special_bird_states,
    update_spell_effects,
)
from src.engine.logic.flowers import update_obstacle_flowers
from src.engine.logic.loot import check_loot_collection, restore_orange_eggs
from src.engine.logic.mini_bats import check_bird_mini_bat_collision, update_mini_bats
from src.engine.logic.portals import update_portals
from src.engine.logic.scoring import update_score_tick
from src.engine.logic.spawning import (
    despawn_old_entities,
    process_spawn_queue,
    spawn_bat,
    spawn_obstacle,
)
from src.engine.physics import (
    update_bird_positions,
    update_loot_positions,
    update_mini_bat_positions,
    update_obstacle_positions,
    update_projectile_positions,
    update_right_panel_barriers,
)
from src.services.sound import sync_active_birds


class Phase(IntEnum):
    MOVE = 1
    PROGRESS = 2
    COLLIDE = 3
    SPAWN = 4
    ACT = 5
    EFFECTS = 6
    CLEANUP = 7


@dataclass(frozen=True)
class System:
    name: str
    phase: Phase
    run: Callable[[], None]
    when: Callable[[], bool] | None = None


def no_boss():
    return state.enemies.boss is None


def _spawn_boss_when_due():
    if should_spawn_boss():
        spawn_boss()
        events.emit('boss_spawned', boss_type=state.enemies.boss.get('boss_type', 'normal'))


class _BossWatch:
    """Announces a boss defeat once, whichever boss module ended the fight."""

    def __init__(self):
        self.boss_type = None
        self.defeated = False

    def __call__(self):
        boss = state.enemies.boss
        if boss is not None:
            self.boss_type = boss.get('boss_type', 'normal')
        defeated = state.enemies.boss_defeated
        if defeated and not self.defeated and self.boss_type is not None:
            events.emit('boss_defeated', boss_type=self.boss_type)
            self.boss_type = None
            # Every biome boss offers a pact (see src/engine/cards.py)
            choices.offer_pact(state.game.level_group)
        self.defeated = defeated


SYSTEMS = (
    # Glitch chaos acts before anything moves
    System('glitch chaos', Phase.MOVE, update_glitch_chaos),
    System('birds', Phase.MOVE, update_bird_positions),
    System('projectiles', Phase.MOVE, update_projectile_positions),
    System('obstacles', Phase.MOVE, update_obstacle_positions),
    System('bats', Phase.MOVE, update_bat_positions),
    System('mini bats', Phase.MOVE, update_mini_bat_positions),
    System('loot', Phase.MOVE, update_loot_positions),
    System('panel scenery', Phase.MOVE, update_right_panel_barriers),
    System('score', Phase.PROGRESS, update_score_tick),
    System('boss arrival', Phase.PROGRESS, _spawn_boss_when_due),
    System('ceiling', Phase.COLLIDE, check_bird_ceiling_bounce),
    System('bird vs obstacle', Phase.COLLIDE, check_bird_obstacle_collision),
    System('bird vs bat', Phase.COLLIDE, check_bird_bat_collision),
    System('bird vs mini bat', Phase.COLLIDE, check_bird_mini_bat_collision),
    System('bird vs boss', Phase.COLLIDE, check_bird_boss_collision),
    System('bird vs meteor', Phase.COLLIDE, check_bird_meteor_collision),
    System('projectiles hit', Phase.COLLIDE, check_projectile_collision),
    System('loot pickup', Phase.COLLIDE, check_loot_collection),
    System('bat vs obstacle', Phase.COLLIDE, check_bat_obstacle_collision),
    System('floor', Phase.COLLIDE, check_bird_floor_collision),
    # No regular enemies while a boss is on screen
    System('obstacle spawn', Phase.SPAWN, spawn_obstacle, when=no_boss),
    System('bat spawn', Phase.SPAWN, spawn_bat, when=no_boss),
    System('spawn queue', Phase.SPAWN, process_spawn_queue),
    System('world hazards', Phase.ACT, hazards.update),
    System('mini bats act', Phase.ACT, update_mini_bats),
    System('obstacle flowers', Phase.ACT, update_obstacle_flowers),
    System('boss', Phase.ACT, update_boss),
    System('stat modifiers', Phase.EFFECTS, stats.expire_modifiers),
    System('enemy regeneration', Phase.EFFECTS, enemy_stats.regenerate),
    System('power-up timers', Phase.EFFECTS, update_powerup_timers),
    System('bird states', Phase.EFFECTS, update_special_bird_states),
    System('spells', Phase.EFFECTS, update_spell_effects),
    System('synergies', Phase.EFFECTS, synergies.cure_blues),
    System('enemy afflictions', Phase.EFFECTS, afflictions.update),
    System('purple charging', Phase.EFFECTS, update_purple_charging),
    System('portals', Phase.EFFECTS, update_portals),
    System('despawn', Phase.CLEANUP, despawn_old_entities),
    System('orange eggs', Phase.CLEANUP, restore_orange_eggs),
    System('boss outcome', Phase.CLEANUP, _BossWatch()),
    System('dynamic music', Phase.CLEANUP, sync_active_birds),
)

assert list(SYSTEMS) == sorted(SYSTEMS, key=lambda s: s.phase), 'systems must be listed in phase order'


def run_tick():
    """Advance the simulation by one tick."""
    for system in SYSTEMS:
        if system.when is None or system.when():
            system.run()
