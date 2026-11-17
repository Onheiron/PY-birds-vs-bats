"""Text pages of the Birdpedia: guide, discovered birds and bats, biomes."""

from src.core import state


def page(content_type):
    """Title and lines of a text page; undiscovered entries are hidden."""
    discovered_birds = state.discovery.birds
    discovered_bats = state.discovery.bats
    discovered_obstacles = state.discovery.obstacles

    # Bird entries with discovery check
    BIRD_ENTRIES = [
        ('YELLOW', "\x1b[93mYELLOW\x1b[0m - Bounces adjacent birds"),
        ('RED', "\x1b[91mRED\x1b[0m - Fires projectiles"),
        ('BLUE', "\x1b[94mBLUE\x1b[0m - Speed boost"),
        ('WHITE', "\x1b[97mWHITE\x1b[0m - Affects 4 lanes"),
        ('PURPLE', "\x1b[95mPURPLE\x1b[0m - Charge & launch"),
        ('ORANGE', "\x1b[38;5;208mORANGE\x1b[0m - Lays eggs, respawns"),
        ('STEALTH', "\x1b[90mSTEALTH\x1b[0m - Goes invisible"),
        ('CLOCKWORK', "\x1b[38;5;130mCLOCKWORK\x1b[0m - Wind-up speed"),
        ('GOLD', "\x1b[33mGOLD\x1b[0m - Extra points"),
        ('PATCHWORK', "\x1b[38;5;213mPATCHWORK\x1b[0m - Random powers"),
        ('COOKIE', "\x1b[38;5;215mCOOKIE\x1b[0m - Drops XP crumbs"),
        ('DINOSAUR', "\x1b[32mDINOSAUR\x1b[0m - Multi-press bounce"),
        ('GLITCH', "\x1b[38;5;51mGLITCH\x1b[0m - Unpredictable"),
    ]

    # Bat entries with discovery check
    BAT_ENTRIES = [
        ('BASIC', ["BASIC BAT", "  Standard flying enemy.", "  Scares birds on contact.", ""]),
        ('FAST', ["FAST BAT", "  Moves quickly across lanes.", "  Harder to avoid.", ""]),
        ('DIVE', ["DIVE BAT", "  Dives down at birds.", "  Very dangerous!", ""]),
        ('BOSS', ["BOSS BAT", "  Huge and powerful!", "  Requires many hits.", ""]),
    ]

    # Build dynamic bird list
    def get_bird_lines():
        lines = []
        discovered_count = 0
        for name, text in BIRD_ENTRIES:
            if name in discovered_birds:
                lines.append(text)
                discovered_count += 1
            else:
                lines.append("\x1b[90m??? - ???\x1b[0m")
        lines.append("")
        lines.append(f"Discovered: {discovered_count}/{len(BIRD_ENTRIES)}")
        return lines

    # Build dynamic bat list
    def get_bat_lines():
        lines = []
        discovered_count = 0
        for name, entry_lines in BAT_ENTRIES:
            if name in discovered_bats:
                lines.extend(entry_lines)
                discovered_count += 1
            else:
                lines.extend(["\x1b[90m??? BAT\x1b[0m", "  ???", "  ???", ""])
        lines.append(f"Discovered: {discovered_count}/{len(BAT_ENTRIES)}")
        return lines

    # Content definitions
    CONTENT = {
        'howto': {
            'title': 'HOW TO PLAY',
            'lines': [
                "Guide your birds to the finish",
                "line at the top of the screen!",
                "",
                "Birds bounce between the start",
                "and finish lines automatically.",
                "",
                "Press UP when a bird is falling",
                "to bounce it back up.",
                "",
                "Press UP when a bird is rising",
                "to activate its special power!",
                "",
                "Collect loot for score & XP.",
                "Avoid obstacles and enemies.",
                "",
                "Don't let birds fall off the",
                "bottom - you'll lose a life!",
            ],
        },
        'commands': {
            'title': 'COMMANDS',
            'lines': [
                "MOVEMENT:",
                "  LEFT/RIGHT - Move cursor",
                "  UP - Bounce / Power",
                "",
                "SELECTION:",
                "  SPACE - Start/Execute swap",
                "",
                "GAME:",
                "  P - Pause game",
                "  X - Toggle XP overlay",
                "  M - Mute/Unmute audio",
                "  Q - Quit game",
                "",
                "Controls can be rebound in",
                "the SETTINGS > CONTROLS menu.",
            ],
        },
        'obstacles': {
            'title': 'OBSTACLES',
            'lines': [
                "TREE - Blocks bird movement." if 'TREE' in discovered_obstacles else "\x1b[90m??? - ???\x1b[0m",
                "  Birds bounce off trees." if 'TREE' in discovered_obstacles else "",
                "",
                "ROCK - Stuns birds on contact." if 'ROCK' in discovered_obstacles else "\x1b[90m??? - ???\x1b[0m",
                "  Stunned birds can't bounce." if 'ROCK' in discovered_obstacles else "",
                "",
                "CLOUD - Slows bird speed." if 'CLOUD' in discovered_obstacles else "\x1b[90m??? - ???\x1b[0m",
                "  Temporary speed reduction." if 'CLOUD' in discovered_obstacles else "",
                "",
                "BARRIER - Right panel hazard." if 'BARRIER' in discovered_obstacles else "\x1b[90m??? - ???\x1b[0m",
                "  Destroys loot on contact." if 'BARRIER' in discovered_obstacles else "",
                "",
                f"Discovered: {len(discovered_obstacles)}/4",
            ],
        },
        'enemies': {
            'title': 'ENEMIES',
            'lines': [
                "BAT - Flying enemy.",
                "  Scares birds on contact!",
                "  Scared birds fall faster",
                "  and cannot be bounced.",
                "",
                "RED projectiles can destroy",
                "bats for bonus points.",
                "",
                "BLUE birds near YELLOW birds",
                "can be cured of fear when",
                "the yellow bird bounces.",
                "",
                "More enemies appear at higher",
                "speed levels.",
            ],
        },
        'birds': {'title': 'BIRD-DEX', 'lines': get_bird_lines()},
        'bats': {'title': 'BAT-DEX', 'lines': get_bat_lines()},
        'biomes': {
            'title': 'BIOMES',
            'lines': [
                "WINDY WOODS (1-1 to 1-3)",
                "  Dense conifer forest.",
                "  Gentle start, basic obstacles.",
                "",
                "THE BORDERS (2-1 to 2-3)",
                "  Open plains, deciduous trees.",
                "  More space, faster foes.",
                "",
                "ROTTEN MARSHES (3-1 to 3-3)",
                "  Swampy wetlands, reeds.",
                "  Watch for murky waters!",
                "",
                "THE DARK SWAMP (4-1 to 4-3)",
                "  Deep dark swamp, twisted trees.",
                "  Visibility reduced, danger rises.",
                "",
                "THE VOID CAVE (5-1 to 5-3)",
                "  Underground cavern, stalactites.",
                "  No light, maximum peril!",
                "",
                "MOUNTAIN RANGE (6-1 to 6-3)",
                "  High peaks, thin air.",
                "  Cloud banks obscure vision!",
            ],
        },
    }

    if content_type.startswith('achievements_'):
        return achievement_page(content_type)
    return CONTENT.get(content_type, {'title': 'UNKNOWN', 'lines': []})


