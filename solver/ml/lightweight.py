# SPDX-License-Identifier: MIT
"""One inexpensive guided attempt; a miss always requires general SAT fallback.

Checkpoint architecture/weights stay unchanged. This changes the heuristic
search policy, so lower candidate cost and hit rate must be evaluated together.
"""
from pathlib import Path
import sys
import time

import search

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ui'))
sys.path.insert(0, str(ROOT / 'cloud'))
from auto_policy import incomplete_terminal
from records import verify


def handle(net, undo, req, net_passes=None, progress=None):
    started = time.monotonic()
    limit = req.get('time', 60)
    deadline = None if limit is None else started + float(limit)
    board = req['board']
    emit = progress or (lambda event: None)
    if incomplete_terminal(board):
        return {'status': 'miss', 'reason': 'incomplete_terminal_exact_route', 'policy': 'lightweight'}
    b = sum(1 << i for i, v in enumerate(board) if v == 'X')
    w = sum(1 << i for i, v in enumerate(board) if v == 'O')
    target = f'{b:016x},{w:016x}'

    def left():
        return float('inf') if deadline is None else deadline - time.monotonic()

    def accepted(moves, stage):
        try:
            normalized, _ = verify(moves, board)
        except (ValueError, KeyError):
            return None
        return {'status': 'found', 'moves': normalized, 'stage': stage, 'policy': 'lightweight'}

    if left() < 2:
        return {'status': 'miss', 'reason': 'model_budget', 'policy': 'lightweight'}
    emit({'stage': 'pass_check', 'message': '短いSAT探索で手順を確認しています', 'device': search.DEV})
    probe = search.findany([target], min(2, int(left())) if deadline else 2)
    if probe.get('index') is not None:
        result = accepted(probe['moves'], 'direct')
        if result:
            return result
    if left() < 5:
        return {'status': 'miss', 'reason': 'model_budget', 'policy': 'lightweight'}
    passes = bool(probe.get('unsat'))
    stage = 'with-passes' if passes else 'fast'
    model = net_passes if passes and net_passes is not None else net
    emit({'stage': 'beam_' + stage, 'message': '少数の候補を学習モデルで評価しています', 'device': search.DEV})
    try:
        candidates = search.beam(model, undo, target, 16, cap=4, stop=30, nsym=1, refine=0,
            passes=passes, deadline=None if deadline is None else deadline - 2,
            progress=lambda event: emit({'stage': 'beam_' + stage, 'device': search.DEV, **event}))
    except search.SearchBudgetExpired:
        return {'status': 'miss', 'reason': 'model_budget', 'policy': 'lightweight'}
    for index in range(0, min(len(candidates), 18), 6):
        if left() < 2:
            break
        chunk = candidates[index:index+6]
        emit({'stage': 'candidate_sat', 'message': '候補から合法な棋譜を確認しています', 'device': search.DEV,
              'tested': index, 'total_candidates': len(candidates)})
        result = search.findany([c for c, _ in chunk], 20 if deadline is None else min(20, int(left())))
        if result.get('index') is not None:
            found = accepted(result['moves'] + chunk[result['index']][1], stage)
            if found:
                return found
    return {'status': 'miss', 'reason': 'lightweight_candidates_exhausted', 'policy': 'lightweight'}
