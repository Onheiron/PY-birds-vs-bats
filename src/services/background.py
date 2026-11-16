"""Fire-and-forget background calls."""

import contextlib
import threading


def safe_call(func, *args, **kwargs):
    """Safely call a function, catching all exceptions."""
    with contextlib.suppress(Exception):
        func(*args, **kwargs)


def background_call(func, *args, **kwargs):
    """Execute function in a daemon thread; failures are silently ignored."""
    with contextlib.suppress(RuntimeError):
        threading.Thread(target=safe_call, args=(func, *args), kwargs=kwargs, daemon=True).start()