# Achievements shown per page
ACHIEVEMENTS_PER_PAGE = 11


def achievement_pages():
    """Content ids of the achievement pages: run ones, then global ones."""
    from src.engine import meta

    out = []
    for kind, table in (('run', meta.run_achievements()), ('global', meta.global_achievements())):
        count = (len(table) + ACHIEVEMENTS_PER_PAGE - 1) // ACHIEVEMENTS_PER_PAGE
        out += [f'achievements_{kind}_{n}' for n in range(count)]
    return out


def achievement_page(content_type):
    """One page of achievements: ✓ for global ones already unlocked, the gold of each."""
    from src.engine import meta

    _prefix, kind, number = content_type.split('_')
    table = meta.run_achievements() if kind == 'run' else meta.global_achievements()
    entries = list(table.items())[int(number) * ACHIEVEMENTS_PER_PAGE :][:ACHIEVEMENTS_PER_PAGE]
    done = set((meta.profile() or {}).get('achievements', [])) if state.meta.profile else set()
    lines = []
    if kind == 'run':
        lines += ['Paid every run you reach them.', '']
    else:
        lines += ['Paid once, the first time.', '']
    for aid, entry in entries:
        entry = entry if isinstance(entry, dict) else vars(entry)
        mark = '✓' if aid in done else ' '
        gold = f"{entry.get('gold', 0)}g"
        lines.append(f"{mark}{gold:>5} {entry.get('desc', aid)}"[:36])
    pages = [p for p in achievement_pages() if f'_{kind}_' in p]
    title = 'RUN' if kind == 'run' else 'GLOBAL'
    return {'title': f'{title} ACHIEVEMENTS {int(number) + 1}/{len(pages)}', 'lines': lines}
