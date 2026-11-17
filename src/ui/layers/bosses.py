"""Boss sprites."""

from src.core import constants, state
from src.entities.sprites import (
    BAT_ARMOR,
    BOSS_DEAD,
    BOSS_FRAME_1,
    BOSS_FRAME_2,
    BOSS_SCREAM,
    FLOWER_COLORS,
    FLOWER_GROWTH_FRAMES,
    JELLY_BOSS_DEAD,
    JELLY_BOSS_FRAMES,
    METEOR_LEFT,
    METEOR_RIGHT,
    METEOR_TRAIL,
    OWL_BOSS_DEAD,
    OWL_BOSS_FRAMES,
    TREE_BOSS_BRANCHES,
    WIND_BOSS_DEAD,
    WIND_BOSS_MAX_DOWN,
    WIND_BOSS_MAX_UP,
    WIND_BOSS_PULL_1,
    WIND_BOSS_PULL_2,
    WIND_BOSS_PULL_3,
    WIND_BOSS_PULL_4,
    WIND_BOSS_PUSH_1,
    WIND_BOSS_PUSH_2,
    WIND_BOSS_PUSH_3,
    WIND_BOSS_PUSH_4,
)
from src.ui.colors import apply_bold, color_from_hp_to_red
from src.ui.layers.background import TREE_HIDDEN_CHARS
from src.ui.layers.birds import draw_bird_status_indicators
from src.ui.layout import GAME_X_OFFSET, HEADER_HEIGHT


def draw_boss(fb):
    """Render the active boss with the renderer for its type."""
    boss = state.enemies.boss
    if boss is None:
        return
    _BOSS_RENDERERS.get(boss.get('boss_type', 'normal'), _draw_basic_boss)(fb)


def _draw_basic_boss(fb):
    """Render the default boss."""
    boss = state.enemies.boss
    boss_hp = boss.get('hp', 0)
    boss_max = boss.get('max_hp', boss_hp if boss_hp > 0 else 1)
    boss_state = boss.get('state', 'active')

    # Choose sprite based on state
    if boss_state == 'dying' or boss_state == 'dead':
        boss_sprite = BOSS_DEAD
    elif boss_state == 'screaming':
        boss_sprite = BOSS_SCREAM
    else:
        # Alternate between frames
        anim_frame = boss.get('anim_frame', 0)
        boss_sprite = BOSS_FRAME_1 if anim_frame == 0 else BOSS_FRAME_2

    # Color based on HP - fades to red instead of dark (stays visible)
    boss_color = apply_bold(color_from_hp_to_red(constants.colors.bats_base_rgb, boss_hp, boss_max))

    for line_idx, line in enumerate(boss_sprite):
        y_pos = boss['y_pos'] + line_idx
        if 0 <= y_pos < constants.layout.height:
            for i, char in enumerate(line):
                if char != ' ':
                    x_pos = boss['x_pos'] + i
                    if 0 <= x_pos < constants.layout.width:
                        # Color outer parentheses with armor color
                        char_color = boss_color
                        if line_idx == 1:  # Middle line has the armor ()
                            if char == '(' or char == ')':
                                line_before = line[:i]
                                open_count = line_before.count('(')
                                # First ( and last ) are the armor
                                if (char == '(' and open_count == 0) or (
                                    char == ')' and i == len(line) - line[::-1].index(')') - 1
                                ):
                                    char_color = BAT_ARMOR
                        fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, char_color)


def _draw_wind_boss(fb):
    """Render Wind Boss to framebuffer."""
    boss = state.enemies.boss
    if boss is None:
        return

    boss_hp = boss.get('hp', 0)
    boss_max = boss.get('max_hp', boss_hp if boss_hp > 0 else 1)
    boss_state = boss.get('state', 'active')
    anim_frame = boss.get('anim_frame', 0)

    # Map animation frame to sprite
    sprite_map = [
        WIND_BOSS_MAX_UP,  # 0
        WIND_BOSS_PUSH_1,  # 1
        WIND_BOSS_PUSH_2,  # 2
        WIND_BOSS_PUSH_3,  # 3
        WIND_BOSS_PUSH_4,  # 4
        WIND_BOSS_MAX_DOWN,  # 5
        WIND_BOSS_PULL_1,  # 6
        WIND_BOSS_PULL_2,  # 7
        WIND_BOSS_PULL_3,  # 8
        WIND_BOSS_PULL_4,  # 9
    ]

    if boss_state == 'dying' or boss_state == 'dead':
        boss_sprite = WIND_BOSS_DEAD
    else:
        boss_sprite = sprite_map[anim_frame % len(sprite_map)]

    # Color based on HP
    boss_color = apply_bold(color_from_hp_to_red(constants.colors.bats_base_rgb, boss_hp, boss_max))

    for line_idx, line in enumerate(boss_sprite):
        y_pos = boss['y_pos'] + line_idx
        if 0 <= y_pos < constants.layout.height:
            for i, char in enumerate(line):
                if char != ' ':
                    x_pos = boss['x_pos'] + i
                    if 0 <= x_pos < constants.layout.width:
                        fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, boss_color)


