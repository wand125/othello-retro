# SPDX-License-Identifier: MIT
"""Regeneration must detect changed inputs even when their hashes are resealed."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'runner'))
from check_generation import (GenerationMismatch, OPENING, check_files, digest,
                              legal_placements, regenerate_game, validate_bank)

MID = ROOT / 'benchmarks/study-midgame-cpu222-unbounded-v1.json'
END = ROOT / 'benchmarks/study-endgame-cpu222-unbounded-v1.json'


def reseal(bank):
    bank['protocol_sha256'] = digest(bank['protocol'])
    for section in bank['splits'].values():
        for case in section['cases']:
            case['reference_sha256'] = digest({'board': case['board'], 'moves': case['reference_moves']})
        section['cases_sha256'] = digest(section['cases'])
        section['schedule_sha256'] = digest(section['schedule'])
    return bank


class GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mid = json.loads(MID.read_text())
        cls.end = json.loads(END.read_text())

    def test_every_published_case_and_schedule(self):
        result = check_files([MID, END])
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['cases_regenerated'], 430)
        self.assertTrue(result['cross_bank_disjointness'].startswith('passed:'))
        end = result['banks'][1]
        self.assertFalse(end['private_pool_random_selection_verified'])
        self.assertTrue(end['limitations'])
        self.assertEqual(end['schedule_rows_regenerated'], 120)

    def test_initial_legal_square_order(self):
        self.assertEqual([square for square, _ in legal_placements(list(OPENING), 'X')], [19, 26, 37, 44])
        self.assertEqual(regenerate_game(123, 4),
                         {'board': OPENING, 'moves': [], 'terminal': False, 'stones': 4})

    def test_changed_seed_rejected_even_with_updated_hashes(self):
        bank = copy.deepcopy(self.mid)
        case = bank['splits']['pilot']['cases'][0]
        case['seed'] += 99
        case['id'] = 'pilot-n12-s' + str(case['seed'])
        with self.assertRaisesRegex(GenerationMismatch, 'seed rule or accepted candidate order'):
            validate_bank(reseal(bank))

    def test_changed_reference_rejected_even_with_updated_hashes(self):
        bank = copy.deepcopy(self.mid)
        bank['splits']['pilot']['cases'][0]['reference_moves'][0] = 'd3'
        with self.assertRaisesRegex(GenerationMismatch, 'reference record mismatch'):
            validate_bank(reseal(bank))

    def test_changed_schedule_rejected_even_with_updated_hashes(self):
        bank = copy.deepcopy(self.mid)
        rows = bank['splits']['pilot']['schedule']
        rows[0], rows[1] = rows[1], rows[0]
        with self.assertRaisesRegex(GenerationMismatch, 'regenerated schedule mismatch'):
            validate_bank(reseal(bank))

    def test_fabricated_rejected_seed_is_not_accepted(self):
        bank = copy.deepcopy(self.mid)
        case = bank['splits']['pilot']['cases'][0]
        bank['splits']['pilot']['rejected_generation_seeds'].append({
            'seed': case['seed'], 'requested_stones': 12,
            'reason': 'terminal before or at requested stone count'})
        with self.assertRaisesRegex(GenerationMismatch, 'rejected seeds'):
            validate_bank(reseal(bank))

    def test_endgame_schedule_rejected_with_resealed_hashes(self):
        bank = copy.deepcopy(self.end)
        rows = bank['splits']['main']['schedule']
        rows[0], rows[1] = rows[1], rows[0]
        with self.assertRaisesRegex(GenerationMismatch, 'regenerated schedule mismatch'):
            validate_bank(reseal(bank))

    def test_endgame_terminal_flag_rejected_with_resealed_hashes(self):
        bank = copy.deepcopy(self.end)
        bank['splits']['main']['cases'][0]['terminal'] = False
        with self.assertRaisesRegex(GenerationMismatch, 'terminal flag mismatch'):
            validate_bank(reseal(bank))


if __name__ == '__main__':
    unittest.main()
