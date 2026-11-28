"""The tutorial: tips that stop the game the first time something happens.

Each tip shows once (the ids seen are kept in the profile, ``tutorial_seen``), when its
moment comes: the start of the first world, the first rising bird under the cursor, the
first boss, the first egg's cards... While a tip is on screen the game holds, as for the
cards; ENTER (X on a gamepad) goes on, S (B) skips the whole tutorial. SETTINGS >
TUTORIAL turns it off, or on again to see every tip once more.

Tips are part of the game (they hold it): the recordings keep the setting and the
profile, so a replay shows the same tips at the same moments. The bot and the
simulator play with it off.
"""

from src.core import constants, state
from src.engine import events

# id -> (title, text). The texts name the keys with {action} labels (src/ui/controls.py)
TIPS = {
    'bounce': (
        'Keep them flying',
        'Birds fall. Press {bounce} when one is over the cursor to send it back up; '
        '{move} moves the cursor. A bird that touches the ground is lost.',
    ),
    'power': (
        'Powers',
        'Press {bounce} on a RISING bird to fire its power: every kind has its own. '
        'SETTINGS > CONTROLS > POWER BUTTON moves powers to {power}.',
    ),
    'obstacle': (
        'Obstacles',
        'Rising birds hit what is above them. Break obstacles for points and XP; '
        'a bird that hits one and does not break it is knocked back down.',
    ),
    'gear': (
        'Gear',
        'Bounces build momentum and momentum raises the gear: faster, more points, but your birds fall faster too.',
    ),
    'swap': (
        'Swaps',
        '{swap} on a lane, move, {swap} again: the two birds change lanes. It costs momentum: '
        'use it to put the right bird in the right place, or to slow down.',
    ),
    'grade': (
        'Grades',
        'Birds earn XP by hitting things and climb grades: stronger, and more powers per ascent. '
        'Some kinds evolve at the top grade.',
    ),
    'boss': (
        'Boss',
        'The road stops until the boss is dead. Beat it for its pact: a strong bonus with a price.',
    ),
    'cards': (
        'Eggs and cards',
        'Every egg offers cards; rarer eggs, rarer cards. Lasting cards have levels and a run follows '
        'only a few kinds: a common card spends a level on a small value, so wait for rare ones. '
        '{reroll} rerolls, {skip} skips. Timed cards and birds cost no level.',
    ),
    'pact': ('Pacts', 'A pact gives a lot and takes something back. You may refuse it.'),
    'merchant': (
        'The merchant',
        'Between worlds the merchant sells eggs and lives for the run\'s feathers: '
        'what you spend comes off the run\'s reward.',
    ),
    'waves': (
        'Bat waves',
        'Bats come in waves, one every so often, whether you killed the last ones or not. '
        'The boss comes only when every wave of its level is dead.',
    ),
    'fear': (
        'Fear',
        'Bats scare birds: a scared bird falls faster and cannot be bounced for a moment. Fast birds '
        '(Blue) fall furthest. Fear resistance and shorter scares are a build of their own.',
    ),
}

_started = {'frame': None}


def enabled():
    return bool(getattr(state.settings, 'tutorial', False)) and not state.ui.show_title


def _seen():
    profile = state.meta.profile
    if profile is None:
        return set(TIPS)
    return set(profile.setdefault('tutorial_seen', []))


def active():
    return state.ui.tip


def show(tip_id):
    """Show a tip now if it is due (not seen, tutorial on, no other tip on screen)."""
    if not enabled() or state.ui.tip is not None or tip_id in _seen():
        return False
    title, text = TIPS[tip_id]
    state.ui.tip = {'id': tip_id, 'title': title, 'text': text}
    state.meta.profile.setdefault('tutorial_seen', []).append(tip_id)
    return True


def dismiss():
    state.ui.tip = None


def skip_all():
    """Skip the whole tutorial (SETTINGS > TUTORIAL turns it on again)."""
    state.ui.tip = None
    if state.meta.profile is not None:
        seen = state.meta.profile.setdefault('tutorial_seen', [])
        seen.extend(t for t in TIPS if t not in seen)
    state.settings.tutorial = False
    if not getattr(state, '_replaying', False):
        from src.services import save_manager

        save_manager.save_default_settings()  # stays off in the next games


def reset():
    """Every tip once more (SETTINGS > TUTORIAL on)."""
    if state.meta.profile is not None:
        state.meta.profile['tutorial_seen'] = []


def handle_key(key):
    """Keys while a tip is on screen: ENTER (X) goes on, S (B) skips the tutorial."""
    if key in ('ENTER', 'PICK'):
        dismiss()
    elif key in ('S', 's'):
        skip_all()


def update():
    """Every tick: the tips whose moment is a state of the game."""
    if not enabled() or state.ui.tip is not None or state.choice.active is not None:
        return
    frame = state.game.frame_count
    if _started['frame'] is None or frame < _started['frame']:
        _started['frame'] = frame
    seconds = (frame - _started['frame']) * constants.timing.base_sleep
    birds = state.birds
    alive = [i for i in range(constants.layout.num_balls) if not birds.lost[i]]
    under_cursor = [i for i in alive if birds.random_lanes[i] == state.player.lane]
    if state.game.level_group == 1 and seconds > 1.0 and show('bounce'):
        return
    if 'bounce' in _seen() and seconds > 8 and any(birds.vy[i] == -1 for i in under_cursor) and show('power'):
        return
    lower = constants.layout.height // 2
    if any(o.get('y_pos', 0) >= lower for o in state.enemies.obstacles) and show('obstacle'):
        return
    if state.game.speed >= 3 and show('gear'):
        return
    if seconds > 40 and show('swap'):
        return
    from src.engine.grades import compute_grade_from_xp

    lowest = compute_grade_from_xp(0)[0]
    if any(compute_grade_from_xp(birds.per_bird_xp[i])[0] != lowest for i in alive) and show('grade'):
        return
    if state.enemies.bat_wave is not None and show('waves'):
        return
    if state.special.scared_birds and show('fear'):
        return


def _on_boss_spawned(**_fields):
    show('boss')


def _on_choice_offered(offer=None, **_fields):
    kind = (offer or {}).get('kind')
    show({'egg': 'cards', 'pact': 'pact', 'merchant': 'merchant'}.get(kind, 'cards'))


def subscribe():
    events.on('boss_spawned', _on_boss_spawned)
    events.on('choice_offered', _on_choice_offered)
