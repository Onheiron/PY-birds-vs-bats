"""The menu tree: structure, navigation and the title/pause differences."""

import json

import pytest

from src.core import state
from src.engine import menus
from src.services import save_manager
from tests.harness import Simulation


@pytest.fixture
def sim():
    with Simulation(seed=21, level=2) as simulation:
        simulation.run(30)
        yield simulation


def open_title(sim):
    state.ui.show_title = True
    menus.open_title()
    sim.press(None, title=True)


def pause(sim):
    sim.step(key='p')
    assert state.game.paused


def press_all(sim, keys, title=False):
    for key in keys:
        sim.press(key, title=title)


def current():
    return state.ui.menu_stack[-1][0], state.ui.menu_stack[-1][1]


def test_tree_is_consistent():
    for screen in menus.SCREENS.values():
        items = screen.items()
        assert items, screen.id
        for item in items:
            if item.opens:
                assert item.opens in menus.SCREENS, f'{screen.id} opens unknown {item.opens}'
        if screen.id not in (menus.TITLE, menus.PAUSE):
            # Every submenu can be left with its last entry
            assert items[-1].back, screen.id


def test_every_submenu_is_reachable_from_a_root():
    from src.core import state as game_state
    from src.engine import meta

    game_state.meta.profile = meta.new_profile()
    game_state.meta.profile['upgrades'] = {'formation': 1}  # FORMATION shows once it is bought
    reachable = set()
    todo = [menus.TITLE, menus.PAUSE]
    while todo:
        screen_id = todo.pop()
        if screen_id in reachable:
            continue
        reachable.add(screen_id)
        todo.extend(item.opens for item in menus.SCREENS[screen_id].items() if item.opens)
    game_state.meta.profile = None
    assert reachable == set(menus.SCREENS)


def test_cursor_wraps_and_back_returns_to_the_opening_item(sim):
    pause(sim)
    press_all(sim, ['UP'])
    assert current() == ('pause', 7)  # wrapped to MAIN MENU
    press_all(sim, ['UP', 'UP', 'ENTER'])  # SETTINGS (above FLOCK)
    assert current() == ('settings', 0)
    press_all(sim, ['DOWN', 'DOWN', 'ENTER'])  # CONTROLS
    assert current() == ('controls', 0)
    press_all(sim, ['ESC'])
    assert current() == ('settings', 2)
    press_all(sim, ['ESC'])
    assert current() == ('pause', 5)
    assert 'SETTINGS' in sim.screen.text()


def test_guide_pages_return_to_their_entry(sim):
    pause(sim)
    press_all(sim, ['DOWN'] * 4 + ['ENTER', 'ENTER', 'DOWN', 'ENTER'])  # BIRDPEDIA > GUIDE > COMMANDS
    assert current() == ('guide_commands', 0)
    assert 'P - Pause game' in sim.screen.text()
    press_all(sim, ['ENTER'])  # the page's only option goes back
    assert current() == ('guide', 1)


def test_pause_root_resumes_with_escape_and_keeps_its_cursor(sim):
    pause(sim)
    press_all(sim, ['DOWN', 'DOWN', 'ESC'])
    assert not state.game.paused
    pause(sim)
    assert current() == ('pause', 2)


def test_keys_in_a_submenu_do_not_unpause(sim):
    pause(sim)
    press_all(sim, ['DOWN'] * 5 + ['ENTER', 'p', 'P'])
    assert state.game.paused
    assert current() == ('settings', 0)


def test_title_screen_swallows_gameplay_keys(sim):
    lane = state.player.lane
    open_title(sim)
    press_all(sim, ['RIGHT', 'p', 'x', 'SPACE', 'ESC'], title=True)
    assert state.player.lane == lane
    assert not state.game.paused
    assert not state.ui.show_xp_overlay
    assert current() == ('title', 0)


def test_new_game_difficulty_is_chosen_on_the_title_menu(sim):
    open_title(sim)
    state.settings.difficulty = 1
    press_all(sim, ['DOWN', 'LEFT'], title=True)
    assert state.settings.difficulty == 0
    assert 'NEW GAME  < PEACEFUL >' in sim.screen.text()
    press_all(sim, ['RIGHT'], title=True)
    assert state.settings.difficulty == 1
    # LEFT/RIGHT elsewhere does nothing
    press_all(sim, ['UP', 'RIGHT'], title=True)
    assert state.settings.difficulty == 1


def defaults_file():
    path = save_manager.get_default_settings_path()
    return json.loads(path.read_text()) if path.exists() else {}


def test_title_settings_are_saved_as_defaults_but_pause_settings_are_not(sim):
    state.settings.sfx_enabled = True
    save_manager.save_default_settings()

    pause(sim)
    press_all(sim, ['DOWN'] * 5 + ['ENTER', 'ENTER', 'ENTER'])  # SETTINGS > SOUND > toggle SFX
    assert state.settings.sfx_enabled is False
    assert defaults_file()['sfx_enabled'] is True
    press_all(sim, ['ESC', 'ESC', 'ESC'])

    open_title(sim)
    press_all(sim, ['DOWN'] * 7 + ['ENTER', 'ENTER', 'RIGHT'], title=True)  # SETTINGS > SOUND > toggle SFX
    assert state.settings.sfx_enabled is True
    assert defaults_file()['sfx_enabled'] is True
    press_all(sim, ['LEFT'], title=True)
    assert defaults_file()['sfx_enabled'] is False
    state.settings.sfx_enabled = True
    save_manager.save_default_settings()


