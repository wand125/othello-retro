# SPDX-License-Identifier: MIT
"""Harness fixture: return public reference records. THIS IS NOT A SOLVER."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from verify import verify


def references(path: Path) -> dict[str, list[str]]:
    bank = json.loads(path.read_text(encoding='utf-8'))
    sections = bank.get('splits', {}).values()
    cases = [case for section in sections for case in section.get('cases', [])]
    cases.extend(bank.get('cases', []))
    result: dict[str, list[str]] = {}
    for case in cases:
        if case.get('expected', 'reachable') != 'reachable' or not isinstance(case.get('reference_moves'), list):
            continue
        checked = verify(case['reference_moves'], case['board'])
        result.setdefault(case['board'], checked['moves'])
    return result


def respond(request: dict, records: dict[str, list[str]]) -> dict:
    base = {'id': request.get('id'), 'fixture': True, 'measurement_kind': 'harness-smoke-only'}
    board = request.get('board')
    if not isinstance(board, str) or len(board) != 64 or set(board) - set('XO-'):
        return {**base, 'status': 'error', 'reason': 'expected 64-cell X/O/- board'}
    if board not in records:
        return {**base, 'status': 'unknown', 'reason': 'fixture has no reference; this program does not search'}
    return {**base, 'status': 'found', 'moves': records[board]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank', type=Path, required=True)
    parser.add_argument('--mode', choices=['oneshot', 'resident'], default='oneshot')
    args = parser.parse_args()
    records = references(args.bank)
    if args.mode == 'resident':
        print(json.dumps({'event': 'ready', 'fixture': True, 'measurement_kind': 'harness-smoke-only', 'note': 'Reference lookup only; not solver performance.'}), flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError('expected JSON object')
            result = respond(request, records)
        except (ValueError, TypeError) as exc:
            result = {'status': 'error', 'reason': str(exc), 'fixture': True, 'measurement_kind': 'harness-smoke-only'}
        output = {'event': 'result', 'payload': result} if args.mode == 'resident' else result
        print(json.dumps(output), flush=True)
        if args.mode == 'oneshot':
            break


if __name__ == '__main__':
    main()
