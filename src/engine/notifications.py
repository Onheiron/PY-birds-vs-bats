"""On-screen notification cards."""

from src.core import constants, state


def notify(text, duration_frames=None, title=None):
    """Add a notification to display in right panel.

    Args:
        text: Main notification text
        duration_frames: How long to display (defaults to config value)
        title: Optional title for the card (e.g., "Achievement:", "Power-Up:")
    """
    if duration_frames is None:
        try:
            duration_seconds = constants.notifications.duration_seconds
        except AttributeError:
            duration_seconds = 3.0
        duration_frames = int(duration_seconds / constants.timing.base_sleep)

    expire_frame = state.game.frame_count + duration_frames

    # New notification format: dict with title, text, expire_frame
    notification = {'title': title or '', 'text': text, 'expire_frame': expire_frame}

    # Insert at beginning (top of stack)
    state.ui.notifications.insert(0, notification)

    # Limit stack size (remove from bottom)
    try:
        max_stack = constants.notifications.max_stack
    except AttributeError:
        max_stack = 3

    while len(state.ui.notifications) > max_stack:
        state.ui.notifications.pop()  # Remove oldest (bottom)
