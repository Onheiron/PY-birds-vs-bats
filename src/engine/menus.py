"""Menus: one declarative tree shared by the title screen and the pause menu.

Every screen is a ``Screen`` holding a list of ``Item``s. An item says what it
shows (a name, optionally a value) and what it does: open a submenu, go back,
run an action on ENTER, change a value with LEFT/RIGHT, or rebind a control.
The same tree drives both input (``handle_key``) and drawing
(``src.ui.layers.menus``), so adding an option is a single entry here.

Navigation is a stack kept in ``state.ui.menu_stack``: a list of
``[screen_id, cursor]`` pairs whose first entry is the root, ``'title'`` or
``'pause'``. Going back pops the stack, so the cursor comes back to the item
that opened the submenu.

The two roots share every submenu. They differ only where the context does:
settings changed on the title screen are saved as defaults straight away,
while in the pause menu they apply to the running game.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from src.core import constants, state
from src.engine.actions import handle_pause
from src.engine.notifications import notify
from src.services import save_manager
from src.services.sound import apply_music_setting

TITLE = 'title'
PAUSE = 'pause'

DIFFICULTY_NAMES = ('PEACEFUL', 'ADVENTURE', 'SURVIVAL', 'LEGENDARY')

# Controls that can be rebound, in the order the CONTROLS screen lists them
REBINDABLE_CONTROLS = (
    ('MOVE LEFT', 'MOVE_LEFT'),
    ('MOVE RIGHT', 'MOVE_RIGHT'),
    ('BOUNCE', 'BOUNCE'),
    ('SWAP', 'SWAP'),
)
_NAMED_KEYS = ('LEFT', 'RIGHT', 'UP', 'DOWN', 'SPACE', 'ENTER')
_KEY_SYMBOLS = {'LEFT': '←', 'RIGHT': '→', 'UP': '↑', 'DOWN': '↓', 'SPACE': 'SPC'}


@dataclass(frozen=True)
class Item:
    """One line of a menu.

    kind tells the view how to lay it out:
      'plain'   just the name
      'option'  name followed by "< value >" (toggles, cyclers)
      'binding' name followed by the key bound to a control
      'slot'    a save slot: name followed by its level and date, or "(empty)"
    """

    name: str
    kind: str = 'plain'
    value: Callable[[], object] | None = None
    opens: str | None = None  # submenu opened by ENTER
    back: bool = False  # ENTER goes back
    on_enter: Callable[[], None] | None = None
    on_change: Callable[[int], None] | None = None  # LEFT/RIGHT, delta -1/+1
    rebind: str | None = None  # control rebound by ENTER


@dataclass(frozen=True)
class Screen:
    """A menu screen. ``content`` names a text page instead of a list of items."""

    id: str
    title: str
    items: Callable[[], list] = field(default=list)
    hint: str = 'change'  # 'change', 'select' or 'controls'
    content: str | None = None


# =============================================================================
# CONTEXT
# =============================================================================


def root():
    """'title' or 'pause': which root the menu currently hangs from."""
    stack = state.ui.menu_stack
    return stack[0][0] if stack else None


def _settings_changed():
    """A setting changed: on the title screen it becomes the saved default."""
    if root() == TITLE:
        save_manager.save_default_settings()


# =============================================================================
# ACTIONS
# =============================================================================


def _quit():
    state.game.quit_requested = True
    state.game.game_over = True


def _toggle(name, after=None):
    def change(_delta=0):
        setattr(state.settings, name, not getattr(state.settings, name))
        if after:
            after()
        _settings_changed()

    return change


def _toggle_music_live():
    # Starting or stopping the music only makes sense during a game
    if root() == PAUSE:
        apply_music_setting()


def _accessibility_changed():
    if state.settings.accessibility_enabled:
        # High-contrast mode: drop the scenery behind the playfield
        state.settings.background_enabled = False
        state.settings.parallax_enabled = False


def _cycle_difficulty(delta=1):
    if not state.ui.show_title:
        notify('A game keeps the difficulty it started with', title='Difficulty:')
        return
    state.settings.difficulty = (state.settings.difficulty + delta) % len(DIFFICULTY_NAMES)
    _settings_changed()


def _difficulty_name():
    from src.engine import meta

    name = DIFFICULTY_NAMES[state.settings.difficulty]
    return name if meta.difficulty_unlocked(name) else f'{name} ✗'


def _start_game(difficulty):
    """Fresh game state; the selected difficulty survives the reset."""
    state.init()
    save_manager.load_default_settings()
    state.settings.difficulty = difficulty
    state.ui.show_title = False


def _continue():
    """Load the most recent save, or start a new game when there is none."""
    most_recent = save_manager.get_most_recent_save()
    if most_recent is not None and save_manager.load_game(most_recent):
        state.ui.show_title = False
        return
    state.init()
    save_manager.load_default_settings()
    state.ui.show_title = False


def _new_game():
    from src.engine import meta

    selected = state.settings.difficulty
    name = DIFFICULTY_NAMES[selected]
    if not meta.difficulty_unlocked(name):
        notify(meta.unlock_goal(name), title=f'{name} is locked:')
        return
    constants.reload_for_difficulty(selected)
    _start_game(selected)


def _change_new_game_difficulty(delta):
    # Picking the difficulty for one game is not a settings change
    state.settings.difficulty = (state.settings.difficulty + delta) % len(DIFFICULTY_NAMES)


def _restart():
    state.init()
    state.game.paused = False
    state.ui.menu_stack = []
    notify("New game!", title="Restart:")


def _main_menu():
    state.game.paused = False
    state.ui.show_title = True
    state.ui.menu_stack = [[TITLE, 0]]
    state.game.game_over = True  # ends the session loop: back to the title screen


def _slot_info(slot):
    """(level text, date text) of a save slot, or None when it is empty."""
    info = save_manager.list_save_slots().get(slot, {})
    if not info.get('exists'):
        return None
    timestamp = info.get('timestamp', '')
    date = save_manager.format_timestamp_display(timestamp) if timestamp else '???'
    return info.get('level_display', '?'), date


def _save_to(slot):
    def save():
        if save_manager.save_game(slot):
            notify(f"Saved to Slot {slot}", title="Save:")
            close_submenus()
        else:
            notify("Save failed!", title="Error:")

    return save


def _load_from(slot):
    def load():
        if root() == TITLE:
            if save_manager.load_game(slot):
                state.ui.show_title = False
                close_submenus()
            return
        if _slot_info(slot) is None:
            notify("Slot is empty!", title="Error:")
        elif save_manager.load_game(slot):
            notify(f"Loaded {'Autosave' if slot == 0 else f'Slot {slot}'}", title="Load:")
            state.ui.menu_stack = [[PAUSE, 0]]
            state.game.paused = False
        else:
            notify("Load failed!", title="Error:")

    return load


def binding_display(control):
    """Text shown for a control's key (blinks while it is being rebound)."""
    if state.ui.rebinding_control == control:
        return "___" if (state.game.frame_count // 5) % 2 == 0 else "   "
    key = state.settings.key_bindings.get(control, '?')
    return _KEY_SYMBOLS.get(key, key)


def _rebind(key):
    """Assign ``key`` to the control waiting for one (ESC cancels)."""
    if key == 'ESC':
        state.ui.rebinding_control = None
        return
    if key in _NAMED_KEYS or (len(key) == 1 and key.isascii() and key.isalnum()):
        state.settings.key_bindings[state.ui.rebinding_control] = key.upper() if len(key) == 1 else key
        state.ui.rebinding_control = None
        _settings_changed()


# =============================================================================
# THE MENU TREE
# =============================================================================


def _back_item():
    return Item('< BACK', back=True)


def _update_items():
    """UPDATE / RESTART in the title menu, when a newer release of this build exists."""
    from src.services import updater

    updater.check_in_background()
    label = updater.menu_label()
    if label is None:
        return []
    name, value = label
    return [Item(name, 'option' if value else 'plain', (lambda v=value: v) if value else None, on_enter=updater.choose)]


_picked_lane = {'lane': None}  # FORMATION: the lane picked up, waiting for a second ENTER to swap


def _formation_list():
    """The bird of each lane: the player's, or the default flock in its usual order."""
    from src.engine import meta

    return meta.formation() or meta.default_flock()


def _save_formation(birds):
    from src.engine import meta

    meta.profile()['formation'] = list(birds)
    save_manager.save_profile(meta.profile())


def _lane_enter(lane):
    """ENTER on a lane: pick it up, or swap it with the lane picked up before."""
    picked = _picked_lane['lane']
    if picked is None:
        _picked_lane['lane'] = lane
        return
    _picked_lane['lane'] = None
    if picked != lane:
        birds = _formation_list()
        birds[picked], birds[lane] = birds[lane], birds[picked]
        _save_formation(birds)


def _lane_change(lane, delta):
    """LEFT / RIGHT on a lane: another bird there (only with the Formation upgrade)."""
    from src.engine import meta

    if not meta.formation_unlocked():
        notify('Choose which birds with the FORMATION upgrade', title='Formation')
        return
    birds = _formation_list()
    options = meta.formation_choices()
    current = options.index(birds[lane]) if birds[lane] in options else 0
    birds[lane] = options[(current + delta) % len(options)]
    _save_formation(birds)


def _random_lanes():
    from src.engine import meta

    _picked_lane['lane'] = None
    meta.profile().pop('formation', None)
    save_manager.save_profile(meta.profile())


def _lane_value(lane, bird):
    from src.engine import meta

    mark = '◆ ' if _picked_lane['lane'] == lane else ''
    return f"{mark}{str(bird).title()}{' ↔' if meta.formation_unlocked() else ''}"


def _formation_items():
    from src.engine import meta

    birds = _formation_list()
    items = [
        Item(
            f'LANE {lane + 1}',
            'option',
            (lambda n=lane, b=bird: _lane_value(n, b)),
            on_enter=(lambda n=lane: _lane_enter(n)),
            on_change=(lambda delta, n=lane: _lane_change(n, delta)),
        )
        for lane, bird in enumerate(birds)
    ]
    status = 'OFF' if meta.formation() else 'ON'
    return [*items, Item('RANDOM LANES', 'option', lambda: status, on_enter=_random_lanes), _back_item()]


def _flock_meta_items():
    """TITLE > FLOCK: the starting flock, the upgrades, the feathers, the birds."""
    return [
        Item('FORMATION', opens='formation'),
        Item('UPGRADES', value=_gold_text, opens='upgrades'),
        Item('FEATHERS', opens='page_feathers'),
        Item('BIRDS', opens='page_flock_birds'),
        _back_item(),
    ]


def _leaderboard_items():
    from src.services import online

    return [
        *[Item(online.PERIOD_NAMES[p], opens=f'leaderboard_{p}') for p in online.PERIODS],
        Item('DIFFICULTY', 'option', _difficulty_name, on_change=_change_new_game_difficulty),
        _back_item(),
    ]


def _title_items():
    return [
        *_update_items(),
        *([Item('CONTINUE', on_enter=_continue)] if save_manager.get_save_path(0).exists() else []),
        Item('NEW GAME', value=_difficulty_name, on_enter=_new_game, on_change=_change_new_game_difficulty),
        Item('LOAD', opens='load'),
        Item('FLOCK', value=_gold_text, opens='flock_meta'),
        Item('ACHIEVEMENTS', opens='achievements'),
        Item('LEADERBOARDS', opens='leaderboards'),
        Item('BIRDPEDIA', opens='birdpedia'),
        Item('SETTINGS', opens='settings'),
        Item('QUIT', on_enter=_quit),
    ]


def _pause_items():
    return [
        Item('RESUME', on_enter=handle_pause),
        Item('RESTART', on_enter=_restart),
        Item('SAVE', opens='save'),
        Item('LOAD', opens='load'),
        Item('BIRDPEDIA', opens='birdpedia'),
        Item('SETTINGS', opens='settings'),
        Item('FLOCK', opens='flock'),
        Item('MAIN MENU', on_enter=_main_menu),
    ]


def _settings_items():
    return [
        Item('SOUND', opens='sound'),
        Item('GRAPHICS', opens='graphics'),
        Item('CONTROLS', opens='controls'),
        Item('DIFFICULTY', 'option', _difficulty_name, on_enter=_cycle_difficulty, on_change=_cycle_difficulty),
        _option('ONLINE', 'online_enabled'),
        _option('TUTORIAL', 'tutorial', _tutorial_toggled),
        *([Item('WIPE SAVE', opens='wipe')] if state.ui.show_title else []),  # not during a game
        _back_item(),
    ]


def _tutorial_toggled():
    """TUTORIAL on again: every tip once more."""
    if state.settings.tutorial:
        from src.engine import tutorial

        if state.meta.profile is None:
            state.meta.profile = save_manager.load_profile()
        tutorial.reset()
        save_manager.save_profile(state.meta.profile)


def _wipe_items():
    return [
        Item('NO, KEEP EVERYTHING', back=True),  # where the cursor starts
        Item('YES, START OVER', on_enter=_wipe),
        _back_item(),
    ]


def _wipe():
    backup = save_manager.wipe_progress()
    state.ui.menu_stack = [[TITLE, 0]]
    notify(
        'Feathers, upgrades, achievements, saves and Birdpedia start over' if backup else 'Nothing to wipe',
        title='Wipe save:',
    )


def _option(name, setting, after=None):
    toggle = _toggle(setting, after)
    return Item(
        name,
        'option',
        lambda: 'ON' if getattr(state.settings, setting) else 'OFF',
        on_enter=toggle,
        on_change=toggle,
    )


def _sound_items():
    return [
        _option('SFX', 'sfx_enabled'),
        _option('MUSIC', 'music_enabled', _toggle_music_live),
        _back_item(),
    ]


def _graphics_items():
    return [
        _option('BACKGROUND', 'background_enabled'),
        _option('PARALLAX', 'parallax_enabled'),
        _option('ACCESSIBILITY', 'accessibility_enabled', _accessibility_changed),
        _back_item(),
    ]


def _controls_profile_name():
    from src.ui import controls

    return controls.profile_name()


def _cycle_controls(delta=1):
    from src.ui import controls

    controls.cycle_profile(delta)
    _settings_changed()


def _power_button_name():
    """Which button fires a rising bird's power."""
    return 'X / DOWN' if state.settings.power_button else 'A / UP'


def _toggle_power_button(_delta=1):
    state.settings.power_button = not state.settings.power_button
    _settings_changed()


def _controls_items():
    items = [
        Item(name, 'binding', (lambda control=control: binding_display(control)), rebind=control)
        for name, control in REBINDABLE_CONTROLS
    ]
    assists = [
        _option('BOUNCE ON ENTER', 'bounce_on_enter'),
        _option('TRIGGER ON ENTER', 'trigger_on_enter'),
        Item(
            'POWER BUTTON', 'option', _power_button_name, on_enter=_toggle_power_button, on_change=_toggle_power_button
        ),
        Item('BUTTON LABELS', 'option', _controls_profile_name, on_enter=_cycle_controls, on_change=_cycle_controls),
    ]
    return items + assists + [_back_item()]


def _save_items():
    slots = [
        Item(f'SLOT {slot}', 'slot', (lambda s=slot: _slot_info(s)), on_enter=_save_to(slot)) for slot in (1, 2, 3)
    ]
    return slots + [_back_item()]


def _load_items():
    slots = [
        Item('AUTO' if slot == 0 else f'SLOT {slot}', 'slot', (lambda s=slot: _slot_info(s)), on_enter=_load_from(slot))
        for slot in (0, 1, 2, 3)
    ]
    return slots + [_back_item()]


def _flock_items():
    """The FLOCK screen: a line per bird (its stat sheet) and the flock's stats."""
    from src.ui import flock_pages

    birds = [Item(flock_pages.bird_label(i), opens=f'flock_bird_{i}') for i in flock_pages.bird_slots()]
    return birds + [Item('FLOCK STATS', opens='flock_stats'), _back_item()]


def _birdpedia_items():
    return [
        Item('GUIDE', opens='guide'),
        Item('BIRD-DEX', opens='birdpedia_list'),
        Item('BAT-DEX', opens='batpedia_list'),
        Item('BIOMES', opens='biomes_list'),
        _back_item(),
    ]


def _guide_items():
    return [
        Item('HOW TO PLAY', opens='guide_howto'),
        Item('COMMANDS', opens='guide_commands'),
        Item('OBSTACLES', opens='guide_obstacles'),
        Item('ENEMIES', opens='guide_enemies'),
        _back_item(),
    ]


# =============================================================================
# META PROGRESSION: upgrades and achievements
# =============================================================================


def _profile():
    from src.engine import meta

    if state.meta.profile is None:
        state.meta.profile = save_manager.load_profile()
    return meta


def _gold_text():
    meta = _profile()
    return f"{meta.profile().get('gold', 0)} ❖"


def _branches():
    meta = _profile()
    out = []
    for entry in meta.upgrades().values():
        branch = (entry if isinstance(entry, dict) else vars(entry)).get('branch', 'Other')
        if branch not in out:
            out.append(branch)
    return out


def _upgrade_ids(branch):
    meta = _profile()
    return [
        uid for uid, e in meta.upgrades().items() if (e if isinstance(e, dict) else vars(e)).get('branch') == branch
    ]


def _upgrade_value(uid):
    meta = _profile()
    entry = meta.upgrades()[uid]
    entry = entry if isinstance(entry, dict) else vars(entry)
    top = len(entry.get('costs', []))
    level = meta.level_of(uid)
    if level >= top:
        return f'{level}/{top}  MAX'
    if meta.missing_requirements(uid):
        return f'{level}/{top}  ✗'
    return f'{level}/{top}  {meta.cost(uid)}❖'


def _buy(uid):
    def buy():
        meta = _profile()
        entry = meta.upgrades()[uid]
        name = (entry if isinstance(entry, dict) else vars(entry)).get('name', uid)
        if meta.buy(uid):
            notify(f'{name} {meta.level_of(uid)}: {meta.describe_upgrade(uid, meta.level_of(uid))}', title='Upgrade!')
            return
        missing = meta.missing_requirements(uid)
        if missing:
            needs = ', '.join(f'{_upgrade_name(m)} {lvl}' for m, lvl in missing.items())
            notify(f'Needs {needs}', title='Locked')
        elif meta.cost(uid) is None:
            notify(f'{name} is at its maximum', title='Upgrade')
        else:
            notify(f'{name} costs {meta.cost(uid)} feathers ❖', title='Not enough feathers')

    return buy


def _upgrade_name(uid):
    meta = _profile()
    entry = meta.upgrades().get(uid, {})
    return (entry if isinstance(entry, dict) else vars(entry)).get('name', uid)


def upgrade_hint(screen_id, cursor):
    """The line under an upgrade screen: what the selected upgrade does next."""
    meta = _profile()
    SCREENS[screen_id].items()  # fills _UPGRADE_OF for this screen
    uid = _UPGRADE_OF.get((screen_id, cursor))
    if uid is None:
        from src.ui import controls

        return controls.hint(f"Feathers: {meta.profile().get('gold', 0)} ❖   {{select}} Buy  {{back}} Back")
    entry = meta.upgrades()[uid]
    desc = (entry if isinstance(entry, dict) else vars(entry)).get('desc', '')
    missing = meta.missing_requirements(uid)
    if missing:
        return 'Needs ' + ', '.join(f'{_upgrade_name(m)} {lvl}' for m, lvl in missing.items())
    nxt = meta.describe_upgrade(uid) if meta.cost(uid) is not None else 'maximum reached'
    return f'{desc}: {nxt}'


_UPGRADE_OF = {}


def _branch_items(branch):
    def items():
        out = []
        for n, uid in enumerate(_upgrade_ids(branch)):
            _UPGRADE_OF[(f'upgrades_{branch}', n)] = uid
            out.append(
                Item(_upgrade_name(uid).upper(), 'option', (lambda u=uid: _upgrade_value(u)), on_enter=_buy(uid))
            )
        return out + [_back_item()]

    return items


def _upgrades_items():
    meta = _profile()
    items = []
    for branch in _branches():
        ids = _upgrade_ids(branch)
        owned = sum(meta.level_of(u) for u in ids)
        top = sum(
            len(
                (meta.upgrades()[u] if isinstance(meta.upgrades()[u], dict) else vars(meta.upgrades()[u])).get(
                    'costs', []
                )
            )
            for u in ids
        )
        items.append(Item(branch.upper(), 'option', (lambda o=owned, t=top: f'{o}/{t}'), opens=f'upgrades_{branch}'))
    return items + [_back_item()]


def _achievements_items():
    from src.ui.pages import achievement_page_label, achievement_pages

    items = []
    for content in achievement_pages():
        label, count = achievement_page_label(content)
        items.append(Item(label, 'option', (lambda c=count: c), opens=f'page_{content}'))
    return items + [_back_item()]


def _page(screen_id, content):
    return Screen(screen_id, '', lambda: [_back_item()], content=content)


SCREENS = {
    screen.id: screen
    for screen in (
        Screen(TITLE, '', _title_items),
        Screen(PAUSE, 'PAUSED', _pause_items),
        Screen('settings', 'SETTINGS', _settings_items),
        Screen('sound', 'SOUND', _sound_items),
        Screen('wipe', 'WIPE SAVE?', _wipe_items, hint='select'),
        Screen('graphics', 'GRAPHICS', _graphics_items),
        Screen('controls', 'CONTROLS', _controls_items, hint='controls'),
        Screen('save', 'SAVE GAME', _save_items, hint='select'),
        Screen('load', 'LOAD GAME', _load_items, hint='select'),
        Screen('birdpedia', 'BIRDPEDIA', _birdpedia_items, hint='select'),
        Screen('flock', 'FLOCK', _flock_items, hint='select'),
        _page('flock_stats', 'flock_stats'),
        *[_page(f'flock_bird_{i}', f'flock_bird_{i}') for i in range(constants.layout.num_balls)],
        Screen('guide', 'GUIDE', _guide_items, hint='select'),
        _page('guide_howto', 'howto'),
        _page('guide_commands', 'commands'),
        _page('guide_obstacles', 'obstacles'),
        _page('guide_enemies', 'enemies'),
        _page('birdpedia_list', 'birds'),
        _page('batpedia_list', 'bats'),
        _page('biomes_list', 'biomes'),
        Screen('upgrades', 'UPGRADES', _upgrades_items, hint='select'),
        Screen('formation', 'FORMATION', _formation_items, hint='formation'),
        Screen('flock_meta', 'FLOCK', _flock_meta_items, hint='select'),
        _page('page_feathers', 'feathers'),
        _page('page_flock_birds', 'flock_birds'),
        Screen('leaderboards', 'LEADERBOARDS', _leaderboard_items, hint='select'),
        *[_page(f'leaderboard_{period}', f'board_{period}') for period in ('week', 'month', 'all')],
        Screen('achievements', 'ACHIEVEMENTS', _achievements_items, hint='select'),
    )
}


def _add_meta_screens():
    """One screen per upgrade branch and per achievement page (they come from the config)."""
    from src.ui.pages import achievement_pages

    for branch in _branches():
        sid = f'upgrades_{branch}'
        SCREENS[sid] = Screen(sid, branch.upper(), _branch_items(branch), hint='upgrade')
    for content in achievement_pages():
        SCREENS[f'page_{content}'] = _page(f'page_{content}', content)


# The configuration is loaded when constants is imported: build them now too
_add_meta_screens()


# =============================================================================
# NAVIGATION
# =============================================================================


def open_title():
    """Show the title menu with the cursor on its first item."""
    state.ui.menu_stack = [[TITLE, 0]]
    state.ui.rebinding_control = None


def ensure_pause_root():
    """Make sure the menu hangs from the pause root (keeping its cursor)."""
    if root() != PAUSE:
        state.ui.menu_stack = [[PAUSE, 0]]


def current_screen():
    return SCREENS[state.ui.menu_stack[-1][0]]


def cursor():
    return state.ui.menu_stack[-1][1]


def depth():
    """1 at the root, more inside submenus."""
    return len(state.ui.menu_stack)


def close_submenus():
    del state.ui.menu_stack[1:]


def _open(screen_id):
    if screen_id not in SCREENS:
        _add_meta_screens()
    state.ui.menu_stack.append([screen_id, 0])


def _back():
    stack = state.ui.menu_stack
    if len(stack) <= 1:
        return
    leaving = stack.pop()[0]
    if leaving == 'settings':
        # Leaving the settings: on the title screen they become the defaults
        _settings_changed()


def _activate(item):
    if item.back:
        _back()
    elif item.opens:
        _open(item.opens)
    elif item.rebind:
        state.ui.rebinding_control = item.rebind
    elif item.on_enter:
        item.on_enter()


def handle_key(key):
    """Apply one key press to the open menu."""
    if key == 'QUIT':
        _quit()
        return
    if state.ui.rebinding_control is None:
        from src.services import sound

        sound.menu_key(key)
    if state.ui.rebinding_control is not None:
        _rebind(key)
        return

    entry = state.ui.menu_stack[-1]
    screen = SCREENS[entry[0]]
    items = screen.items()

    if screen.content and key in ('UP', 'DOWN'):
        # Text pages scroll (the view keeps the offset within the page)
        scroll = state.ui.page_scroll
        scroll[screen.content] = max(0, scroll.get(screen.content, 0) + (1 if key == 'DOWN' else -1))
        return
    if key in ('UP', 'DOWN'):
        entry[1] = (entry[1] + (1 if key == 'DOWN' else -1)) % len(items)
    elif key in ('LEFT', 'RIGHT'):
        item = items[entry[1]]
        if item.on_change:
            item.on_change(1 if key == 'RIGHT' else -1)
    elif key == 'ENTER':
        _activate(items[entry[1]])
    elif depth() > 1:
        if key == 'ESC':
            _back()
    elif root() == PAUSE and key in ('ESC', 'p', 'P'):
        handle_pause()  # resume
