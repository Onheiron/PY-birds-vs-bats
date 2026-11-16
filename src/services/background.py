"""Fire-and-forget background calls."""

import threading


def safe_call(func, *args, **kwargs):
    """Safely call a function, catching all exceptions."""
    try:
        func(*args, **kwargs)
    except:
        pass


def background_call(func, *args, **kwargs):
    """Execute function in background thread."""
    try:
        t = threading.Thread(target=safe_call, args=(func,) + args, kwargs=kwargs, daemon=True)
        t.start()
    except:
        pass
