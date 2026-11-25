"""Online leaderboards: what is sent, the leaderboard names, the pages (no network: BVB_OFFLINE)."""

import datetime
import gzip
import json

from src.services import online
from src.ui import pages
from tests.harness import Simulation


def test_values_go_to_firestore_and_back():
    data = {'name': 'Bob', 'score': 12, 'ok': True, 'parts': [1, 2], 'x': {'y': 1.5}}
    fields = online._fields(data)['fields']
    assert fields['score'] == {'integerValue': '12'}
    assert online._plain({'mapValue': {'fields': fields}}) == data
    assert online._value(b'\x00\x01') == {'bytesValue': 'AAE='}


def test_a_game_is_cut_in_parts(tmp_path, monkeypatch):
    monkeypatch.setattr(online, 'PART_BYTES', 10)
    path = tmp_path / 'game.json.gz'
    path.write_bytes(gzip.compress(json.dumps({'keys': list(range(50))}).encode()))
    with Simulation(seed=1, key_rate=0):
        document, parts = online.submission(path, '  Ann  ')
    assert b''.join(parts) == path.read_bytes() and document['parts'] == len(parts) > 1
    assert document['status'] == 'pending' and document['name'] == 'Ann'


def test_leaderboard_names_and_pages(monkeypatch):
    when = datetime.datetime(2026, 11, 25, tzinfo=datetime.timezone.utc)
    assert online.board_id('week', 1, when) == 'week-2026-W48-adventure'
    assert online.board_id('month', 3, when) == 'month-2026-11-legendary'
    assert online.board_id('all', 0, when) == 'all-peaceful'
    assert not online.enabled()  # the tests never go online
    with Simulation(seed=1, key_rate=0):
        assert 'Offline' in pages.leaderboard_page('week')['lines'][0]
        monkeypatch.setattr(online, 'board', lambda period: [{'uid': 'u', 'name': 'Ann', 'score': 1234, 'level': 7}])
        lines = pages.leaderboard_page('all')['lines']
        assert 'Ann' in lines[1] and '1,234' in lines[1]
