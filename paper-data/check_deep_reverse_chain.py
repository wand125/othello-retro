#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 wand125 and contributors.
"""Check a recorded reverse-chain example without a solver or model.

Array-only Othello rules, occupancy closure, initial-disc invariants and suffix
composition are implemented here. No solver/retro implementation is imported.
UNSAT is an existing recorded solver outcome, not a newly checked DRAT proof.
"""
import argparse
import hashlib
import json
from pathlib import Path

INITIAL = '---------------------------OX------XO---------------------------'
DIRECTIONS = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]
CENTER = {27, 28, 35, 36}


def insist(value, message):
    if not value:
        raise ValueError(message)


def valid_board(board):
    insist(isinstance(board, str) and len(board) == 64 and set(board) <= set('XO-'), 'invalid_board')


def flips(board, square, mover):
    if board[square] != '-':
        return []
    opponent = 'O' if mover == 'X' else 'X'
    row, col = divmod(square, 8)
    result = []
    for dr, dc in DIRECTIONS:
        r, c, ray = row + dr, col + dc, []
        while 0 <= r < 8 and 0 <= c < 8 and board[8*r+c] == opponent:
            ray.append(8*r+c)
            r, c = r + dr, c + dc
        if ray and 0 <= r < 8 and 0 <= c < 8 and board[8*r+c] == mover:
            result.extend(ray)
    return result


def can_play(board, mover):
    return any(flips(board, square, mover) for square in range(64))


def apply(board, move, mover):
    insist(isinstance(move, str) and len(move) == 2 and move[0] in 'abcdefgh' and move[1] in '12345678', 'invalid_coordinate')
    square = 8*(int(move[1])-1) + 'abcdefgh'.index(move[0])
    changed = flips(board, square, mover)
    insist(bool(changed), 'placement_without_a_flip')
    result = list(board)
    for cell in [square, *changed]:
        result[cell] = mover
    return ''.join(result), square


def following_side(board, mover):
    opponent = 'O' if mover == 'X' else 'X'
    if can_play(board, opponent):
        return opponent
    return mover if can_play(board, mover) else None


def cheap_conditions(node):
    board, side = node['board'], node['next_player']
    valid_board(board)
    occupied = {s for s, color in enumerate(board) if color != '-'}
    checks = {'central_four_occupied': CENTER <= occupied,
              'two_colors_and_at_least_four': 'X' in board and 'O' in board and len(occupied) >= 4}
    closure = set(CENTER)
    changed = True
    while changed:
        changed = False
        for square in sorted(occupied - closure):
            r, c = divmod(square, 8)
            for dr, dc in DIRECTIONS:
                r1, c1, r2, c2 = r+dr, c+dc, r+2*dr, c+2*dc
                if (0 <= r1 < 8 and 0 <= c1 < 8 and 0 <= r2 < 8 and 0 <= c2 < 8
                        and 8*r1+c1 in closure and 8*r2+c2 in closure):
                    closure.add(square)
                    changed = True
                    break
    checks['color_free_occupancy_closure'] = closure == occupied
    invariant_colors = True
    for square in CENTER:
        r, c = divmod(square, 8)
        flippable_geometry = any(0 <= r-dr < 8 and 0 <= r+dr < 8 and 0 <= c-dc < 8 and 0 <= c+dc < 8
                                  and 8*(r-dr)+c-dc in occupied and 8*(r+dr)+c+dc in occupied
                                  for dr, dc in [(1, 0), (0, 1), (1, 1), (1, -1)])
        if not flippable_geometry and board[square] != INITIAL[square]:
            invariant_colors = False
    checks['never_flippable_initial_disc_colors'] = invariant_colors
    checks['four_disc_goal_includes_initial_black_turn'] = len(occupied) != 4 or (board == INITIAL and side == 'X')
    checks['declared_next_player_can_move_or_terminal'] = (can_play(board, side) if side in ('X', 'O')
                                                          else side is None and not can_play(board, 'X') and not can_play(board, 'O'))
    return checks