def _draw_jelly_boss(fb):
    """Render Jelly Boss to framebuffer."""
    boss = state.enemies.boss
    if boss is None:
        return

    boss_hp = boss.get('hp', 0)
    boss_max = boss.get('max_hp', boss_hp if boss_hp > 0 else 1)
    boss_state = boss.get('state', 'active')
    anim_frame = boss.get('anim_frame', 0)

    # Choose sprite based on state
    if boss_state == 'dying' or boss_state == 'dead':
        boss_sprite = JELLY_BOSS_DEAD
    else:
        boss_sprite = JELLY_BOSS_FRAMES[anim_frame % len(JELLY_BOSS_FRAMES)]

    # Color based on HP - jelly boss uses a purple-ish base color
    jelly_base_rgb = (180, 100, 220)  # Purple/jelly color
    boss_color = apply_bold(color_from_hp_to_red(jelly_base_rgb, boss_hp, boss_max))

    for line_idx, line in enumerate(boss_sprite):
        y_pos = boss['y_pos'] + line_idx
        if 0 <= y_pos < constants.layout.height:
            for i, char in enumerate(line):
                if char != ' ':
                    x_pos = boss['x_pos'] + i
                    if 0 <= x_pos < constants.layout.width:
                        fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, boss_color)

    # Render bat spawn animation if active
    bat_anim = boss.get('bat_spawn_anim')
    if bat_anim and bat_anim.get('active'):
        anim_x = bat_anim.get('x_pos', 0)
        anim_y = bat_anim.get('y_pos', 0)
        anim_char = bat_anim.get('char', 'o')
        if 0 <= anim_y < constants.layout.height and 0 <= anim_x < constants.layout.width:
            # Spawn animation uses bright color
            spawn_color = "\033[1;35m"  # Bright magenta
            # Handle multi-char like "()"
            for i, c in enumerate(anim_char):
                fb.put(GAME_X_OFFSET + anim_x + i, anim_y + HEADER_HEIGHT, c, spawn_color)


def _draw_tree_boss(fb):
    """Render Tree Boss foreground elements (branches, flowers, status indicators).

    Note: The background tree is rendered separately by draw_tree_boss_background()
    which is called BEFORE the biome background for proper layering.
    """
    boss = state.enemies.boss
    if boss is None:
        return

    # =========================================================================
    # 1. RENDER FOREGROUND BRANCHES (tangible, white bold, fades to red when damaged)
    # =========================================================================
    branches = boss.get('branches', [])

    # Branch base color (white, like tree background but bold/foreground)
    branch_base_rgb = (255, 255, 255)  # White

    for branch_idx, branch in enumerate(branches):
        if branch.get('destroyed'):
            continue  # Don't render destroyed branches

        branch_x = branch.get('x_pos', 0)
        branch_y = branch.get('y_pos', 0)
        branch_hp = branch.get('hp', 1)
        branch_max_hp = branch.get('max_hp', 1)
        sprite_idx = branch.get('sprite_idx', branch_idx % len(TREE_BOSS_BRANCHES))

        # Get branch sprite
        if sprite_idx < len(TREE_BOSS_BRANCHES):
            branch_sprite = TREE_BOSS_BRANCHES[sprite_idx]
        else:
            branch_sprite = TREE_BOSS_BRANCHES[0]

        # Color based on HP - white when full, fades to red as damaged
        branch_color = apply_bold(color_from_hp_to_red(branch_base_rgb, branch_hp, branch_max_hp))

        # Render branch sprite
        # Hide digits 1-5 (overlap markers) and 'o' (flower position markers)
        for line_idx, line in enumerate(branch_sprite):
            y_pos = branch_y + line_idx
            if 0 <= y_pos < constants.layout.height:
                for i, char in enumerate(line):
                    if char != ' ' and char not in TREE_HIDDEN_CHARS:
                        x_pos = branch_x + i
                        if 0 <= x_pos < constants.layout.width:
                            fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, branch_color)

        # =====================================================================
        # 3. RENDER FLOWER on this branch (if active)
        # =====================================================================
        flower = branch.get('flower')
        if flower and flower.get('active'):
            flower_type = flower.get('type', 'red')
            flower_frame = flower.get('frame', 0)

            # Get flower sprite lines based on growth frame (can be multi-line)
            if flower_frame < len(FLOWER_GROWTH_FRAMES):
                flower_lines = FLOWER_GROWTH_FRAMES[flower_frame]
            else:
                flower_lines = FLOWER_GROWTH_FRAMES[-1]  # Mature flower

            # Get flower color
            flower_color = FLOWER_COLORS.get(flower_type, '\033[1;37m')  # Default white

            # Get flower position from branch (stored when flower spawns)
            flower_rel_x = flower.get('rel_x', 0)
            flower_rel_y = flower.get('rel_y', 0)

            # Calculate actual position
            flower_base_x = branch_x + flower_rel_x
            flower_base_y = branch_y + flower_rel_y

            # Render each line of the flower sprite (from bottom to top for multi-line)
            for line_offset, flower_line in enumerate(reversed(flower_lines)):
                flower_y = flower_base_y - line_offset
                # Center the flower line
                line_width = len(flower_line)
                flower_x = flower_base_x - line_width // 2

                if 0 <= flower_y < constants.layout.height:
                    for char_idx, char in enumerate(flower_line):
                        x_pos = flower_x + char_idx
                        if char != ' ' and 0 <= x_pos < constants.layout.width:
                            fb.put(GAME_X_OFFSET + x_pos, flower_y + HEADER_HEIGHT, char, flower_color)

    # =========================================================================
    # 4. RENDER STATUS INDICATORS for stunned/frozen/poisoned birds
    # =========================================================================
    draw_bird_status_indicators(fb)


