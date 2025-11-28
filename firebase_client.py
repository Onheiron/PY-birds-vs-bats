# Minimal firebase-admin helper for BVB game
# No triple-quoted module docstring to avoid parser issues.
from typing import Optional, Dict, Any
import os
import time
import uuid

# module state
_app = None
_db = None
_user_id: Optional[str] = None
_service_account_path: Optional[str] = None

# Hard-coded Firebase project/app name as requested
DEFAULT_PROJECT = 'birds-vs-bats'
DEFAULT_DB = 'birds-vs-bats'


def _id_file() -> str:
    return os.path.join(os.path.dirname(__file__), 'firebase_user_id.txt')


def get_or_create_local_user_id() -> str:
    global _user_id
    if _user_id:
        return _user_id
    path = _id_file()
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                _user_id = f.read().strip()
                if _user_id:
                    return _user_id
        _user_id = str(uuid.uuid4())
        with open(path, 'w') as f:
            f.write(_user_id)
        return _user_id
    except Exception:
        _user_id = str(uuid.uuid4())
        return _user_id


def init_from_env(service_account_path: Optional[str] = None) -> bool:
    # initialise firebase-admin and firestore client
    # This function prefers a service account JSON if present next to the
    # module, otherwise it will attempt to initialize with the default
    # application credentials using the hard-coded project id.
    global _app, _db, _service_account_path
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except Exception as e:
        # firebase-admin not installed; bail out
        return False

    repo_root = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if service_account_path:
        candidates.append(service_account_path)
    # do NOT require environment variables per user's request - only look for
    # common filenames next to this module
    for name in ('serviceAccountKey.json', 'service-account.json', 'firebase-adminsdk.json', 'serviceAccount.json'):
        candidates.append(os.path.join(repo_root, name))

    found = None
    for p in candidates:
        if p and os.path.exists(p):
            found = p
            break

    try:
        import firebase_admin as _fa
        if found:
            # If we found a service account, initialise with it and the
            # requested project id so Firestore uses the correct project.
            cred = credentials.Certificate(found)
            if not getattr(_fa, '_apps', None):
                _app = firebase_admin.initialize_app(cred, options={'projectId': DEFAULT_PROJECT})
            else:
                _app = list(_fa._apps.values())[0]
            _db = firestore.client()
        else:
            # No service account found. Try to initialize app with just the
            # project id (this will work if ADC are available in the
            # runtime). We do not raise here; functions will be best-effort.
            if not getattr(_fa, '_apps', None):
                _app = firebase_admin.initialize_app(options={'projectId': DEFAULT_PROJECT})
            else:
                _app = list(_fa._apps.values())[0]
            try:
                _db = firestore.client()
            except Exception:
                _db = None

        _service_account_path = found
        # ensure stable local id
        get_or_create_local_user_id()
        return True
    except Exception:
        # best-effort: don't crash importers; leave _db possibly None
        _db = None
        return False


def sign_in_anonymous():
    """Ensure a Firebase Auth user exists for this install and return (firebase_uid, local_id).

    Behavior:
    - Initializes the client if needed (best-effort).
    - Uses the local stable id as the desired Firebase UID. If a user with that
      UID exists, returns it. If not, attempts to create one via the admin SDK.
    - Falls back to (None, local_id) if auth/admin SDK is not available or any
      operation fails.
    """
    global _db
    if _db is None:
        try:
            init_from_env()
        except Exception:
            pass

    local_id = get_or_create_local_user_id()

    try:
        # Import auth lazily so module-level import remains cheap when firebase-admin
        # isn't installed.
        from firebase_admin import auth
    except Exception:
        # Admin SDK auth not available
        return None, local_id

    try:
        # Try to look up a user with the local id as UID; if not found, create one.
        try:
            user = auth.get_user(local_id)
        except Exception:
            # Create a minimal user record using the local id as UID so the user
            # becomes visible in the Firebase Auth console.
            try:
                user = auth.create_user(uid=local_id)
            except Exception:
                user = None

        if user:
            return user.uid, local_id
    except Exception:
        # Any error - fall back to returning only the local id
        pass

    return None, local_id


