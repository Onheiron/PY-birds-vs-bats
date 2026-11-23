"""Obstacles, flowers, portals, bats, loot and projectiles."""

from src.core import constants, state
from src.engine import clock, hazards
from src.engine.progression import hp_scale
from src.entities.sprites import (
    ARMORED_BAT_FRAME_1,
    ARMORED_BAT_FRAME_2,
    BAT_ARMOR,
    BAT_FRAME_1,
    BAT_FRAME_2,
    BOSS_DEAD,
    CYAN,
    DARK_GRAY,
    DIVER_BAT_DIVE,
    DIVER_BAT_FRAME_1,
    DIVER_BAT_FRAME_2,
    DIVER_BAT_STUNNED,
    FLOWER_COLORS,
    FLOWER_GROWTH_FRAMES,
    FROSTY,
    GREEN,
    JUMPSCARE_BAT_FRAME_1,
    JUMPSCARE_BAT_FRAME_2,
    JUMPSCARE_BAT_SCARY_FACE,
    MINI_BAT_ANIM_FRAMES,
    MINI_BAT_FRAME_1,
    MINI_BAT_FRAME_2,
    OBSTACLE_SPRITE_T1,
    POISON,
    PORTAL_COLOR,
    PORTAL_FRAME_1,
    PORTAL_FRAME_2,
    PURPLE,
    RED,
    SPELLCASTER_BAT_CASTING,
    SPELLCASTER_BAT_FRAME_1,
    SPELLCASTER_BAT_FRAME_2,
    WHITE,
    WIND_BOSS_DEAD,
    YELLOW,
    get_biome_obstacles,
    get_dynamic_color,
)
from src.ui.colors import apply_bold, color_from_hp, color_from_hp_to_red, dim_ansi_color, get_biome_obstacle_color
from src.ui.layout import GAME_X_OFFSET, HEADER_HEIGHT

# Elite bats: a golden body that reddens with damage, and a diamond above them
ELITE_RGB = (255, 190, 40)
# The ears of the bat sprites (⋀⋀, or /\ under a spellcaster's star)
EAR_CHARS = {'⋀', '/', '\\'}


def draw_obstacles(fb):
    """Render obstacles to framebuffer using biome-specific sprites and colors."""

    # Get obstacle sprites for current biome (fallback)
    biome_obstacles = get_biome_obstacles(state.game.level_group)
    # Get biome base color for obstacles
    biome_base_color = get_biome_obstacle_color(state.game.level_group)

    for obs in state.enemies.obstacles:
        tier = obs.get('tier', 1)
        is_boss_corpse = obs.get('is_boss_corpse', False)
        is_wind_boss_corpse = obs.get('is_wind_boss_corpse', False)

        if is_boss_corpse:
            # Special rendering for boss corpse
            if is_wind_boss_corpse:
                sprite = WIND_BOSS_DEAD
            else:
                sprite = BOSS_DEAD
            obs_hp = obs.get('hp', 0)
            obs_max = obs.get('max_hp', obs_hp if obs_hp > 0 else 1)
            # Use red fade like the boss
            obs_color = apply_bold(color_from_hp_to_red(constants.colors.bats_base_rgb, obs_hp, obs_max))

            # Boss corpse uses exact x_pos, not centered on lane
            x_start = obs.get('x_pos', 0)
            for line_idx, line in enumerate(sprite):
                y_pos = obs['y_pos'] + line_idx
                if 0 <= y_pos < constants.layout.height:
                    for i, char in enumerate(line):
                        if char != ' ':
                            x_pos = x_start + i
                            if 0 <= x_pos < constants.layout.width:
                                fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, obs_color)
        else:
            # Normal obstacle rendering
            # Calculate color based on HP - dims biome color as obstacle takes damage
            max_hp = constants.obstacle.max_hp_by_tier.get(tier, obs.get('hp', 1))
            obs_color = apply_bold(dim_ansi_color(biome_base_color, obs.get('hp', 0), max_hp))
            if obs.get('kind') == 'stalactite':
                obs_color = apply_bold(WHITE)

            # Usa sprite salvata nell'ostacolo (variante + flip), o fallback a default bioma
            sprite = obs.get('sprite')
            if sprite is None:
                sprite = biome_obstacles.get(tier, biome_obstacles.get(1, OBSTACLE_SPRITE_T1))

            sprite_width = max(len(line) for line in sprite)

            # Posizione x centrata sulla lane
            start_lane = obs['lane']
            center_x = constants.layout.lane_positions[start_lane]
            x_offset = sprite_width // 2

            # Still emerging (hazards.emerging): only bubbles, or dim specks in the dark
            if hazards.is_emerging(obs):
                bubble = '·' if obs.get('look') == 'dark' else ('o' if state.game.frame_count // 6 % 2 else '°')
                line = sprite[-1]
                y_pos = obs['y_pos'] + len(sprite) - 1
                if 0 <= y_pos < constants.layout.height:
                    for i, char in enumerate(line):
                        if char != ' ' and i % 2 == 0:
                            fb.put(GAME_X_OFFSET + center_x - x_offset + i, y_pos + HEADER_HEIGHT, bubble, DARK_GRAY)
                continue

            for line_idx, line in enumerate(sprite):
                y_pos = obs['y_pos'] + line_idx
                if 0 <= y_pos < constants.layout.height:
                    for i, char in enumerate(line):
                        if char != ' ':  # Solo caratteri non-spazio
                            x_pos = center_x - x_offset + i
                            if 0 <= x_pos < constants.layout.width:
                                fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, obs_color)

            # Render flower if present
            flower = obs.get('flower')
            if flower and flower.get('active'):
                _draw_obstacle_flower(fb, obs, flower, center_x, x_offset)


