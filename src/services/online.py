"""Online: an anonymous account, sending finished games, reading the leaderboards (Firebase).

Only the public web key of the Firebase project is in the game (``online`` in
config.yml); nothing here can write a score. How it works:

- **Account**: the first time, Firebase Auth makes an anonymous user (an uid);
  its refresh token is kept in ~/.bvb/account.json and gives a fresh ID token
  (valid one hour) at every start. No password, no e-mail.
- **Sending a game**: at game over the recording of the game (seed, version,
  every key: src/engine/recorder.py) goes to Firestore as a *submission*,
  its bytes cut in ``parts`` of at most PART_BYTES. The rules
  (firestore.rules) let a player only add submissions and parts with their
  own uid, and set their own name in ``players``.
- **Verification**: a GitHub Actions workflow (tools/verify_runs.py, every 15
  minutes) replays every new submission with the code of its version; only
  the games whose replay ends with the score sent enter the leaderboards.
- **Leaderboards**: documents ``boards/<period>-<difficulty>`` (period: all,
  month-YYYY-MM, week-YYYY-Www) with the best runs, written by the verifier
  only; everyone can read them.

Every call is made in the background (src/services/background.py) and fails
quietly: offline, the game plays as usual. ``disabled`` (the simulator, the
bot, the tests) or SETTINGS > ONLINE off stop all of it.
"""

import base64
import datetime
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from src import __version__
from src.core import constants, state

PART_BYTES = 700_000  # bytes of a recording per Firestore document (the limit is 1 MiB)
TIMEOUT = 15
BOARD_TTL = 120  # seconds a leaderboard read is kept
PERIODS = ('week', 'month', 'all')
PERIOD_NAMES = {'week': 'THIS WEEK', 'month': 'THIS MONTH', 'all': 'ALL TIME'}

disabled = bool(os.environ.get('BVB_OFFLINE'))  # set by the simulator, the bot and the tests
_lock = threading.Lock()
_token = {'id': None, 'expires': 0.0}
_boards = {}  # board id -> (time read, entries or None)
last_status = None  # what happened to the last game sent (shown at game over)


def _cfg():
    node = getattr(constants, 'online', None)
    return node if isinstance(node, dict) else vars(node) if node is not None else {}


def _firebase():
    node = _cfg().get('firebase')
    return node if isinstance(node, dict) else vars(node) if node is not None else {}


def enabled():
    cfg = _cfg()
    return (
        not disabled
        and bool(cfg.get('enabled', False))
        and bool(_firebase().get('api_key'))
        and getattr(state.settings, 'online_enabled', True)
    )


def _project():
    return _firebase().get('project_id', '')


def _docs_url(path=''):
    return f'https://firestore.googleapis.com/v1/projects/{_project()}/databases/(default)/documents{path}'


def _account_file():
    from src.services.save_manager import SAVE_DIR_NAME

    return Path.home() / SAVE_DIR_NAME / 'account.json'


def _request(url, body=None, token=None, form=False, method=None):
    headers = {'User-Agent': f'BVB/{__version__}'}
    data = None
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        else:
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = f'Bearer {token}'
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    from src.services import net

    with net.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read() or b'{}')


# --------------------------------------------------------------------------- the account


def account():
    """{'uid', 'refresh_token'} of this player, or None before the first sign-in."""
    try:
        return json.loads(_account_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _save_account(uid, refresh_token):
    path = _account_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'uid': uid, 'refresh_token': refresh_token}), encoding='utf-8')


def id_token():
    """A valid Firebase ID token for this player (signing in anonymously the first time)."""
    with _lock:
        if _token['id'] and time.time() < _token['expires'] - 60:
            return _token['id']
        key = _firebase()['api_key']
        known = account()
        if known:
            reply = _request(
                f'https://securetoken.googleapis.com/v1/token?key={key}',
                {'grant_type': 'refresh_token', 'refresh_token': known['refresh_token']},
                form=True,
            )
            token, uid, refresh, expires = (
                reply['id_token'],
                reply['user_id'],
                reply['refresh_token'],
                reply['expires_in'],
            )
        else:
            reply = _request(
                f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={key}', {'returnSecureToken': True}
            )
            token, uid, refresh, expires = reply['idToken'], reply['localId'], reply['refreshToken'], reply['expiresIn']
        _save_account(uid, refresh)
        _token.update(id=token, expires=time.time() + int(expires))
        return token


# --------------------------------------------------------------------------- Firestore values


