"""Public, permanent reconstruction records; never serialize usage identities.

Firestore documents use a unique ISO UTC sort_key so pagination needs only its
standard single-field index. Static published records remain available forever.
"""
import base64
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path

COLLECTION = 'othello_retro_records'
ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FIELDS = ('id', 'title', 'board', 'moves', 'terminal', 'verification', 'source',
                 'elapsed_seconds', 'wall_seconds', 'requested_seconds', 'method',
                 'environment', 'created_at', 'started_at', 'finished_at', 'timing_note')
ID_PATTERN = re.compile(r'[A-Za-z0-9_-]{1,100}\Z')


def iso(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def verify(moves, target):
    """Independent replay, including omitted forced passes; reject invalid results."""
    if not isinstance(target, str) or not re.fullmatch('[XO-]{64}', target) or not isinstance(moves, list) or len(moves) > 120:
        raise ValueError('invalid record')
    board, side, normalized = list('---------------------------OX------XO---------------------------'), 'X', []
    def flips(square, color):
        if board[square] != '-': return []
        result, other = [], 'O' if color == 'X' else 'X'
        r0, c0 = divmod(square, 8)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if not (dr or dc): continue
                line, r, c = [], r0 + dr, c0 + dc
                while 0 <= r < 8 and 0 <= c < 8 and board[r*8+c] == other:
                    line.append(r*8+c); r += dr; c += dc
                if line and 0 <= r < 8 and 0 <= c < 8 and board[r*8+c] == color: result.extend(line)
        return result
    def can_move(color): return any(flips(square, color) for square in range(64))
    for move in moves:
        other = 'O' if side == 'X' else 'X'
        if not isinstance(move, str) or not re.fullmatch(r'(?:[a-h][1-8]|pass)', move): raise ValueError('invalid move')
        if move == 'pass':
            if can_move(side) or not can_move(other): raise ValueError('illegal pass')
            normalized.append(move); side = other; continue
        if not can_move(side) and can_move(other):
            normalized.append('pass'); side, other = other, side
        square = (int(move[1])-1)*8 + 'abcdefgh'.index(move[0])
        changed = flips(square, side)
        if not changed: raise ValueError('illegal move')
        for position in [square, *changed]: board[position] = side
        normalized.append(move); side = other
    if ''.join(board) != target: raise ValueError('target mismatch')
    return normalized, not can_move('X') and not can_move('O')


def make_record(job_id, item, result, finished_at=None, environment='Cloud Run'):
    """Return a safe document, or None for failed/invalid/non-solve results."""
    if result.get('status') != 'found' or item.get('kind', 'solve') != 'solve': return None
    if not ID_PATTERN.fullmatch(job_id): raise ValueError('invalid job id')
    request = item.get('request', {})
    try:
        moves, terminal = verify(result.get('moves'), request.get('board'))
    except ValueError:
        return None
    finished = iso(finished_at or item.get('finished_at') or dt.datetime.now(dt.timezone.utc))
    created = iso(item.get('created_at'))
    started = iso(item.get('started_at'))
    wall = max(0, (dt.datetime.fromisoformat(finished.replace('Z', '+00:00')) - dt.datetime.fromisoformat(started.replace('Z', '+00:00'))).total_seconds()) if started else None
    ident, board = 'record-' + job_id, request['board']
    digest = hashlib.sha256((board+'|'+''.join(moves)).encode()).hexdigest()
    record = {'id':ident, 'title':('終局盤面' if terminal else '途中の盤面') + f'（{64-board.count("-")}石）',
              'board':board, 'moves':moves, 'terminal':terminal,
              'verification':{'legal':True, 'target_matches':True, 'record_sha256':digest},
              'source':'reconstruction', 'elapsed_seconds':number(result.get('time')),
              'requested_seconds':number(request.get('time')), 'method':result.get('method') if isinstance(result.get('method'), str) else None,
              'environment':environment, 'created_at':created, 'started_at':started, 'finished_at':finished, 'wall_seconds':wall,
              'sort_key':finished+'_'+ident}
    return record


def public(record):
    return {key:record.get(key) for key in PUBLIC_FIELDS if key in record}


def static_records():
    path = ROOT / 'ui/public-examples.json'
    rows = json.loads(path.read_text())['examples'] if path.exists() else []
    return [{**row, 'sort_key':'0000_'+row['id']} for row in rows]


def record_ref(db, ident):
    if not ID_PATTERN.fullmatch(ident): raise ValueError('invalid record id')
    return db.collection(COLLECTION).document(ident)


def get_record(db, ident):
    if not ID_PATTERN.fullmatch(ident): return None
    published = next((row for row in static_records() if row['id'] == ident), None)
    if published: return public(published)
    snap = record_ref(db, ident).get()
    return public(snap.to_dict()) if snap.exists else None


def encode_cursor(key):
    return base64.urlsafe_b64encode(key.encode()).decode().rstrip('=')


def decode_cursor(cursor):
    if not isinstance(cursor, str) or len(cursor) > 300 or not re.fullmatch('[A-Za-z0-9_-]+', cursor): raise ValueError('invalid cursor')
    try: key = base64.urlsafe_b64decode(cursor + '='*(-len(cursor)%4)).decode()
    except (ValueError, UnicodeError) as exc: raise ValueError('invalid cursor') from exc
    if not re.fullmatch(r'(?:0000|\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z)_[A-Za-z0-9_-]+', key): raise ValueError('invalid cursor')
    return key


def list_records(db, cursor=None, limit=20):
    limit = max(1, min(int(limit), 50))
    after = decode_cursor(cursor) if cursor else None
    query = db.collection(COLLECTION).order_by('sort_key', direction='DESCENDING')
    if after:
        # Positional where is supported by Firestore and avoids a version-dependent FieldFilter import.
        query = query.where('sort_key', '<', after)
    dynamic = [snap.to_dict() for snap in query.limit(limit+1).stream()]
    # Static URLs remain available even if a migration has not copied them into DB.
    rows = {row['id']:row for row in static_records() if not after or row['sort_key'] < after}
    rows.update({row['id']:row for row in dynamic})
    selected = sorted(rows.values(), key=lambda row:row['sort_key'], reverse=True)
    page = selected[:limit]
    return {'records':[public(row) for row in page],
            'next_cursor':encode_cursor(page[-1]['sort_key']) if len(selected) > limit else None}