def check_node(node):
    valid_board(node['board'])
    occupied = 64 - node['board'].count('-')
    insist(node['stones'] == occupied and node['placements'] == occupied-4, 'node_disc_count_mismatch')
    checks = cheap_conditions(node)
    insist(all(checks.values()), 'necessary_condition_failed')
    return checks


def check_edge(earlier, later, edge):
    mover = edge['mover']
    insist(mover in ('X', 'O') and earlier['next_player'] == mover, 'mover_and_earlier_turn_mismatch')
    result, square = apply(earlier['board'], edge['move'], mover)
    insist(result == later['board'], 'forward_edge_target_mismatch')
    insist(later['stones'] == earlier['stones']+1, 'edge_did_not_add_one_disc')
    expected = following_side(result, mover)
    insist(later['next_player'] == expected, 'next_turn_or_terminal_mismatch')
    insist(type(edge['forced_pass_after_move']) is bool and edge['forced_pass_after_move'] == (expected == mover), 'forced_pass_flag_mismatch')
    insist(edge['earlier_raw_index'] == earlier['raw_index'] and edge['later_raw_index'] == later['raw_index'], 'raw_index_mismatch')
    return {'move': edge['move'], 'mover': mover, 'forced_pass': expected == mover, 'added_square': square}


def replay_from_initial(moves, target):
    board, mover, placements, passes = INITIAL, 'X', 0, 0
    for move in moves:
        other = 'O' if mover == 'X' else 'X'
        if move == 'pass':
            insist(not can_play(board, mover) and can_play(board, other), 'illegal_explicit_pass')
            mover = other
            passes += 1
            continue
        if not can_play(board, mover):
            insist(can_play(board, other), 'record_continues_after_termination')
            mover, passes = other, passes+1
        board, _ = apply(board, move, mover)
        mover = 'O' if mover == 'X' else 'X'
        placements += 1
    insist(board == target, 'full_reference_target_mismatch')
    return {'placements': placements, 'forced_passes': passes,
            'terminal': not can_play(board, 'X') and not can_play(board, 'O')}