def _draw_obstacle_flower(fb, obs, flower, center_x, x_offset):
    """Render a flower on a swamp obstacle using the same FLOWER_GROWTH_FRAMES as Tree Boss."""

    frame = flower.get('frame', 0)
    flower_type = flower.get('type', 'red')
    rel_x = flower.get('rel_x', 0)
    rel_y = flower.get('rel_y', 0)

    # Calculate absolute position (base position)
    flower_base_x = center_x - x_offset + rel_x
    flower_base_y = obs['y_pos'] + rel_y

    # Get flower sprite lines based on growth frame (can be multi-line like Tree Boss)
    if frame < len(FLOWER_GROWTH_FRAMES):
        flower_lines = FLOWER_GROWTH_FRAMES[frame]
    else:
        flower_lines = FLOWER_GROWTH_FRAMES[-1]  # Mature flower

    # Get flower color
    flower_color = FLOWER_COLORS.get(flower_type, FLOWER_COLORS['red'])

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


def draw_portals(fb):
    """Render portals to framebuffer (biome 5 natural portals OR Owl Boss bend_space portals)."""
    # Render if we're in biome 5 OR if there are any portals (from Owl Boss)
    if state.game.level_group != 5 and not state.enemies.portals:
        return

    for portal in state.enemies.portals:
        px = portal['x_pos']
        py = portal['y_pos']
        portal_idx = portal['portal_idx']

        # Animate between frames
        frame_toggle = (state.game.frame_count // 6) % 2
        if portal_idx == 0:
            sprite = PORTAL_FRAME_1 if frame_toggle == 0 else PORTAL_FRAME_2
        else:
            sprite = PORTAL_FRAME_2 if frame_toggle == 0 else PORTAL_FRAME_1

        for line_idx, line in enumerate(sprite):
            y_pos = py + line_idx
            if 0 <= y_pos < constants.layout.height:
                for i, char in enumerate(line):
                    if char != ' ':
                        x_pos = px + i
                        if 0 <= x_pos < constants.layout.width:
                            fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, PORTAL_COLOR)


# Colour of a shot that carries a neighbour's affliction
SHOT_COLORS = {FROSTY: 'CYAN', POISON: 'GREEN'}

# Badge of the special bat kinds (src/engine/logic/bat_abilities.py)
KIND_BADGES = {
    'healer': ('+', GREEN),
    'bomber': ('o', YELLOW),
    'plague': ('¤', GREEN),
    'necromancer': ('†', PURPLE),
}


