"""Boss lifecycle: spawn conditions, dispatch and collisions."""

from collections.abc import Callable
from dataclasses import dataclass

from src.core import constants, state
from src.engine import bird_kinds, stats
from src.engine.birds import reset_bird_power, scare_bird_ticks, set_ball_vy, stun_bird
from src.engine.logic import afflictions
from src.engine.logic.bosses.basic import spawn_basic_boss, update_basic_boss
from src.engine.logic.bosses.common import get_boss_config
from src.engine.logic.bosses.jelly import spawn_jelly_boss, update_jelly_boss
from src.engine.logic.bosses.owl import spawn_owl_boss, update_owl_boss
from src.engine.logic.bosses.tree import check_bird_tree_branch_collision, spawn_tree_boss, update_tree_boss
from src.engine.logic.bosses.wind import spawn_wind_boss, update_wind_boss
from src.engine.logic.damage import calculate_bird_damage
from src.engine.progression import add_score, award_damage_xp, get_level_milestones, hp_scale
from src.entities.sprites import BLUE, ORANGE
from src.services.sound import play_sfx


@dataclass(frozen=True)
class BossKind:
    """A boss with its own behaviour, bound to one level through its config section."""

    boss_type: str
    config_section: str
    default_level: int
    default_spawn_miles: int
    spawn: Callable[[], None]
    update: Callable[[], None]

    @property
    def config(self):
        return getattr(constants, self.config_section, None)

    @property
    def level(self):
        return getattr(self.config, 'level', self.default_level)

    @property
    def spawn_miles_before_transition(self):
        return getattr(self.config, 'spawn_miles_before_transition', self.default_spawn_miles)


# Bosses with dedicated mechanics. Any other boss level gets the basic boss.
SPECIAL_BOSSES = (
    BossKind('wind', 'wind_boss', 6, 1, spawn_wind_boss, update_wind_boss),
    BossKind('jelly', 'jelly_boss', 9, 1, spawn_jelly_boss, update_jelly_boss),
    BossKind('tree', 'tree_boss', 12, 3, spawn_tree_boss, update_tree_boss),
    BossKind('owl', 'owl_boss', 15, 3, spawn_owl_boss, update_owl_boss),
)
_UPDATE_BY_TYPE = {kind.boss_type: kind.update for kind in SPECIAL_BOSSES}


def special_boss_for_level(level):
    """The special boss configured for ``level``, or None."""
    for kind in SPECIAL_BOSSES:
        if kind.level == level:
            return kind
    return None


def should_spawn_boss():
    """Check if boss should spawn (end of biome level, near transition)."""
    # Already spawned or defeated this level?
    if state.enemies.boss_spawned or state.enemies.boss is not None:
        return False

    level = state.game.level
    special = special_boss_for_level(level)
    boss_cfg = get_boss_config()

    if special is not None:
        spawn_miles_before = special.spawn_miles_before_transition
    else:
        # Basic boss: needs its config and a level listed in boss_levels
        if boss_cfg is None or level not in getattr(boss_cfg, 'boss_levels', [3, 6, 9, 12, 15, 18]):
            return False
        spawn_miles_before = getattr(boss_cfg, 'spawn_miles_before_transition', 1)

    milestones = get_level_milestones()
    # Miles at which the current level starts and ends
    level_start_miles = milestones[level - 2] if level >= 2 else 0
    level_end_miles = milestones[level - 1] if level <= len(milestones) else milestones[-1]

    miles_in_level = state.game.miles - level_start_miles
    miles_remaining = level_end_miles - state.game.miles

    # Spawn once we are inside the level and close enough to its end
    return miles_in_level > 0 and miles_remaining <= spawn_miles_before


def spawn_boss():
    """Spawn the boss for current biome."""
    special = special_boss_for_level(state.game.level)
    if special is not None:
        special.spawn()
    else:
        spawn_basic_boss()


def update_boss():
    """Update boss state and behavior."""
    boss = state.enemies.boss
    if boss is None:
        return
    _UPDATE_BY_TYPE.get(boss.get('boss_type', 'normal'), update_basic_boss)()


