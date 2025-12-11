"""
Achievements system for Birds vs Bats game.
Handles achievement definitions, tracking, unlocking, and combo detection.
"""

import constants as v

# Global state
achievements = {}
notifications = []  # list of (text, expire_frame)
power_usage_counters = {}        # e.g. {'power_yellow': 3}
recent_powers = []              # list of (power_name, frame_count, lane) for synergy detection
top50_hold_frames = 0
top30_hold_frames = 0
original_alive_frames = 0
bat_destroy_counters = {'total': 0, 'tier1': 0, 'tier2': 0, 'tier3': 0, 'tier4': 0}

# Recent atomic actions for combo detection: list of dicts {action, frame, lane, color}
recent_actions = []
# Prevents repeating the same combo too frequently: map combo_id -> expire_frame
combo_cooldowns = {}

# Synergy transfer ratio
SYNERGY_TRANSFER_RATIO = 0.10  # fraction of XP gap transferred on synergy


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
        'destroy_obstacle_10': {'name': 'Breaker I', 'desc': 'Destroy 10 obstacles', 'unlocked': False, 'type': 'counter', 'key': 'obstacles_destroyed', 'goal': 10, 'progress': 0},
        'destroy_obstacle_100': {'name': 'Breaker II', 'desc': 'Destroy 100 obstacles', 'unlocked': False, 'type': 'counter', 'key': 'obstacles_destroyed', 'goal': 100, 'progress': 0},
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
        'hold_top50_200': {'name': 'High Skies', 'desc': 'Keep all birds in top 50% for a while', 'unlocked': False, 'type': 'area', 'key': 'top50', 'goal': 200},
        'hold_top30_400': {'name': 'Heavenly', 'desc': 'Keep all birds in top 30% for longer', 'unlocked': False, 'type': 'area', 'key': 'top30', 'goal': 400},
        # original birds survival
        'original_alive_300': {'name': 'Careful', 'desc': 'Keep original birds alive for some time', 'unlocked': False, 'type': 'original', 'goal': 300},
        'original_alive_700': {'name': 'Responsible', 'desc': 'Keep original birds alive for a long time', 'unlocked': False, 'type': 'original', 'goal': 700},
        'original_alive_2000': {'name': 'Survivalist', 'desc': 'Keep original birds alive for a very long time', 'unlocked': False, 'type': 'original', 'goal': 2000},
        # counts of single color
        'count_yellow_5': {'name': 'Yellow Flock', 'desc': 'Have 5 yellow birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'YELLOW', 'goal': 5},
        'count_yellow_7': {'name': 'Yellow Horde', 'desc': 'Have 7 yellow birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'YELLOW', 'goal': 7},
        'count_all_9': {'name': 'Nine of a Kind', 'desc': 'Have all 9 birds of the same color', 'unlocked': False, 'type': 'color_count_all', 'goal': 9},
        # Additional color-count achievements for other colors
        'count_red_5': {'name': 'Red Flock', 'desc': 'Have 5 red birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'RED', 'goal': 5},
        'count_red_7': {'name': 'Red Horde', 'desc': 'Have 7 red birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'RED', 'goal': 7},
        'count_blue_5': {'name': 'Blue Flock', 'desc': 'Have 5 blue birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'BLUE', 'goal': 5},
        'count_blue_7': {'name': 'Blue Horde', 'desc': 'Have 7 blue birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'BLUE', 'goal': 7},
        'count_white_5': {'name': 'White Flock', 'desc': 'Have 5 white birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'WHITE', 'goal': 5},
        'count_white_7': {'name': 'White Horde', 'desc': 'Have 7 white birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'WHITE', 'goal': 7},
        'count_clockwork_5': {'name': 'Clockwork Flock', 'desc': 'Have 5 clockwork birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'CLOCKWORK', 'goal': 5},
        'count_clockwork_7': {'name': 'Clockwork Horde', 'desc': 'Have 7 clockwork birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'CLOCKWORK', 'goal': 7},
        'count_purple_5': {'name': 'Purple Flock', 'desc': 'Have 5 purple birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'PURPLE', 'goal': 5},
        'count_purple_7': {'name': 'Purple Horde', 'desc': 'Have 7 purple birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'PURPLE', 'goal': 7},
        'count_orange_5': {'name': 'Orange Flock', 'desc': 'Have 5 orange birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'ORANGE', 'goal': 5},
        'count_orange_7': {'name': 'Orange Horde', 'desc': 'Have 7 orange birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'ORANGE', 'goal': 7},
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
        # Power usage achievements for cursor and new powers (tailwind, shuffle)
        'power_wide_cursor_1': {'name': 'Cursor Novice', 'desc': 'Use Wide Cursor once', 'unlocked': False, 'type': 'counter', 'key': 'power_wide_cursor', 'goal': 1, 'progress': 0},
        'power_wide_cursor_10': {'name': 'Cursor Expert', 'desc': 'Use Wide Cursor 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_wide_cursor', 'goal': 10, 'progress': 0},
        # Replaced bounce/suction achievements with tailwind and shuffle
        'power_tailwind_1': {'name': 'Tailwind Novice', 'desc': 'Use Tailwind once', 'unlocked': False, 'type': 'counter', 'key': 'power_tailwind', 'goal': 1, 'progress': 0},
        'power_tailwind_10': {'name': 'Tailwind Expert', 'desc': 'Use Tailwind 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_tailwind', 'goal': 10, 'progress': 0},
        'power_shuffle_1': {'name': 'Shuffle Novice', 'desc': 'Use Shuffle once', 'unlocked': False, 'type': 'counter', 'key': 'power_shuffle', 'goal': 1, 'progress': 0},
        'power_shuffle_10': {'name': 'Shuffle Expert', 'desc': 'Use Shuffle 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_shuffle', 'goal': 10, 'progress': 0},
        # Area hold smaller tiers
        'hold_top50_100': {'name': 'Sky Keepers I', 'desc': 'Keep all birds in top 50% for 100 frames', 'unlocked': False, 'type': 'area', 'key': 'top50', 'goal': 100},
        'hold_top30_200': {'name': 'Cloud Nine I', 'desc': 'Keep all birds in top 30% for 200 frames', 'unlocked': False, 'type': 'area', 'key': 'top30', 'goal': 200},
        # Configuration synergies and complex combos (special events to be emitted)
        'synergy_adjacent_red': {'name': 'Crimson Link', 'desc': 'Trigger adjacent red synergy', 'unlocked': False, 'type': 'special', 'event': 'synergy_adjacent_red'},
        'combo_fire_suction_bounce_fire': {'name': 'Elemental Chain', 'desc': 'Perform Fire → Suction → Bounce → Fire combo', 'unlocked': False, 'type': 'special', 'event': 'combo_fire_suction_bounce_fire'},
        'combo_yellow_blue_bounce_chain': {'name': 'Fearless Flip', 'desc': 'Perform the Yellow→Blue bounce chain combo', 'unlocked': False, 'type': 'special', 'event': 'combo_yellow_blue_bounce_chain'},
    }


def add_notification(text, frame_count, notifications_list):
    """Add a short on-screen notification for a few frames."""
    try:
        frames = int(v.notification_duration_seconds / v.base_sleep)
        if frames <= 0:
            frames = 1
    except Exception:
        frames = 40
    notifications_list.append((text, frame_count + frames))


def unlock_achievement(aid, frame_count, notifications_list, firebase_client=None, background_call=None):
    """Unlock an achievement and add notification."""
    global achievements
    a = achievements.get(aid)
    if not a or a.get('unlocked'):
        return False
    a['unlocked'] = True
    add_notification(f"Achievement unlocked: {a['name']}", frame_count, notifications_list)
    
    # Try to sync/unlock achievement for remote user
    if firebase_client and background_call:
        try:
            background_call(firebase_client.unlock_achievement, aid)
        except Exception:
            pass
        try:
            background_call(firebase_client.log_event, 'achievement_unlocked', {'id': aid, 'name': a.get('name')})
        except Exception:
            pass
    return True


def on_synergy_triggered(combo, recent_powers, frame_count, random_lanes, NUM_BALLS, ball_lost, per_bird_xp, award_xp, add_notification_fn):
    """Handle a true synergy event: award the weakest participating bird 10% of the XP gap."""
    try:
        if not combo or not isinstance(combo, (set, list)):
            return None
        participants = []
        for entry in recent_powers:
            try:
                if not entry:
                    continue
                if len(entry) >= 3:
                    p, f, l = entry[0], entry[1], entry[2]
                else:
                    p, f = entry[0], entry[1]
                    l = None
                if p in combo and l is not None:
                    try:
                        if l in random_lanes:
                            bidx = random_lanes.index(l)
                        else:
                            bidx = next((i for i in range(NUM_BALLS) if random_lanes[i] == l), None)
                    except Exception:
                        bidx = None
                    if bidx is None or bidx < 0:
                        continue
                    try:
                        if ball_lost and ball_lost[bidx]:
                            continue
                    except Exception:
                        pass
                    participants.append(bidx)
            except Exception:
                continue

        participants = list(dict.fromkeys(participants))
        if len(participants) < 2:
            return None

        xp_list = []
        for b in participants:
            try:
                xp_list.append((b, int(per_bird_xp[b] or 0)))
            except Exception:
                xp_list.append((b, 0))

        try:
            strongest = max(xp_list, key=lambda t: t[1])
            weakest = min(xp_list, key=lambda t: t[1])
            gap = strongest[1] - weakest[1]
            if gap > 0:
                transfer = int(gap * SYNERGY_TRANSFER_RATIO)
                if transfer <= 0:
                    transfer = 1
                award_xp(weakest[0], transfer)
                try:
                    wlane = random_lanes[weakest[0]]
                    add_notification_fn(f"Synergy: +{transfer} XP to lane {wlane+1}")
                except Exception:
                    pass
                return transfer
        except Exception:
            return None
    except Exception:
        return None


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

    elif event == 'destroy_obstacle':
        for aid, a in achievements.items():
            if a.get('type') == 'counter' and a.get('key') == 'obstacles_destroyed' and not a.get('unlocked'):
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

        distinct = set(p for (p, f, l) in recent_powers)
        if len(distinct) >= 2:
            check_achievements_event('synergy', frame_count, notifications_list, firebase_client, background_call, combo=distinct)
        if len(distinct) >= 3:
            check_achievements_event('synergy', frame_count, notifications_list, firebase_client, background_call, combo=distinct)

        if power in ('red', 'purple'):
            append_recent_action_fn = kwargs.get('append_recent_action')
            if append_recent_action_fn:
                try:
                    append_recent_action_fn('fire', lane=lane, color=power.upper())
                except Exception:
                    pass

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

        try:
            explicit = bool(kwargs.get('explicit', False))
            if explicit and isinstance(combo, (set, list)) and len(combo) >= 2:
                on_synergy_fn = kwargs.get('on_synergy_triggered')
                if on_synergy_fn:
                    try:
                        on_synergy_fn(combo)
                    except Exception:
                        pass
        except Exception:
            pass

    elif event == 'area_hold':
        area = kwargs.get('area')
        frames = kwargs.get('frames', 0)
        for aid, a in achievements.items():
            if a.get('type') == 'area' and a.get('key') == area and not a.get('unlocked'):
                if frames >= a.get('goal', 0):
                    unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)

    elif event == 'original_survive':
        frames = kwargs.get('frames', 0)
        for aid, a in achievements.items():
            if a.get('type') == 'original' and not a.get('unlocked'):
                if frames >= a.get('goal', 0):
                    unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)

    elif event == 'color_count':
        color = kwargs.get('color')
        count = kwargs.get('count', 0)
        for aid, a in achievements.items():
            if a.get('type') == 'color_count' and a.get('key') == color and not a.get('unlocked'):
                if count >= a.get('goal', 0):
                    unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)
        if count >= 9:
            for aid, a in achievements.items():
                if a.get('type') == 'color_count_all' and not a.get('unlocked'):
                    if a.get('goal', 0) <= count:
                        unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)

    elif event == 'destroy_bat_with_orange':
        for aid, a in achievements.items():
            if a.get('type') == 'special' and a.get('event') == 'destroy_bat_with_orange' and not a.get('unlocked'):
                unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)


def append_recent_action(action, frame_count, lane=None, color=None):
    """Append an atomic action for combo detection and prune old actions."""
    global recent_actions
    recent_actions.append({'action': action, 'frame': frame_count, 'lane': lane, 'color': color})
    recent_actions[:] = [a for a in recent_actions if frame_count - a['frame'] <= v.COMBO_WINDOW_FRAMES]


def detect_combos(frame_count, notifications_list, firebase_client=None, background_call=None):
    """Look for configured combos in recent_actions and unlock achievements."""
    global recent_actions, combo_cooldowns, achievements
    now = frame_count
    
    # Prune expired cooldowns
    expired = [cid for cid, exp in combo_cooldowns.items() if now >= exp]
    for cid in expired:
        del combo_cooldowns[cid]
    
    # Fire → Suction → Bounce → Fire combo detection
    fire_actions = [a for a in recent_actions if a['action'] == 'fire']
    suction_actions = [a for a in recent_actions if a['action'] == 'suction']
    bounce_actions = [a for a in recent_actions if a['action'] == 'bounce']
    
    if len(fire_actions) >= 2 and suction_actions and bounce_actions:
        combo_id = 'combo_fire_suction_bounce_fire'
        if combo_id not in combo_cooldowns:
            for aid, a in achievements.items():
                if a.get('type') == 'special' and a.get('event') == combo_id and not a.get('unlocked'):
                    unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)
                    combo_cooldowns[combo_id] = now + 300
                    break
    
    # Yellow→Blue bounce chain combo
    yellow_bounces = [a for a in recent_actions if a['action'] == 'bounce' and a.get('color') == 'YELLOW']
    blue_speed_boosts = [a for a in recent_actions if a['action'] == 'speed_boost' and a.get('color') == 'BLUE']
    
    if yellow_bounces and blue_speed_boosts:
        combo_id = 'combo_yellow_blue_bounce_chain'
        if combo_id not in combo_cooldowns:
            for yb in yellow_bounces:
                for bb in blue_speed_boosts:
                    if abs(yb['frame'] - bb['frame']) <= v.YELLOW_BLUE_CHAIN_WINDOW:
                        for aid, a in achievements.items():
                            if a.get('type') == 'special' and a.get('event') == combo_id and not a.get('unlocked'):
                                unlock_achievement(aid, frame_count, notifications_list, firebase_client, background_call)
                                combo_cooldowns[combo_id] = now + 300
                                return