def draw_bats(fb):
    """Render bats to framebuffer."""

    for bat in state.enemies.bats:
        bat_hp = bat.get('hp', 0)
        bat_max = bat.get('max_hp', bat_hp if bat_hp > 0 else 1)
        is_armored = bat.get('armored', False)
        is_diver = bat.get('diver', False)
        is_spellcaster = bat.get('spellcaster', False)
        diver_state = bat.get('diver_state', 'flying')
        spell_state = bat.get('spell_state', 'idle')

        # Apply bold modifier for foreground game elements
        bat_color = apply_bold(color_from_hp(constants.colors.bats_base_rgb, bat_hp, bat_max))
        # Elites look like the others, with yellow ears
        is_elite = bat.get('elite', False)
        ear_color = apply_bold(color_from_hp(ELITE_RGB, bat_hp, bat_max)) if is_elite else bat_color
        ear_line = 1 if is_spellcaster else 0

        # Choose sprite based on bat type and state
        if is_spellcaster:
            # Spellcaster bat sprites based on casting state
            if spell_state == 'casting':
                bat_sprite = SPELLCASTER_BAT_CASTING
            else:
                bat_sprite = (
                    SPELLCASTER_BAT_FRAME_1 if (state.game.frame_count // 3) % 2 == 0 else SPELLCASTER_BAT_FRAME_2
                )
        elif is_armored:
            bat_sprite = ARMORED_BAT_FRAME_1 if (state.game.frame_count // 4) % 2 == 0 else ARMORED_BAT_FRAME_2
        elif is_diver:
            # Diver bat sprites based on state
            if diver_state == 'diving':
                bat_sprite = DIVER_BAT_DIVE
            elif diver_state in ('stunned', 'returning'):
                bat_sprite = DIVER_BAT_STUNNED
            else:  # flying
                bat_sprite = DIVER_BAT_FRAME_1 if (state.game.frame_count // 3) % 2 == 0 else DIVER_BAT_FRAME_2
        else:
            bat_sprite = BAT_FRAME_1 if (state.game.frame_count // 3) % 2 == 0 else BAT_FRAME_2

        for line_idx, line in enumerate(bat_sprite):
            y_pos = bat['y_pos'] + line_idx
            if 0 <= y_pos < constants.layout.height:
                for i, char in enumerate(line):
                    if char != ' ':  # Solo caratteri non-spazio
                        char_color = bat_color
                        ear = char in EAR_CHARS and (not is_spellcaster or i in (3, 4))  # not a caster's wings
                        if is_elite and line_idx == ear_line and ear:
                            char_color = ear_color
                        # Spellcaster star is colored differently when casting
                        if is_spellcaster and char == '*':
                            if spell_state == 'casting':
                                char_color = PURPLE  # Magic star glows purple when casting
                            else:
                                char_color = YELLOW  # Normal star is yellow
                        # For armored bats, color the outer parentheses with armor color
                        elif is_armored and line_idx == 1:  # Bottom line has the armor ()
                            if char == '(' or char == ')':
                                line_before = line[:i]
                                open_count = line_before.count('(')
                                line_before.count(')')
                                if (char == '(' and open_count == 0) or (
                                    char == ')' and i == len(line) - line[::-1].index(')') - 1
                                ):
                                    char_color = BAT_ARMOR
                        fb.put(GAME_X_OFFSET + bat['x_pos'] + i, y_pos + HEADER_HEIGHT, char, char_color)

        # An elite spellcaster charging two spells shows two stars
        if is_spellcaster and spell_state == 'casting' and len(bat.get('current_spells') or ()) == 2:
            star = bat_sprite[0].find('*')
            if star >= 0 and 0 <= bat['y_pos'] < constants.layout.height:
                fb.put(GAME_X_OFFSET + bat['x_pos'] + star + 1, bat['y_pos'] + HEADER_HEIGHT, '*', PURPLE)

        # New kinds: a badge in the middle of the bat (healer flashes while healing)
        badge = KIND_BADGES.get(bat.get('kind'))
        if badge and 0 <= bat['y_pos'] < constants.layout.height:
            char, color = badge
            if bat.get('kind') == 'healer' and clock.now() < bat.get('healing_until', 0):
                char = '✚'
            fb.put(GAME_X_OFFSET + bat['x_pos'] + 4, bat['y_pos'] + HEADER_HEIGHT, char, apply_bold(color))

        # Render debuff indicators above bat (using flower-like symbols)
        bat_id = id(bat)
        indicator_y = bat['y_pos'] - 1
        if 0 <= indicator_y < constants.layout.height:
            indicator_x = bat['x_pos'] + 3  # Center above bat
            indicators = []
            # Healed above its max HP (elite healers)
            if bat.get('hp', 0) > bat.get('max_hp', bat.get('hp', 0)):
                indicators.append(('+', GREEN))
            # FROZEN: snowflake (cyan) - ❄ or *
            if bat_id in state.special.frozen_enemies:
                indicators.append(('*', CYAN))
            # POISONED: skull (green) - ☠ or %
            if bat_id in state.special.poisoned_enemies:
                indicators.append(('%', GREEN))
            # BLEEDING: drop (red) - 💧 or ~
            if bat_id in state.special.bleeding_enemies:
                indicators.append(('~', RED))
            # Render indicators side by side
            for idx, (symbol, color) in enumerate(indicators):
                fb.put(GAME_X_OFFSET + indicator_x + idx, indicator_y + HEADER_HEIGHT, symbol, apply_bold(color))


def draw_mini_bats(fb):
    """Render mini bats to framebuffer."""

    for mb in state.enemies.mini_bats:
        mb_hp = mb.get('hp', 0)
        mb_max = mb.get('max_hp', mb_hp if mb_hp > 0 else 1)
        # Use bat color but slightly different hue (more purple/pink)
        mb_color = apply_bold(color_from_hp((200, 50, 255), mb_hp, mb_max))

        mb_state = mb.get('state', 'active')
        anim_frame = mb.get('anim_frame', 0)
        is_jumpscare = mb.get('is_jumpscare', False)

        # Determine what to render based on state
        if mb_state == 'spawning':
            # Spawn animation: · → • → ⛌ → 〇
            if anim_frame < len(MINI_BAT_ANIM_FRAMES):
                char = MINI_BAT_ANIM_FRAMES[anim_frame]
                y_pos = mb['y_pos']
                if 0 <= y_pos < constants.layout.height:
                    fb.put(GAME_X_OFFSET + mb['x_pos'], y_pos + HEADER_HEIGHT, char, mb_color)

        elif mb_state == 'hiding':
            # Hide animation: reverse of spawn (〇 → ⛌ → • → ·)
            if 0 <= anim_frame < len(MINI_BAT_ANIM_FRAMES):
                char = MINI_BAT_ANIM_FRAMES[anim_frame]
                y_pos = mb['y_pos']
                if 0 <= y_pos < constants.layout.height:
                    fb.put(GAME_X_OFFSET + mb['x_pos'], y_pos + HEADER_HEIGHT, char, mb_color)

        else:  # 'active'
            y_pos = mb['y_pos']

            # Jumpscare bat with scary face active
            if is_jumpscare and mb.get('scary_face_timer', 0) > 0:
                # Render scary face sprite (3 lines tall)
                for line_offset, line in enumerate(JUMPSCARE_BAT_SCARY_FACE):
                    render_y = y_pos - 1 + line_offset
                    if 0 <= render_y < constants.layout.height:
                        sprite_width = len(line)
                        start_x = mb['x_pos'] - sprite_width // 2
                        for i, char in enumerate(line):
                            x = start_x + i
                            if 0 <= x < constants.layout.width:
                                fb.put(GAME_X_OFFSET + x, render_y + HEADER_HEIGHT, char, mb_color)
            elif is_jumpscare:
                # Jumpscare bat uses multi-line Diver Bat sprite
                sprite = JUMPSCARE_BAT_FRAME_1 if (state.game.frame_count // 4) % 2 == 0 else JUMPSCARE_BAT_FRAME_2
                for line_offset, line in enumerate(sprite):
                    render_y = y_pos + line_offset
                    if 0 <= render_y < constants.layout.height:
                        sprite_width = len(line)
                        start_x = mb['x_pos'] - sprite_width // 2
                        for i, char in enumerate(line):
                            x = start_x + i
                            if 0 <= x < constants.layout.width:
                                fb.put(GAME_X_OFFSET + x, render_y + HEADER_HEIGHT, char, mb_color)
            else:
                # Normal mini bat - single line sprite
                sprite = MINI_BAT_FRAME_1 if (state.game.frame_count // 4) % 2 == 0 else MINI_BAT_FRAME_2
                if 0 <= y_pos < constants.layout.height:
                    sprite_width = len(sprite)
                    start_x = mb['x_pos'] - sprite_width // 2
                    for i, char in enumerate(sprite):
                        x = start_x + i
                        if 0 <= x < constants.layout.width:
                            fb.put(GAME_X_OFFSET + x, y_pos + HEADER_HEIGHT, char, mb_color)


def draw_loot(fb):
    """Render loot items to framebuffer."""
    # Use dynamic colors for accessibility support
    loot_symbols = {
        'yellow_egg': ('⬯', 'YELLOW'),
        'red_egg': ('⬯', 'RED'),
        'blue_egg': ('⬯', 'BLUE'),
        'white_egg': ('⬯', 'WHITE'),
        'clockwork_egg': ('⬯', 'CLOCKWORK'),
        'gold_egg': ('⬯', 'GOLD'),
        'stealth_egg': ('⬯', 'DARK_GRAY'),
        'patchwork_egg': ('⬯', 'PATCHWORK'),
        'orange_egg': ('⬯', 'ORANGE'),
        'cookie_egg': ('⬯', 'COOKIE'),
        'cookie_crumb': ('•', 'COOKIE'),
        'firefly': ('✦', 'YELLOW'),
        'dinosaur_egg': ('⬯', 'DINOSAUR'),
        'glitch_egg': ('⬯', 'GLITCH'),
        'purple_egg': ('⬯', 'PURPLE'),
    }

    for loot in state.items.loot_items:
        y_pos = loot['y_pos']
        if 0 <= y_pos < constants.layout.height:
            loot_type = loot['type']
            rarity = loot.get('rarity', 'common')

            # Colore basato su rarity (use dynamic colors)
            if rarity == 'common':
                power_color = get_dynamic_color('YELLOW')
            elif rarity == 'uncommon':
                power_color = get_dynamic_color('RED')
            elif rarity == 'rare':
                power_color = get_dynamic_color('BLUE')
            else:
                power_color = get_dynamic_color('WHITE')

            if loot_type == 'egg':
                # Rarity eggs: grey, green, blue, purple, yellow, white
                from src.ui.layers.choice import RARITY_COLORS

                # Hollow and filled in turn, so a dropped egg catches the eye
                char = '⬯' if (state.game.frame_count // 4) % 2 == 0 else '⬮'
                color = RARITY_COLORS.get(rarity, power_color)
            elif loot_type in loot_symbols:
                char, color_name = loot_symbols[loot_type]
                color = get_dynamic_color(color_name)
            elif 'wide_cursor' in loot_type:
                char = '↔'
                color = power_color
            elif 'tailwind' in loot_type:
                char = '༄'  # Originale
                color = power_color
            elif 'timelapse' in loot_type:
                char = '◴'  # Clock/time symbol
                color = power_color
            else:
                char = '?'
                color = WHITE

            fb.put(GAME_X_OFFSET + loot['x_pos'], y_pos + HEADER_HEIGHT, char, color)
            # A Phoenix's egg: the seconds left to wake it, under it
            if loot_type == 'orange_egg' and y_pos + 1 < constants.layout.height:
                age = clock.now() - loot.get('spawn_ts', clock.now())
                left = getattr(constants.loot, 'loot_despawn_time', 30) - age
                text = str(max(0, int(left + 0.999)))
                x = loot['x_pos'] - len(text) // 2
                fb.put_string(GAME_X_OFFSET + x, y_pos + 1 + HEADER_HEIGHT, text, color)


def draw_projectiles(fb):
    """Render projectiles to framebuffer."""
    for proj in state.special.red_projectiles:
        y_pos = proj['y_pos']
        if 0 <= y_pos < constants.layout.height:
            damage = proj.get('damage', 1)
            if damage >= 64 * hp_scale():
                symbol = '●'  # Max Purple charge
            elif proj.get('powered'):
                symbol = '•'  # Powered
            else:
                symbol = '⋅'  # Basic
            proj_color = proj.get('color', RED)
            # Shots carrying a Frosty's freeze or a Poison's venom (synergy) take their colour
            for j in proj.get('afflict', ()):
                carried = state.birds.colors[j] if 0 <= j < len(state.birds.colors) else None
                if carried in SHOT_COLORS:
                    proj_color = get_dynamic_color(SHOT_COLORS[carried])
                    break
            fb.put(GAME_X_OFFSET + proj['x_pos'], y_pos + HEADER_HEIGHT, symbol, proj_color)
