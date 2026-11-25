"""Sound facade: every call is a safe no-op when the audio backend is missing.

The real backend (src.services.audio) needs numpy and pygame-ce (SDL audio,
in requirements.txt). Game code talks to this module only, so it never has to
check whether audio is available; ``unavailable_reason()`` says why it is not.
"""

from src.core import constants, state
from src.entities.bird_types import get_bird_type_by_color

_why = None
try:
    from src.services import audio as _backend

    if not _backend.is_audio_available():
        _why = _backend.unavailable_reason()
        _backend = None
except (ImportError, OSError) as error:
    _why = str(error)
    _backend = None
_told = False

_last_bird_sync_frame = 0
_last_bird_set = None


def get_audio():
    """Return the audio backend module, or None when audio is unavailable."""
    return _backend


def unavailable_reason():
    """Why there is no audio (None if there is)."""
    return None if _backend is not None else (_why or 'unknown reason')


def _tell_once():
    """No audio: say why once, on the first game of the session."""
    global _told
    if _backend is None and not _told:
        _told = True
        from src.engine.notifications import notify

        notify(f'No audio: {unavailable_reason()}', duration_frames=200)


def play_sfx(name):
    """Play a sound effect if audio is available and SFX is enabled."""
    if _backend is not None and state.settings.sfx_enabled:
        _backend.play_sfx(name)


def apply_music_setting():
    """Start or stop the music according to the music setting."""
    if _backend is None:
        return
    if not state.settings.music_enabled:
        _backend.stop_music()
    elif state.ui.show_title:
        _backend.play_screen('title')
    else:
        _backend.start_music()


def play_screen_music(name):
    """The music of a screen: 'title' (title and its menus) or 'game_over'."""
    if _backend is not None and state.settings.music_enabled:
        _backend.play_screen(name)


def start_session_music():
    """Restart the music for a new session, in sync with biome, gear and flock."""
    if _backend is None:
        _tell_once()
        return
    _backend.stop_music()
    if state.settings.music_enabled:
        _backend.update_music_for_biome(state.game.level_group)
        # Higher gear = faster tempo
        _backend.update_tempo_for_gear(state.game.speed)
        # Sync the flock before starting so the first bars already match it
        sync_active_birds(force=True)
        _backend.start_music()


def follow_pause(paused):
    """The music holds while the game is paused (run every frame: it acts on changes only)."""
    if _backend is not None:
        _backend.pause_music(paused)


def stop_music():
    """Stop the music (the mixer keeps running for sound effects)."""
    if _backend is not None:
        _backend.stop_music()


def cleanup():
    """Shut the audio backend down."""
    if _backend is not None:
        _backend.cleanup()


def sync_active_birds(force=False):
    """Tell the dynamic music which bird types are alive.

    Runs at most once every ``timing.audio_sync_interval`` game frames unless
    ``force`` is set (used at game start).
    """
    global _last_bird_sync_frame, _last_bird_set

    if _backend is None:
        return

    audio_sync_interval = getattr(constants.timing, 'audio_sync_interval', 60)
    if not force and state.game.frame_count - _last_bird_sync_frame < audio_sync_interval:
        return
    _last_bird_sync_frame = state.game.frame_count

    # How many birds of each type, and the bats on screen: the music follows both
    counts = {}
    for color, lost in zip(state.birds.colors, state.birds.lost):
        if not lost:
            bird_type = get_bird_type_by_color(color)
            if bird_type:
                counts[bird_type] = counts.get(bird_type, 0) + 1
    bats = len(state.enemies.bats) + len(state.enemies.mini_bats)

    boss = _boss_now()

    # Only update if something changed (or force)
    if force or (counts, bats, boss) != _last_bird_set:
        _last_bird_set = (counts, bats, boss)
        _backend.update_active_birds(counts)
        _backend.update_bats(bats)
        _backend.update_boss(*boss)


def boss_health(boss):
    """How much of its health a boss has left, 0..1 (the Tree: its branches')."""
    if boss.get('boss_type') == 'tree':
        branches = boss.get('branches') or []
        top = sum(b.get('max_hp', 0) for b in branches)
        left = sum(max(0, b.get('hp', 0)) for b in branches if not b.get('destroyed'))
        return left / top if top else 1.0
    top = boss.get('max_hp') or 0
    return max(0.0, boss.get('hp', 0)) / top if top else 1.0


def _boss_now():
    """(boss type, health step) of the boss fought now, or (None, 0)."""
    from src.services.music import boss as boss_music

    boss = state.enemies.boss
    if boss is None or state.enemies.boss_defeated:
        return None, 0
    return boss.get('boss_type', 'normal'), boss_music.health_step(boss_health(boss))


# =============================================================================
# EVENT SUBSCRIPTIONS
# =============================================================================

_SOUND_FOR_EVENT = {
    'bat_killed': 'bat_death',
    'mini_bat_killed': 'bat_death',
    'bird_lost': 'bird_lost',
    'level_up': 'level_up',
    'swap': 'swap',
}


def _sound_for(event):
    name = _SOUND_FOR_EVENT[event]
    return lambda **_fields: play_sfx(name)


def _on_loot_collected(loot, bird):
    play_sfx('egg' if '_egg' in loot['type'] else 'powerup')


def _on_choice_made(offer=None, card=None, **_fields):
    skipped = card is not None and card.get('id') in ('skip', 'refuse')
    play_sfx('menu_back' if skipped else 'card_take')


def menu_key(key):
    """The little sounds of menus and choices: moving, selecting, going back."""
    if key in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
        play_sfx('menu_move')
    elif key == 'ENTER':
        play_sfx('menu_select')
    elif key == 'ESC':
        play_sfx('menu_back')


def subscribe():
    """Play sound effects for game events."""
    from src.engine import events

    for event in _SOUND_FOR_EVENT:
        events.on(event, _sound_for(event))
    events.on('loot_collected', _on_loot_collected)
    events.on('choice_made', _on_choice_made)