def send_score(name: str, score: int, time_played_seconds: Optional[int] = None, time_played: Optional[str] = None, version: Optional[str] = None, avg_ppm: Optional[float] = None) -> Optional[Dict[str, Any]]:
    global _db
    if _db is None:
        # best-effort: do nothing if Firestore client not available
        return None
    try:
        # Create a new leaderboard document for every submission (append mode).
        # We still store a stable local user id in the payload so entries can be
        # grouped or filtered by user, but we do NOT upsert by uid anymore.
        uid = get_or_create_local_user_id()
        doc_ref = _db.collection('leaderboard').document()
        payload = {'name': name, 'score': int(score), 'userId': uid, 'ts': int(time.time())}
        # Attach optional play time information if provided
        try:
            if time_played_seconds is not None:
                payload['time_played_seconds'] = int(time_played_seconds)
        except Exception:
            pass
        try:
            if time_played is not None:
                payload['time_played'] = str(time_played)
        except Exception:
            pass
        # Optional version and average points-per-minute
        try:
            if version is not None:
                payload['version'] = str(version)
        except Exception:
            pass
        try:
            if avg_ppm is not None:
                # store as float (rounded to 3 decimals to save space)
                payload['avg_ppm'] = float(round(float(avg_ppm), 3))
        except Exception:
            pass
        # set() with the uid as document id performs an upsert (create or replace)
        doc_ref.set(payload)
        return {'id': doc_ref.id, **payload}
    except Exception:
        return None


def get_leaderboard(limit: int = 10):
    global _db
    if _db is None:
        return []
    try:
        docs = _db.collection('leaderboard').order_by('score', direction='DESCENDING').limit(limit).stream()
        entries = []
        for d in docs:
            data = d.to_dict() or {}
            entries.append({
                'id': d.id,
                'name': data.get('name'),
                'score': int(data.get('score', 0)),
                'ts': data.get('ts'),
                'time_played_seconds': int(data.get('time_played_seconds')) if data.get('time_played_seconds') is not None else None,
                'time_played': data.get('time_played')
            })
        return entries
    except Exception:
        return []


def unlock_achievement(achievement_id: str) -> bool:
    global _db
    if _db is None:
        return False
    try:
        uid = get_or_create_local_user_id()
        doc_ref = _db.collection('users').document(uid).collection('achievements').document(achievement_id)
        # Try to create the doc atomically: create() will succeed only if the
        # document does not exist. This avoids a race where two clients both
        # read 'missing' and then both write.
        payload = {'unlocked': True, 'ts': int(time.time())}
        try:
            # create() raises AlreadyExists if the document is present
            doc_ref.create(payload)
            return True
        except Exception as e:
            # If the error is an AlreadyExists from the API, treat as already unlocked
            try:
                from google.api_core.exceptions import AlreadyExists
                if isinstance(e, AlreadyExists):
                    return False
            except Exception:
                # If we can't import the exception type, fall through to checks
                pass

            # Fallback: attempt a read; if unlocked, skip writing. Otherwise try set.
            try:
                existing = doc_ref.get()
                if existing.exists:
                    data = existing.to_dict() or {}
                    if data.get('unlocked'):
                        return False
            except Exception:
                # read failed (offline/permissions) — we'll attempt the write as a best-effort
                pass

            try:
                doc_ref.set(payload)
                return True
            except Exception:
                return False
    except Exception:
        return False


def sync_achievements(achievements: Dict[str, Any]):
    for aid, a in (achievements or {}).items():
        try:
            if a.get('unlocked'):
                try:
                    unlock_achievement(aid)
                except Exception:
                    pass
        except Exception:
            continue


def log_event(name: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    global _db
    if _db is None:
        return None
    try:
        payload = {'name': name, 'params': params or {}, 'ts': int(time.time()), 'userId': get_or_create_local_user_id()}
        doc_ref = _db.collection('events').document()
        doc_ref.set(payload)
        return {'id': doc_ref.id, **payload}
    except Exception:
        return None


def report_crash(stack_text: str) -> None:
    global _db
    try:
        if _db is None:
            return
        payload = {'stack': stack_text, 'ts': int(time.time()), 'userId': get_or_create_local_user_id()}
        doc_ref = _db.collection('crashes').document()
        doc_ref.set(payload)
    except Exception:
        return

