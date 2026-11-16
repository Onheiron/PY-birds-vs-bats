"""Optional Firebase client: None when firebase-admin is not installed."""

try:
    from src.services import firebase_client
except ImportError:
    firebase_client = None


def close_firebase():
    """Release any connection the Firebase client keeps open."""
    if not firebase_client:
        return
    for attr in ('close', 'session', 'pool', 'requests_session'):
        obj = getattr(firebase_client, attr, None)
        try:
            if callable(obj):
                obj()
            elif obj and hasattr(obj, 'close'):
                obj.close()
        except Exception:
            pass