def _draw_owl_boss(fb):
    """Render Owl Boss and its spell effects."""
    boss = state.enemies.boss
    if boss is None:
        return

    boss_hp = boss.get('hp', 0)
    boss_max = boss.get('max_hp', boss_hp if boss_hp > 0 else 1)
    boss_state = boss.get('state', 'fly')
    anim_frame = boss.get('anim_frame', 0)

    # Choose sprite based on state
    # boss['state'] contains: 'descending', 'fly', 'conjure', 'cast', 'recharge', 'dying', 'dead'
    if boss_state in ('dying', 'dead'):
        boss_sprite = OWL_BOSS_DEAD
    elif boss_state == 'descending':
        # While descending, use fly animation
        stage_frames = OWL_BOSS_FRAMES.get('fly', OWL_BOSS_FRAMES['fly'])
        boss_sprite = stage_frames[anim_frame % len(stage_frames)]
    else:
        # Get frames for current stage (fly, conjure, cast, recharge)
        stage_frames = OWL_BOSS_FRAMES.get(boss_state, OWL_BOSS_FRAMES['fly'])
        boss_sprite = stage_frames[anim_frame % len(stage_frames)]

    # Color based on HP - uses purple base for magical owl
    owl_base_rgb = (180, 100, 220)  # Purple
    boss_color = apply_bold(color_from_hp_to_red(owl_base_rgb, boss_hp, boss_max))

    # Render owl boss sprite
    for line_idx, line in enumerate(boss_sprite):
        y_pos = boss['y_pos'] + line_idx
        if 0 <= y_pos < constants.layout.height:
            for i, char in enumerate(line):
                if char != ' ':
                    x_pos = boss['x_pos'] + i
                    if 0 <= x_pos < constants.layout.width:
                        # Special coloring for certain characters
                        char_color = boss_color
                        if char == '*':  # Magic star
                            char_color = "\033[1;33m"  # Yellow
                        elif char in ('@', 'v'):  # Eyes/beak
                            # Different eye colors based on stage
                            if boss_state == 'conjure':
                                char_color = "\033[1;31m"  # Red (narrowed)
                            elif boss_state == 'cast':
                                char_color = "\033[1;37m"  # White (star eyes)
                            elif boss_state == 'recharge':
                                char_color = "\033[1;34m"  # Blue (drowsy)
                            else:
                                char_color = "\033[1;33m"  # Yellow (normal)
                        fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, char_color)

    # Owl boss portals now use state.enemies.portals and are rendered by draw_portals()

    # Render owl meteors (2 large meteors: one left, one right)
    owl_meteors = boss.get('owl_meteors', [])
    trail_color = "\033[38;5;208m"  # Orange trail
    for meteor in owl_meteors:
        meteor_x = meteor['x_pos']
        meteor_y = meteor['y_pos']
        meteor_hp = meteor.get('hp', 1)
        meteor_max = meteor.get('max_hp', 1)
        meteor_side = meteor.get('side', 'left')

        # Choose sprite based on side
        meteor_sprite = METEOR_LEFT if meteor_side == 'left' else METEOR_RIGHT

        # Color based on meteor HP
        meteor_base_rgb = (255, 100, 0)  # Orange
        m_color = apply_bold(color_from_hp_to_red(meteor_base_rgb, meteor_hp, meteor_max))

        # Render trail above meteor (centered on meteor)
        sprite_width = max(len(line) for line in meteor_sprite)
        trail_x = meteor_x + sprite_width // 2
        for line_idx, line in enumerate(METEOR_TRAIL):
            y_pos = meteor_y - len(METEOR_TRAIL) + line_idx
            if 0 <= y_pos < constants.layout.height:
                for i, char in enumerate(line):
                    if char != ' ':
                        x_pos = trail_x + i - len(line) // 2
                        if 0 <= x_pos < constants.layout.width:
                            fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, trail_color)

        # Render meteor body
        for line_idx, line in enumerate(meteor_sprite):
            y_pos = meteor_y + line_idx
            if 0 <= y_pos < constants.layout.height:
                for i, char in enumerate(line):
                    if char != ' ':
                        x_pos = meteor_x + i
                        if 0 <= x_pos < constants.layout.width:
                            fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, m_color)

    # Render status indicators for affected birds (same as Tree Boss)
    draw_bird_status_indicators(fb)


_BOSS_RENDERERS = {
    'wind': _draw_wind_boss,
    'jelly': _draw_jelly_boss,
    'tree': _draw_tree_boss,
    'owl': _draw_owl_boss,
}
