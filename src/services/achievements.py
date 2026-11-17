"""
Achievements system for Birds vs Bats game.
Handles achievement definitions, tracking and unlocking.
"""

import contextlib

from src.core import constants as v

# Global state
achievements = {}
notifications = []  # list of (text, expire_frame)
recent_powers = []              # list of (power_name, frame_count, lane) for synergy detection
bat_destroy_counters = {'total': 0, 'tier1': 0, 'tier2': 0, 'tier3': 0, 'tier4': 0}


def init_achievements():
    """Define achievements with simple goals."""
    global achievements
    achievements = {
        # score milestones
        'score_1k': {'name': 'Novice', 'desc': 'Reach 1,000 points', 'unlocked': False, 'type': 'score', 'goal': 1000},
        'score_5k': {'name': 'Expert', 'desc': 'Reach 5,000 points', 'unlocked': False, 'type': 'score', 'goal': 5000},
        'score_20k': {'name': 'Veteran', 'desc': 'Reach 20,000 points', 'unlocked': False, 'type': 'score', 'goal': 20000},
        'score_70k': {'name': 'Legend', 'desc': 'Reach 70,000 points', 'unlocked': False, 'type': 'score', 'goal': 70000},
        # swaps
        'swap_1': {'name': 'Swapping Lanes', 'desc': 'Use swap once', 'unlocked': False, 'type': 'counter', 'key': 'swaps', 'goal': 1, 'progress': 0},
        'swap_10': {'name': 'Rearranger', 'desc': 'Use swap 10 times', 'unlocked': False, 'type': 'counter', 'key': 'swaps', 'goal': 10, 'progress': 0},
        'swap_100': {'name': 'OCD', 'desc': 'Use swap 100 times', 'unlocked': False, 'type': 'counter', 'key': 'swaps', 'goal': 100, 'progress': 0},
        # collect special eggs
        'collect_purple': {'name': 'The Fearless', 'desc': 'Collect a purple egg', 'unlocked': False, 'type': 'collect', 'loot': 'purple_egg'},
        'collect_clockwork': {'name': 'The Bot', 'desc': 'Collect a clockwork egg', 'unlocked': False, 'type': 'collect', 'loot': 'clockwork_egg'},
        'collect_white': {'name': 'The Phantom', 'desc': 'Collect a white egg', 'unlocked': False, 'type': 'collect', 'loot': 'white_egg'},
        'collect_orange': {'name': 'The Phoenix', 'desc': 'Collect an orange egg', 'unlocked': False, 'type': 'collect', 'loot': 'orange_egg'},
        # destroy counters
        'destroy_bat_orange': {'name': 'Phoenix Fire', 'desc': 'Destroy a bat with an orange bird', 'unlocked': False, 'type': 'special', 'event': 'destroy_bat_with_orange'},
        # power usage progressive achievements (per power)
        'power_yellow_1': {'name': 'Chirp', 'desc': 'Use Yellow power once', 'unlocked': False, 'type': 'counter', 'key': 'power_yellow', 'goal': 1, 'progress': 0},
        'power_yellow_10': {'name': 'Mockingbird', 'desc': 'Use Yellow power 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_yellow', 'goal': 10, 'progress': 0},
        'power_red_1': {'name': 'Ember', 'desc': 'Use Red power once', 'unlocked': False, 'type': 'counter', 'key': 'power_red', 'goal': 1, 'progress': 0},
        'power_red_10': {'name': 'Flame', 'desc': 'Use Red power 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_red', 'goal': 10, 'progress': 0},
        'power_blue_1': {'name': 'Sprint', 'desc': 'Use Blue power once', 'unlocked': False, 'type': 'counter', 'key': 'power_blue', 'goal': 1, 'progress': 0},
        'power_blue_10': {'name': 'Haste', 'desc': 'Use Blue power 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_blue', 'goal': 10, 'progress': 0},
        'power_white_1': {'name': 'Encourage!', 'desc': 'Use White power once', 'unlocked': False, 'type': 'counter', 'key': 'power_white', 'goal': 1, 'progress': 0},
        'power_white_10': {'name': 'Brave Bird', 'desc': 'Use White power 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_white', 'goal': 10, 'progress': 0},
        # synergies
        'synergy_pair': {'name': 'Get Along', 'desc': 'Trigger two different powers in quick succession', 'unlocked': False, 'type': 'special', 'event': 'synergy_pair'},
        'synergy_triple': {'name': 'Frenship Is Magic', 'desc': 'Trigger three different powers in quick succession', 'unlocked': False, 'type': 'special', 'event': 'synergy_triple'},
        # area hold achievements (frames)
        # original birds survival
        # counts of single color
        # Additional color-count achievements for other colors
        # Collect blue egg achievement (others already present)
        'collect_blue': {'name': 'Baby Blue', 'desc': 'Collect a blue egg', 'unlocked': False, 'type': 'collect', 'loot': 'blue_egg'},
        # Bat kills (total)
        'destroy_bat_10': {'name': 'Bat Slayer I', 'desc': 'Destroy 10 bats', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed', 'goal': 10, 'progress': 0},
        'destroy_bat_100': {'name': 'Bat Slayer II', 'desc': 'Destroy 100 bats', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed', 'goal': 100, 'progress': 0},
        # Per-tier bat kill achievements (tier-specific keys)
        'destroy_bat_t1_10': {'name': 'Tier1 Slayer', 'desc': 'Destroy 10 tier1 bats', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed_tier1', 'goal': 10, 'progress': 0},
        'destroy_bat_t2_10': {'name': 'Tier2 Slayer', 'desc': 'Destroy 10 tier2 bats', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed_tier2', 'goal': 10, 'progress': 0},
        'destroy_bat_t3_10': {'name': 'Tier3 Slayer', 'desc': 'Destroy 10 tier3 bats', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed_tier3', 'goal': 10, 'progress': 0},
        'destroy_bat_t4_1': {'name': 'Tier4 Hunter', 'desc': 'Destroy 1 tier4 bat', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed_tier4', 'goal': 1, 'progress': 0},
        'destroy_bat_t4_10': {'name': 'Tier4 Slayer', 'desc': 'Destroy 10 tier4 bats', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed_tier4', 'goal': 10, 'progress': 0},
        # Power-up usage
        'power_wide_cursor_1': {'name': 'Cursor Novice', 'desc': 'Use Wide Cursor once', 'unlocked': False, 'type': 'counter', 'key': 'power_wide_cursor', 'goal': 1, 'progress': 0},
        'power_wide_cursor_10': {'name': 'Cursor Expert', 'desc': 'Use Wide Cursor 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_wide_cursor', 'goal': 10, 'progress': 0},
        'power_tailwind_1': {'name': 'Tailwind Novice', 'desc': 'Use Tailwind once', 'unlocked': False, 'type': 'counter', 'key': 'power_tailwind', 'goal': 1, 'progress': 0},
        'power_tailwind_10': {'name': 'Tailwind Expert', 'desc': 'Use Tailwind 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_tailwind', 'goal': 10, 'progress': 0},
    }


def add_notification(text, frame_count, notifications_list, title=None):
    """Add a short on-screen notification for a few frames.

    Args:
        text: Main notification text
        frame_count: Current frame number
        notifications_list: List to append notification to
        title: Optional title for the card
    """
    try:
        duration = getattr(v.notifications, 'duration_seconds', 3.0)
        base_sleep = getattr(v.timing, 'base_sleep', 0.1)
        frames = int(duration / base_sleep)
        if frames <= 0:
            frames = 1
    except Exception:
        frames = 40

    notification = {
        'title': title or '',
        'text': text,
        'expire_frame': frame_count + frames
    }

    # Insert at beginning (top of stack)
    notifications_list.insert(0, notification)

    # Limit stack size
    try:
        max_stack = getattr(v.notifications, 'max_stack', 3)
    except Exception:
        max_stack = 3

    while len(notifications_list) > max_stack:
        notifications_list.pop()


def unlock_achievement(aid, frame_count, notifications_list, firebase_client=None, background_call=None):
    """Unlock an achievement and add notification."""
    global achievements
    a = achievements.get(aid)
    if not a or a.get('unlocked'):
        return False
    a['unlocked'] = True
    add_notification(a['name'], frame_count, notifications_list, title="Achievement:")

    # Try to sync/unlock achievement for remote user
    if firebase_client and background_call:
        with contextlib.suppress(Exception):
            background_call(firebase_client.unlock_achievement, aid)
        with contextlib.suppress(Exception):
            background_call(firebase_client.log_event, 'achievement_unlocked', {'id': aid, 'name': a.get('name')})
    return True


def check_achievements_event(event, frame_count, notifications_list, firebase_client=None, background_call=None, **kwargs):
    """Handle simple achievement triggers."""
    global achievements, bat_destroy_counters, recent_powers

    if event == 'score':
        sc = kwargs.get('score', 0)
        for aid, a in achievements.items():
            if a.get('type') == 'score' and not a.get('unlocked'):
                if sc >= a.get('goal', 0):
                    unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)

    elif event == 'swap':
        swaps = kwargs.get('swaps', 0)
        for aid, a in achievements.items():
            if a.get('type') == 'counter' and a.get('key') == 'swaps' and not a.get('unlocked'):
                if swaps >= a.get('goal', 0):
                    unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)

    elif event == 'collect':
        loot = kwargs.get('loot')
        for aid, a in achievements.items():
            if a.get('type') == 'collect' and not a.get('unlocked'):
                if a.get('loot') == loot:
                    unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)

    elif event == 'destroy_bat':
        tier = kwargs.get('tier')
        try:
            bat_destroy_counters['total'] += 1
            if tier in (1, 2, 3, 4):
                bat_destroy_counters[f'tier{tier}'] += 1
        except Exception:
            pass

        for aid, a in achievements.items():
            if a.get('type') == 'counter' and not a.get('unlocked'):
                if a.get('key') == 'bats_destroyed':
                    a['progress'] = a.get('progress', 0) + 1
                    if a['progress'] >= a.get('goal', 0):
                        unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)
                if tier in (1, 2, 3, 4) and a.get('key') == f'bats_destroyed_tier{tier}':
                    a['progress'] = a.get('progress', 0) + 1
                    if a['progress'] >= a.get('goal', 0):
                        unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)

    elif event == 'power_used':
        power = kwargs.get('power')
        lane = kwargs.get('lane')
        if not power:
            return
        key = f'power_{power}'
        for aid, a in achievements.items():
            if a.get('type') == 'counter' and a.get('key') == key and not a.get('unlocked'):
                a['progress'] = a.get('progress', 0) + 1
                if a['progress'] >= a.get('goal', 0):
                    unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)

        recent_powers.append((power, frame_count, lane))
        recent_powers[:] = [(p, f, l) for (p, f, l) in recent_powers if frame_count - f <= 300]

        distinct = {p for (p, f, l) in recent_powers}
        if len(distinct) >= 2:
            check_achievements_event('synergy', frame_count, notifications_list, firebase_client, background_call, combo=distinct)
        if len(distinct) >= 3:
            check_achievements_event('synergy', frame_count, notifications_list, firebase_client, background_call, combo=distinct)

    elif event == 'synergy':
        combo = kwargs.get('combo', set())
        if len(combo) >= 3:
            for aid, a in achievements.items():
                if a.get('type') == 'special' and a.get('event') == 'synergy_triple' and not a.get('unlocked'):
                    unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)
        elif len(combo) >= 2:
            for aid, a in achievements.items():
                if a.get('type') == 'special' and a.get('event') == 'synergy_pair' and not a.get('unlocked'):
                    unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)

    elif event == 'destroy_bat_with_orange':
        for aid, a in achievements.items():
            if a.get('type') == 'special' and a.get('event') == 'destroy_bat_with_orange' and not a.get('unlocked'):
                unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)


# =============================================================================
# EVENT SUBSCRIPTIONS
# =============================================================================


def _check(event, **fields):
    from src.core import state

    check_achievements_event(event, state.game.frame_count, state.ui.notifications, **fields)


def _on_score_changed(score):
    from src.services.background import background_call
    from src.services.optional import firebase_client

    _check('score', firebase_client=firebase_client, background_call=background_call, score=score)


def _on_bat_killed(bat, tier, killer):
    from src.core import state
    from src.entities.sprites import ORANGE

    if state.birds.colors[killer] == ORANGE:
        _check('destroy_bat_with_orange')
    _check('destroy_bat', tier=tier)


def subscribe():
    """Track achievements from game events."""
    from src.engine import events

    events.on('score_changed', _on_score_changed)
    events.on('swap', lambda swaps: _check('swap', swaps=swaps))
    events.on('power_used', lambda power, lane: _check('power_used', power=power, lane=lane))
    events.on('bat_killed', _on_bat_killed)
    events.on('mini_bat_killed', lambda bat, killer: _check('destroy_bat', tier=0))
    events.on('loot_collected', lambda loot, bird: _check('collect', loot=loot['type']))