def _value(v):
    if isinstance(v, bool):
        return {'booleanValue': v}
    if isinstance(v, int):
        return {'integerValue': str(v)}
    if isinstance(v, float):
        return {'doubleValue': v}
    if isinstance(v, bytes):
        return {'bytesValue': base64.b64encode(v).decode()}
    if isinstance(v, dict):
        return {'mapValue': {'fields': {k: _value(x) for k, x in v.items()}}}
    if isinstance(v, list | tuple):
        return {'arrayValue': {'values': [_value(x) for x in v]}}
    if v is None:
        return {'nullValue': None}
    return {'stringValue': str(v)}


def _plain(v):
    """A Firestore value as plain Python."""
    if 'mapValue' in v:
        return {k: _plain(x) for k, x in v['mapValue'].get('fields', {}).items()}
    if 'arrayValue' in v:
        return [_plain(x) for x in v['arrayValue'].get('values', [])]
    if 'integerValue' in v:
        return int(v['integerValue'])
    for kind in ('stringValue', 'doubleValue', 'booleanValue', 'timestampValue'):
        if kind in v:
            return v[kind]
    return None


def _fields(data):
    return {'fields': {k: _value(v) for k, v in data.items()}}


# --------------------------------------------------------------------------- sending a game


def submission(recording_path, name):
    """(document, [parts]) of a finished game: the recording's bytes cut in parts."""
    raw = Path(recording_path).read_bytes()  # the recording as saved: gzip of JSON
    parts = [raw[i : i + PART_BYTES] for i in range(0, len(raw), PART_BYTES)] or [b'']
    game = state.game
    document = {
        'name': (name or 'Anonymous').strip()[:20],
        'version': __version__,
        'difficulty': int(state.settings.difficulty),
        'score': int(game.score),
        'level': int(game.level),
        'parts': len(parts),
        'status': 'pending',
    }
    return document, parts


def send_game(recording_path, name):
    """Send a finished game for verification (background thread); quiet when offline."""
    global last_status
    if not enabled() or not recording_path:
        return False
    try:
        token = id_token()
        uid = account()['uid']
        document, parts = submission(recording_path, name)
        document['uid'] = uid
        sid = f'{uid}-{int(time.time() * 1000)}'
        for n, chunk in enumerate(parts):
            _request(
                _docs_url(f'/parts?documentId={sid}-{n}'),
                _fields({'uid': uid, 'submission': sid, 'n': n, 'data': chunk}),
                token,
            )
        _request(_docs_url(f'/submissions?documentId={sid}'), _fields(document), token)
        if name and name.strip():
            _request(_docs_url(f'/players/{uid}'), _fields({'name': name.strip()[:20]}), token, method='PATCH')
        last_status = 'sent: on the leaderboards once verified (a few minutes)'
        return True
    except (urllib.error.URLError, OSError, KeyError, ValueError) as error:
        last_status = f'not sent ({type(error).__name__}): offline?'
        return False


# --------------------------------------------------------------------------- leaderboards


def board_id(period, difficulty, when=None):
    """The document of a leaderboard: <period>-<difficulty>, e.g. week-2026-W48-adventure."""
    when = when or datetime.datetime.now(datetime.timezone.utc)
    name = ('PEACEFUL', 'ADVENTURE', 'SURVIVAL', 'LEGENDARY')[max(0, min(3, int(difficulty)))].lower()
    if period == 'week':
        year, week, _day = when.isocalendar()
        return f'week-{year}-W{week:02d}-{name}'
    if period == 'month':
        return f'month-{when.year}-{when.month:02d}-{name}'
    return f'all-{name}'


def board(period, difficulty=None):
    """The entries of a leaderboard ([{name, score, level, ...}], best first); None while not read,
    'offline' when it cannot be read. Reads in the background and keeps it BOARD_TTL seconds."""
    if difficulty is None:
        difficulty = state.settings.difficulty
    bid = board_id(period, difficulty)
    read_at, entries = _boards.get(bid, (0, None))
    if time.time() - read_at > BOARD_TTL and enabled():
        _boards[bid] = (time.time(), entries)
        threading.Thread(target=_read_board, args=(bid,), daemon=True).start()
    if not enabled():
        return 'offline'
    return entries


def _read_board(bid):
    try:
        doc = _request(_docs_url(f'/boards/{bid}'))
        entries = _plain({'mapValue': {'fields': doc.get('fields', {})}}).get('entries', [])
    except urllib.error.HTTPError as error:
        entries = [] if error.code == 404 else 'offline'  # 404: nobody on it yet
    except (urllib.error.URLError, OSError, ValueError):
        entries = 'offline'
    _boards[bid] = (time.time(), entries)
