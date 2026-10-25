# SPDX-License-Identifier: MIT
"""Rule fixtures and strict-witness rejection for the lightweight policy."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('OTHELLO_DEVICE', 'cpu')
sys.path[:0] = [str(ROOT / 'ui'), str(ROOT / 'ml')]
from auto_policy import incomplete_terminal


class RoutingRules(unittest.TestCase):
    def test_all_frozen_reference_positions(self):
        for suite in ['midgame', 'endgame']:
            bank = json.loads((ROOT / 'benchmarks' / f'study-{suite}-cpu222-unbounded-v1.json').read_text())
            for case in bank['splits']['main']['cases']:
                expected = bool(case['terminal'] and '-' in case['board'])
                self.assertEqual(incomplete_terminal(case['board']), expected, case['id'])

    def test_full_board_is_not_incomplete(self):
        self.assertFalse(incomplete_terminal('X' * 64))

    def test_server_skips_worker_startup_on_incomplete_terminal(self):
        import server
        bank = json.loads((ROOT / 'benchmarks/study-endgame-cpu222-unbounded-v1.json').read_text())
        case = next(c for c in bank['splits']['main']['cases'] if '-' in c['board'])
        captured = []
        runner = SimpleNamespace(finish_job=lambda job, result: captured.append(result))
        proc = SimpleNamespace(returncode=0,
            communicate=lambda *a, **kw: (json.dumps({'status': 'found', 'moves': case['reference_moves']}), ''))
        with patch.dict(os.environ, {'RETRO_AUTO_POLICY': 'lightweight'}), patch.object(server.WORKER, 'solve', side_effect=AssertionError('unexpected model startup')) as model, patch.object(server.subprocess, 'Popen', return_value=proc):
            server.Handler.run_solver(runner, case['board'], 60, 'routing-test')
        model.assert_not_called()
        self.assertEqual(captured[0]['status'], 'found')
        self.assertEqual(captured[0]['method'], 'sat')

    def test_invalid_input_rejected(self):
        for value in [None, 'X' * 63, '?' * 64]:
            with self.assertRaises(ValueError):
                incomplete_terminal(value)


class GuidedSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import lightweight
        cls.light = lightweight
        bank = json.loads((ROOT / 'benchmarks/study-midgame-cpu222-unbounded-v1.json').read_text())
        cls.case = next(c for c in bank['splits']['main']['cases'] if c['stones'] == 44)
        b = sum(1 << i for i, v in enumerate(cls.case['board']) if v == 'X')
        w = sum(1 << i for i, v in enumerate(cls.case['board']) if v == 'O')
        cls.hex = f'{b:016x},{w:016x}'

    def test_incomplete_terminal_uses_no_guided_calls(self):
        bank = json.loads((ROOT / 'benchmarks/study-endgame-cpu222-unbounded-v1.json').read_text())
        case = next(c for c in bank['splits']['main']['cases'] if '-' in c['board'])
        with patch.object(self.light.search, 'findany') as sat, patch.object(self.light.search, 'beam') as beam:
            result = self.light.handle(None, None, {'board': case['board'], 'time': None})
        self.assertEqual(result['reason'], 'incomplete_terminal_exact_route')
        sat.assert_not_called()
        beam.assert_not_called()

    def test_accepts_a_strictly_valid_witness(self):
        with patch.object(self.light.search, 'findany', return_value={'index': 0, 'moves': self.case['reference_moves']}):
            result = self.light.handle(None, None, {'board': self.case['board'], 'time': None})
        self.assertEqual(result['status'], 'found')
        self.assertEqual(result['stage'], 'direct')

    def test_invalid_voluntary_pass_never_counts_as_hit(self):
        with patch.object(self.light.search, 'findany', return_value={'index': 0, 'moves': ['pass'] + self.case['reference_moves']}), patch.object(self.light.search, 'beam', return_value=[]):
            result = self.light.handle(None, None, {'board': self.case['board'], 'time': None})
        self.assertEqual(result['status'], 'miss')

    def test_no_candidate_leaves_the_exact_fallback_available(self):
        with patch.object(self.light.search, 'findany', return_value={'index': None, 'unsat': False}), patch.object(self.light.search, 'beam', return_value=[]):
            result = self.light.handle(None, None, {'board': self.case['board'], 'time': None})
        self.assertEqual(result['status'], 'miss')
        self.assertEqual(result['reason'], 'lightweight_candidates_exhausted')


if __name__ == '__main__':
    unittest.main()