def test_rebinding_a_control(sim):
    pause(sim)
    press_all(sim, ['DOWN'] * 5 + ['ENTER', 'DOWN', 'DOWN', 'ENTER', 'DOWN', 'DOWN', 'ENTER'])  # CONTROLS > BOUNCE
    assert state.ui.rebinding_control == 'BOUNCE'
    assert 'Press new key' in sim.screen.text()
    press_all(sim, ['!'])  # not bindable: still waiting
    assert state.ui.rebinding_control == 'BOUNCE'
    press_all(sim, ['w'])
    assert state.ui.rebinding_control is None
    assert state.settings.key_bindings['BOUNCE'] == 'W'
    # ESC cancels without changing anything
    press_all(sim, ['ENTER', 'ESC'])
    assert state.settings.key_bindings['BOUNCE'] == 'W'
    state.settings.key_bindings['BOUNCE'] = 'UP'


def test_save_and_load_through_the_pause_menu(sim):
    score = state.game.score = 4321
    pause(sim)
    press_all(sim, ['DOWN', 'DOWN', 'ENTER', 'DOWN', 'DOWN', 'ENTER'])  # SAVE > SLOT 3
    assert current() == ('pause', 2)
    assert save_manager.list_save_slots()[3]['exists']

    state.game.score = 0
    press_all(sim, ['DOWN', 'ENTER', 'DOWN', 'DOWN', 'DOWN', 'ENTER'])  # LOAD > SLOT 3
    assert state.game.score == score
    assert not state.game.paused
    assert state.ui.notifications[0]['text'] == 'Loaded Slot 3'
    save_manager.delete_save(3)


def test_loading_an_empty_slot_reports_it(sim):
    pause(sim)  # pausing saves to the autosave slot...
    for slot in range(4):
        save_manager.delete_save(slot)  # ...so empty them all afterwards
    press_all(sim, ['DOWN'] * 3 + ['ENTER', 'ENTER'])  # LOAD > AUTO
    assert state.ui.notifications[0]['text'] == 'Slot is empty!'
    assert state.game.paused
    assert 'AUTO  (empty)' in sim.screen.text()


def test_pausing_saves_the_game(sim):
    save_manager.delete_save(0)
    pause(sim)
    assert save_manager.get_most_recent_save() == 0


def test_main_menu_returns_to_the_title(sim):
    pause(sim)
    press_all(sim, ['UP', 'ENTER'])  # MAIN MENU
    assert state.ui.show_title
    assert state.game.game_over
    assert current() == ('title', 0)


def test_cursor_assists_are_off_by_default_and_work():
    from src.core import constants
    from src.engine.actions import handle_movement
    from tests.harness import Simulation

    with Simulation(seed=1, key_rate=0) as sim:
        state = sim.state
        assert not state.settings.bounce_on_enter and not state.settings.trigger_on_enter
        try:
            _check_assists(sim, state, handle_movement)
        finally:
            # Settings outlive a game: leave them as found
            state.settings.bounce_on_enter = state.settings.trigger_on_enter = False
        assert constants.layout.num_lanes == 9


def _check_assists(sim, state, handle_movement):
    sim.run(5)
    state.player.lane = 3
    bird = next(i for i in range(9) if state.birds.random_lanes[i] == 4)
    state.birds.vy[bird] = 1
    state.special.scared_birds.pop(bird, None)
    state.special.stunned_birds.pop(bird, None)
    handle_movement('RIGHT')
    assert state.birds.vy[bird] == 1, 'no assist by default'

    state.settings.bounce_on_enter = True
    handle_movement('LEFT')
    handle_movement('RIGHT')
    assert state.birds.vy[bird] == -1, 'bounce on enter bounced the falling bird'
    assert not state.birds.power_used[bird], 'but did not fire its power'

    state.settings.bounce_on_enter = False
    state.settings.trigger_on_enter = True
    state.birds.power_used[bird] = False
    handle_movement('LEFT')
    handle_movement('RIGHT')
    assert state.birds.power_used[bird] or state.birds.power_uses[bird] > 0, 'trigger on enter fired the power'


def test_the_flock_menu_shows_base_power_ups_and_total(sim):
    from src.engine import stats
    from src.ui import flock_pages

    bird = flock_pages.bird_slots()[0]
    stats.add_modifier(bird, 'fall_speed_bonus', add=-4, source='card:feather_brake')
    sim.state.choice.taken.append({'id': 'feather_brake', 'name': 'Feather Brake', 'kind': 'stat', 'rarity': 'common'})
    page = flock_pages.bird_page(bird)
    row = next(line for line in page['lines'] if line.startswith('fall speed bonus'))
    base, now = (float(v) for v in row.split()[-2:])
    assert now == base - 4
    flock = flock_pages.flock_page()
    assert any('Feather Brake' in line for line in flock['lines'])
    pause(sim)
    press_all(sim, ['UP', 'UP', 'ENTER'])  # FLOCK (above MAIN MENU)
    assert current() == ('flock', 0)
    press_all(sim, ['ENTER'])
    assert current()[0].startswith('flock_bird_')


def test_the_music_always_starts_on(sim):
    state.settings.music_enabled = False
    save_manager.save_default_settings()
    assert defaults_file()['music_enabled'] is False
    save_manager.load_default_settings()
    assert state.settings.music_enabled is True  # off only for the session it was turned off in