def check(path, cnf=None, solver_output=None):
    data = json.loads(Path(path).read_text())
    nodes, edges = data['nodes'], data['edges']
    insist(len(nodes) == 12 and len(edges) == data['reverse_edges_after_root'] == 11, 'wrong_chain_length')
    condition_rows = []
    for depth, node in enumerate(nodes):
        insist(node['chain_depth'] == depth and node['raw_index'] == depth+3, 'chain_depth_or_index_mismatch')
        condition_rows.append(check_node(node))
        insist(node['passes_paper_cheap_conditions'] is True and node['state_unreachable_given_chain_next_side'] is True, 'node_claim_mismatch')
        insist(node['board_unreachable'] is (True if depth == 0 else None), 'descendant_board_only_overclaim')
    insist(nodes[0]['stones'] == 61 and nodes[-1]['stones'] == 50, 'wrong_disc_endpoints')
    black = sum(1 << i for i, c in enumerate(nodes[0]['board']) if c == 'X')
    white = sum(1 << i for i, c in enumerate(nodes[0]['board']) if c == 'O')
    insist(data['root_hex'] == f'{black:016x},{white:016x}', 'root_hex_mismatch')
    audited_edges = [check_edge(nodes[i+1], nodes[i], edge) for i, edge in enumerate(edges)]
    # A hypothetical reachable last state with its recorded next side would
    # legally traverse the reversed edge list into the recorded impossible root.
    current = dict(nodes[-1])
    for i in range(len(edges)-1, -1, -1):
        check_edge(current, nodes[i], edges[i])
        current = nodes[i]
    insist(current['board'] == nodes[0]['board'], 'suffix_composition_failed')
    reference = replay_from_initial(data['reachable_full_target']['moves'], data['reachable_full_target']['board'])
    prefix = data['prefix_from_reachable_target']
    insist(len(prefix['nodes']) == 4 and len(prefix['edges']) == 3, 'wrong_prefix_length')
    insist(prefix['nodes'][0]['board'] == data['reachable_full_target']['board'], 'prefix_full_target_mismatch')
    insist(prefix['nodes'][-1]['board'] == nodes[0]['board'] and prefix['nodes'][-1]['next_player'] == nodes[0]['next_player'], 'prefix_root_mismatch')
    for node in prefix['nodes']:
        check_node(node)
    for i, edge in enumerate(prefix['edges']):
        check_edge(prefix['nodes'][i+1], prefix['nodes'][i], edge)
    for node in prefix['nodes'][1:3]:
        insist(node['board_unreachable'] is None and node['state_unreachable_given_chain_next_side'] is None, 'unverified_prefix_overclaim')
    proof = data['proof']
    expected = {'encoding_options': 'occ', 'nopass': False, 'pass_window': 0, 'free_colors': 0,
                'selectors': False, 'target_next_side': 'unrestricted', 'solver_exit_code': 20,
                'solver_result': 'UNSAT', 'solver_version': '4.0.3', 'drat_trace_generated': False,
                'drat_independently_checked': False}
    insist(all(proof[k] == v for k, v in expected.items()), 'recorded_general_unsat_scope_mismatch')
    artifacts = {'cnf_hash_and_header': 'not_supplied', 'solver_output_hash_and_unsat_line': 'not_supplied'}
    if cnf is not None:
        raw = Path(cnf).read_bytes()
        insist(hashlib.sha256(raw).hexdigest() == proof['cnf_sha256'], 'cnf_hash_mismatch')
        insist(raw.splitlines()[0].decode() == proof['cnf_header'], 'cnf_header_mismatch')
        artifacts['cnf_hash_and_header'] = 'passed'
    if solver_output is not None:
        raw = Path(solver_output).read_bytes()
        insist(hashlib.sha256(raw).hexdigest() == proof['solver_output_sha256'], 'solver_output_hash_mismatch')
        insist('s UNSATISFIABLE' in raw.decode().splitlines(), 'missing_recorded_unsat_line')
        artifacts['solver_output_hash_and_unsat_line'] = 'passed'
    return {'status': 'passed', 'input_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'reverse_edges_independently_forward_replayed': len(audited_edges), 'nodes': len(nodes),
            'disc_counts': [node['stones'] for node in nodes], 'cheap_conditions_per_node': condition_rows,
            'all_12_nodes_pass_listed_necessary_conditions': True,
            'full_target_reference': reference, 'prefix_edges_independently_forward_replayed': 3,
            'suffix_from_50_disc_state_to_61_disc_root': [edges[i]['move'] for i in range(10, -1, -1)],
            'forced_passes_on_11_edges': sum(edge['forced_pass'] for edge in audited_edges),
            'root_recorded_solver_result': 'general-pass board-only UNSAT, Kissat4.0.3 exit20',
            'existing_artifact_checks': artifacts, 'new_solver_or_search_execution': False,
            'drat_generated': False, 'drat_checked': False,
            'allowed_claim': 'One locally legal11-edge reverse chain passes the listed necessary filters. Conditional on the recorded general root UNSAT, descendants are unreachable only with the specified chain next side.',
            'not_established': ['UNSAT recomputation or independently verified proof trace', 'board-only unreachability of downstream boards with a different next side', 'all-frontier survival to depth11', 'minimum contradiction depth11 or any algorithmic lower bound', 'a new exact label for the63/62-disc prefix states', 'a population frequency or typical-case depth claim']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--cnf', type=Path)
    parser.add_argument('--solver-output', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = check(args.input, args.cnf, args.solver_output)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        result = {'status': 'failed', 'error_type': type(exc).__name__}
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
