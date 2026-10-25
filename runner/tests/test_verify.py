# SPDX-License-Identifier: MIT
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify import INITIAL, InvalidRecord, verify

# One public, generated legal game; reference data, not a solver implementation.
PASS_TARGET = 'XXXXOOXXXOXXOOXXXOOXXXOXXOOXXOOXXOXXXOOXXXOXOXOXXXXOOOOXXXXXOOOX'
PASS_RECORD = ['f5', 'd6', 'c3', 'g5', 'c6', 'c5', 'g6', 'b2', 'h5', 'f4', 'd3', 'b7', 'g4', 'e3', 'c2', 'c1', 'e6', 'h7', 'a1', 'a2', 'g7', 'e7', 'c7', 'h4', 'f2', 'g8', 'g3', 'e1', 'b4', 'b6', 'f7', 'f3', 'a6', 'd7', 'a8', 'a5', 'g2', 'b8', 'b5', 'h3', 'f6', 'd2', 'b1', 'h2', 'a4', 'c4', 'a3', 'h6', 'h8', 'e2', 'c8', 'b3', 'a7', 'f8', 'd1', 'pass', 'g1', 'f1', 'h1', 'pass', 'd8', 'e8']

class ReplayTests(unittest.TestCase):
    def test_empty_initial_record(self):
        self.assertEqual(verify([], INITIAL), {'moves': [], 'terminal': False, 'placements': 0, 'passes': 0})

    def test_valid_two_moves(self):
        board = list(INITIAL)
        for square in [19, 27]: board[square] = 'X'
        for square in [18, 27]: board[square] = 'O'
        result = verify(['d3', 'c3'], ''.join(board))
        self.assertEqual(result['moves'], ['d3', 'c3'])
        self.assertEqual(result['placements'], 2)
        self.assertFalse(result['terminal'])

    def test_illegal_color_switch_is_not_an_implicit_pass(self):
        board = list(INITIAL)
        for square in [19, 27, 36, 37]: board[square] = 'X'
        with self.assertRaises(InvalidRecord): verify(['d3', 'f5'], ''.join(board))

    def test_pass_with_legal_move_rejected(self):
        with self.assertRaises(InvalidRecord): verify(['pass'], INITIAL)

    def test_explicit_and_omitted_forced_passes_agree(self):
        explicit = verify(PASS_RECORD, PASS_TARGET)
        implicit = verify([m for m in PASS_RECORD if m != 'pass'], PASS_TARGET)
        self.assertEqual(explicit, implicit)
        self.assertGreater(explicit['passes'], 0)
        self.assertTrue(explicit['terminal'])
        self.assertEqual(explicit['placements'], 60)

    def test_terminal_double_pass_rejected(self):
        with self.assertRaises(InvalidRecord): verify(PASS_RECORD + ['pass', 'pass'], PASS_TARGET)

    def test_move_after_terminal_rejected(self):
        with self.assertRaises(InvalidRecord): verify(PASS_RECORD + ['a1'], PASS_TARGET)

    def test_all_target_cells_are_compared(self):
        wrong = list(PASS_TARGET)
        wrong[0] = 'O' if wrong[0] == 'X' else 'X'
        with self.assertRaises(InvalidRecord): verify(PASS_RECORD, ''.join(wrong))

    def test_occupied_square_rejected(self):
        with self.assertRaises(InvalidRecord): verify(['d3', 'd3'], INITIAL)

    def test_invalid_types_and_coordinates(self):
        for moves in ['d3', None, [19], ['D3'], ['a0'], ['i1'], [' pass ']]:
            with self.subTest(moves=moves), self.assertRaises(InvalidRecord): verify(moves, INITIAL)
        for target in [None, INITIAL[:-1], 'A' * 64]:
            with self.subTest(target=target), self.assertRaises(InvalidRecord): verify([], target)


if __name__ == '__main__': unittest.main()