def check_bird_boss_collision():
    """Check bird-boss collisions."""
    boss = state.enemies.boss
    if boss is None or boss['state'] in ('dying', 'dead'):
        return

    # Special handling for Tree Boss (collision with branches)
    if boss.get('boss_type') == 'tree':
        check_bird_tree_branch_collision()
        return

    # Get boss config based on type
    boss_type = boss.get('boss_type', 'normal')
    if boss_type == 'owl':
        boss_cfg = getattr(constants, 'owl_boss', None)
        boss_width = 15  # Owl boss hitbox width (wider than sprite for easier hits)
        boss_height = 6  # Owl boss hitbox height (slightly taller)
    elif boss_type == 'wind':
        boss_cfg = getattr(constants, 'wind_boss', None)
        boss_width = 26
        boss_height = 5
    elif boss_type == 'jelly':
        boss_cfg = getattr(constants, 'jelly_boss', None)
        boss_width = 23
        boss_height = 6
    else:
        boss_cfg = get_boss_config()
        boss_width = 19
        boss_height = 3

    if boss_cfg is None:
        return

    # Boss hitbox
    boss_left = boss['x_pos']
    boss_right = boss['x_pos'] + boss_width
    boss_top = boss['y_pos']
    boss_bottom = boss['y_pos'] + boss_height

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i] or state.birds.vy[i] != -1:
            continue

        # Skip charging purple
        if state.special.purple_state[i] == 2 or state.special.purple_just_fired_frames[i] > 0:
            continue

        bird_color = state.birds.colors[i]
        bird_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_kinds.is_intangible(i):
            continue

        bird_height = bird_kinds.height(i)

        lane_left, lane_right = bird_kinds.hit_span(i)

        horizontal_overlap = not (boss_right < lane_left or boss_left > lane_right)
        vertical_overlap = not (bird_y + bird_height < boss_top or bird_y > boss_bottom)

        if not (horizontal_overlap and vertical_overlap):
            continue

        # Hit boss!
        damage = calculate_bird_damage(i, 'elite')

        # Apply armor reduction (lowered by freezing, bleeding and armor pierce)
        armor_reduction = getattr(boss_cfg, 'armor_reduction', 1)
        if armor_reduction > 0:
            # Bosses of later worlds are better armored (combat.boss_armor_per_world)
            per_world = float(getattr(constants.combat, 'boss_armor_per_world', 0))
            armor_reduction += per_world * (max(1, state.game.level_group) - 1)
        if armor_reduction > 0:
            armor_reduction = max(0, armor_reduction - afflictions.armor_cut(boss) - stats.bird(i, 'armor_pierce'))
        if bird_color != ORANGE:
            damage = max(1, damage - armor_reduction)
            afflictions.try_afflict(i, boss, is_boss=True)

        if bird_color == ORANGE:
            boss['hp'] -= 32 * hp_scale()  # Orange does a fixed 32 (×hp_scale) to bosses
        else:
            boss['hp'] -= damage
            award_damage_xp(i, damage, 'contact', 'boss')

        # Boss scream if hit causes scare
        scare_bird_ticks(i, int(1.0 / constants.timing.base_sleep))

        if boss['hp'] <= 0:
            boss['state'] = 'dying'
            play_sfx('boss_death')
        else:
            set_ball_vy(i, 1)
            state.birds.y[i] = boss_bottom + 1
            if bird_color == BLUE:
                reset_bird_power(i)
            play_sfx('hit')
        break


def check_bird_meteor_collision():
    """Check bird-meteor collisions (Owl Boss meteors)."""
    boss = state.enemies.boss
    if boss is None or boss.get('boss_type') != 'owl':
        return

    owl_meteors = boss.get('owl_meteors', [])
    if not owl_meteors:
        return

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i] or state.birds.vy[i] != -1:
            continue

        # Skip charging purple
        if state.special.purple_state[i] == 2 or state.special.purple_just_fired_frames[i] > 0:
            continue

        bird_color = state.birds.colors[i]
        bird_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_kinds.is_intangible(i):
            continue

        bird_height = bird_kinds.height(i)

        for meteor in owl_meteors:
            meteor_x = meteor['x_pos']
            meteor_y = meteor['y_pos']
            meteor_width = meteor.get('width', 6)

            # Meteor hitbox
            meteor_left = meteor_x - meteor_width // 2
            meteor_right = meteor_x + meteor_width // 2
            meteor_top = meteor_y
            meteor_bottom = meteor_y + 4  # Meteor is ~4 lines tall

            lane_left, lane_right = bird_kinds.hit_span(i)

            horizontal_overlap = not (meteor_right < lane_left or meteor_left > lane_right)
            vertical_overlap = not (bird_y + bird_height < meteor_top or bird_y > meteor_bottom)

            if not (horizontal_overlap and vertical_overlap):
                continue

            # Hit meteor!
            damage = calculate_bird_damage(i, 'obstacle')

            if bird_color == ORANGE:
                meteor['hp'] = 0  # Orange destroys meteor
            else:
                meteor['hp'] = meteor.get('hp', 1) - damage
                award_damage_xp(i, damage)

            if meteor['hp'] <= 0:
                # Meteor destroyed
                add_score(100)
                play_sfx('destroy')
            else:
                # Bounce bird down
                set_ball_vy(i, 1)
                state.birds.y[i] = meteor_bottom + 1
                # Stun bird briefly
                stun_bird(i, 0.5)
                if bird_color == BLUE:
                    reset_bird_power(i)
                play_sfx('hit')
            break
