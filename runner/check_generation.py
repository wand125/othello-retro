#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independently regenerate the two public frozen banks; stdlib, CPython 3.10+."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import sys
import time

OPENING = '---------------------------OX------XO---------------------------'
LAYERS = (12, 20, 28, 36, 44)
END_LAYERS = ('full-reference-no-pass', 'full-reference-with-pass', 'early-terminal')
END_COUNTS = (7, 7, 6)
RAYS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


class GenerationMismatch(ValueError):
    """A frozen input disagrees with its deterministic generation rules."""


def require(condition, message):
    if not condition:
        raise GenerationMismatch(message)


def digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()


def legal_placements(cells, player):
    """Independent array implementation, yielding squares in a1..h8 order."""
    opponent = 'O' if player == 'X' else 'X'
    result = []
    for square, value in enumerate(cells):
        if value != '-':
            continue
        row, column = divmod(square, 8)
        captured = []
        for dr, dc in RAYS:
            r, c = row + dr, column + dc
            ray = []
            while 0 <= r < 8 and 0 <= c < 8 and cells[8 * r + c] == opponent:
                ray.append(8 * r + c)
                r, c = r + dr, c + dc
            if ray and 0 <= r < 8 and 0 <= c < 8 and cells[8 * r + c] == player:
                captured.extend(ray)
        if captured:
            result.append((square, captured))
    return result


def regenerate_game(seed, target_stones=None):
    """Uniform legal-square draws; stop at target occupancy or actual termination.

    A terminal result at/before the target is returned, allowing the caller to
    independently decide the midgame rejection. No terminal double pass is added.
    """
    require(type(seed) is int and seed >= 0, 'seed must be a nonnegative integer')
    if target_stones is not None:
        require(type(target_stones) is int and 4 <= target_stones <= 64, 'invalid target occupancy')
    rng = random.Random(seed)
    cells, side, record, stones = list(OPENING), 'X', [], 4
    while True:
        options = legal_placements(cells, side)
        other = 'O' if side == 'X' else 'X'
        opposite = legal_placements(cells, other) if not options or stones == target_stones else None
        terminal = not options and not opposite
        if terminal or stones == target_stones:
            # If the current side has moves, termination is already false.
            return {'board': ''.join(cells), 'moves': record, 'terminal': terminal, 'stones': stones}
        if not options:
            record.append('pass')
            side = other
            continue
        square, flipped = options[rng.randrange(len(options))]
        cells[square] = side
        for cell in flipped:
            cells[cell] = side
        record.append('abcdefgh'[square % 8] + str(square // 8 + 1))
        stones += 1
        side = other


def regenerate_schedule(cases, repeats, seed, endgame=False):
    rng, rows = random.Random(seed), []
    strata = END_LAYERS if endgame else LAYERS
    field = 'stratum' if endgame else 'stones'
    for repeat in range(1, repeats + 1):
        first = {}
        for layer_index, layer in enumerate(strata):
            group = [case for case in cases if case[field] == layer]
            sat_first = len(group) // 2
            if endgame and len(group) % 2 and (repeat + layer_index) % 2:
                sat_first += 1
            flags = ['sat'] * sat_first + ['auto'] * (len(group) - sat_first)
            rng.shuffle(flags)
            first.update((case['id'], flag) for case, flag in zip(group, flags))
        order = list(cases)
        rng.shuffle(order)
        for case in order:
            methods = ('sat', 'auto') if first[case['id']] == 'sat' else ('auto', 'sat')
            for method in methods:
                row = {'case': case['id'], 'repeat': repeat, 'method': method, 'first_method': methods[0]}
                if endgame:
                    row['stratum'] = case['stratum']
                rows.append(row)
    return rows


def check_case(case, generated):
    tag = case.get('id', '<missing case id>')
    require(case['board'] == generated['board'], tag + ': seed-generated board mismatch')
    require(case['reference_moves'] == generated['moves'], tag + ': seed-generated reference record mismatch')
    require(case['terminal'] is generated['terminal'], tag + ': terminal flag mismatch')
    require(case['stones'] == generated['stones'], tag + ': occupancy mismatch')
    require(case.get('expected') == 'reachable', tag + ': expected label mismatch')
    require(case['reference_sha256'] == digest({'board': generated['board'], 'moves': generated['moves']}),
            tag + ': reference digest mismatch')


def check_midgame(bank):
    protocol = bank['protocol']
    require(protocol['target_stones'] == list(LAYERS), 'midgame: fixed stone layers changed')
    require(protocol['main_cases_per_stratum'] == 80 and protocol['pilot_cases_per_stratum'] == 2,
            'midgame: fixed sample counts changed')
    require(protocol['main_repeats'] == 3 and protocol['pilot_repeats'] == 1,
            'midgame: fixed repetition counts changed')
    require(set(bank['splits']) == {'pilot', 'main'}, 'midgame: unexpected splits')
    reports, all_seeds, all_boards, attempted = {}, [], [], []
    for split, count, base, order_seed, repeats in (
        ('pilot', 2, 202610250900000, 730251, 1), ('main', 80, 202610250000000, 730252, 3)
    ):
        section = bank['splits'][split]
        require(len(section['cases']) == count * len(LAYERS), split + ': case count mismatch')
        require(section['independent_games'] == count * len(LAYERS), split + ': independent count mismatch')
        require(section['order_seed'] == order_seed, split + ': fixed schedule seed changed')
        expected_rejected, offset = [], 0
        for layer_index, stones in enumerate(LAYERS):
            accepted = candidate = 0
            while accepted < count:
                require(candidate < 100000, split + ': seed range exhausted')
                seed = base + layer_index * 100000 + candidate
                candidate += 1
                attempted.append(seed)
                generated = regenerate_game(seed, stones)
                if generated['terminal'] or generated['stones'] != stones:
                    expected_rejected.append({'seed': seed, 'requested_stones': stones,
                                              'reason': 'terminal before or at requested stone count'})
                    continue
                case = section['cases'][offset]
                require(case['seed'] == seed, split + ': seed rule or accepted candidate order mismatch')
                require(case['id'] == f'{split}-n{stones}-s{seed}', split + ': generated case id mismatch')
                check_case(case, generated)
                all_seeds.append(seed)
                all_boards.append(case['board'])
                accepted += 1
                offset += 1
        require(section.get('rejected_generation_seeds') == expected_rejected,
                split + ': rejected seeds, reasons, or rejection order mismatch')
        expected_schedule = regenerate_schedule(section['cases'], repeats, order_seed)
        require(section['schedule'] == expected_schedule, split + ': regenerated schedule mismatch')
        reports[split] = {'cases_regenerated': offset, 'rejected_seeds_regenerated': len(expected_rejected),
                         'schedule_rows_regenerated': len(expected_schedule), 'seed_rule_and_acceptance_order': 'passed'}
    require(len(attempted) == len(set(attempted)), 'midgame: attempted seeds overlap')
    return {'kind': 'midgame', 'splits': reports, 'case_count': len(all_seeds),
            'all_case_seeds_unique': True, 'all_attempted_seeds_unique': True,
            'rejection_audit': 'every candidate up to the final accepted case regenerated; complete recorded rejection lists matched',
            'limitations': []}, set(attempted), set(all_boards)


def check_endgame(bank):
    protocol, section = bank['protocol'], bank['splits']['main']
    require(set(bank['splits']) == {'main'}, 'endgame: unexpected splits')
    require([item['id'] for item in protocol['strata']] == list(END_LAYERS), 'endgame: stratum order changed')
    require(protocol['main_repeats'] == 3, 'endgame: repetition count changed')
    require(protocol['selection']['selection_seed_base'] == 730271, 'endgame: selection seed base changed')
    require(protocol['selection']['schedule_seed'] == 730272 and section['order_seed'] == 730272,
            'endgame: fixed schedule seed changed')
    require(len(section['cases']) == section['independent_games'] == 20, 'endgame: case count mismatch')
    require(protocol['selection']['counts'] == dict(zip(END_LAYERS, END_COUNTS)), 'endgame: selected counts changed')
    require(len(section['selection']) == 3, 'endgame: selection declaration count mismatch')
    ordered_cases = [case for layer in END_LAYERS for case in section['cases'] if case['stratum'] == layer]
    require(section['cases'] == ordered_cases, 'endgame: stratum-grouped case order mismatch')
    selected_seeds, selected_boards, counts = [], [], Counter()
    for layer_index, (layer, count) in enumerate(zip(END_LAYERS, END_COUNTS)):
        group = [case for case in section['cases'] if case['stratum'] == layer]
        require(len(group) == count, layer + ': case count mismatch')
        selection = section['selection'][layer_index]
        require(selection['stratum'] == layer and selection['selection_seed'] == 730271 + layer_index,
                layer + ': selection declaration mismatch')
        require(selection['selected'] == count and selection['candidate_pool_size'] == 80,
                layer + ': pool/count declaration mismatch')
        require(selection['selected_source_case_ids'] == [case['source_case_id'] for case in group],
                layer + ': selected source identifiers or order mismatch')
        for case in group:
            seed = case['seed']
            low = 202610255000000 + (layer_index + 2) * 100000
            require(type(seed) is int and low <= seed < low + 100000, layer + ': source seed range mismatch')
            require(case['id'] == f'endgame-{layer}-s{seed}', layer + ': generated case id mismatch')
            require(case['source_case_id'] == f'long-main-{layer}-s{seed}', layer + ': source case id mismatch')
            require(case['game_id'] == f'game-seed-{seed}', layer + ': game id mismatch')
            require(case['selection_stratum'] == layer, layer + ': selection stratum mismatch')
            generated = regenerate_game(seed)
            check_case(case, generated)
            passes = generated['moves'].count('pass')
            require(generated['terminal'], layer + ': generated game is not terminal')
            require(case['actualstones'] == generated['stones'] and case['reference_passes'] == passes,
                    layer + ': occupancy/pass metadata mismatch')
            require((layer == END_LAYERS[0] and generated['stones'] == 64 and passes == 0)
                    or (layer == END_LAYERS[1] and generated['stones'] == 64 and passes > 0)
                    or (layer == END_LAYERS[2] and generated['stones'] < 64), layer + ': stratum condition mismatch')
            selected_seeds.append(seed)
            selected_boards.append(generated['board'])
            counts[layer] += 1
    require(len(set(selected_seeds)) == len(set(selected_boards)) == 20, 'endgame: repeated seed or board')
    expected = regenerate_schedule(section['cases'], 3, 730272, endgame=True)
    require(section['schedule'] == expected, 'endgame: regenerated schedule mismatch')
    balance = {}
    for repeat in range(1, 4):
        actual = Counter(row['first_method'] for row in expected
                         if row['repeat'] == repeat and row['method'] == row['first_method'])
        require(actual == {'sat': 10, 'auto': 10}, 'endgame: first-method balance mismatch')
        balance[str(repeat)] = dict(actual)
    limitations = ['The private 240-case candidate pool is not included. Its completeness, candidate rejections, eligibility/exclusions, and Random.sample selection cannot be independently verified from these files. Selection metadata is checked for internal consistency only; random sampling from that pool is not certified.']
    return {'kind': 'endgame', 'case_count': 20, 'stratum_counts': dict(counts),
            'all_case_seeds_unique': True, 'all_boards_unique': True,
            'schedule_rows_regenerated': len(expected), 'first_method_pairs_by_repeat': balance,
            'private_pool_random_selection_verified': False, 'limitations': limitations}, set(selected_seeds), set(selected_boards)


def validate_bank(bank):
    require(platform.python_implementation() == 'CPython', 'CPython is required for the stated RNG reproduction')
    require(digest(bank['protocol']) == bank['protocol_sha256'], 'protocol hash mismatch')
    for name, section in bank['splits'].items():
        require(digest(section['cases']) == section['cases_sha256'], name + ': cases hash mismatch')
        require(digest(section['schedule']) == section['schedule_sha256'], name + ': schedule hash mismatch')
    if 'target_stones' in bank['protocol']:
        return check_midgame(bank)
    return check_endgame(bank)


def check_files(paths):
    started = time.monotonic()
    reports, evidence = [], []
    for path in paths:
        data = Path(path).read_bytes()
        bank = json.loads(data)
        report, seeds, boards = validate_bank(bank)
        report.update(file=Path(path).name, bank_sha256=hashlib.sha256(data).hexdigest(),
                      protocol_sha256=bank['protocol_sha256'])
        reports.append(report)
        evidence.append((report['kind'], seeds, boards))
    cross = 'not checked: provide both banks'
    if {'midgame', 'endgame'}.issubset(item[0] for item in evidence):
        for kind_a, seeds_a, boards_a in evidence:
            for kind_b, seeds_b, boards_b in evidence:
                if kind_a == 'midgame' and kind_b == 'endgame':
                    require(not seeds_a & seeds_b, 'cross-bank attempted seeds overlap')
                    require(not boards_a & boards_b, 'cross-bank accepted boards overlap')
        cross = 'passed: endgame seeds disjoint from all attempted midgame seeds; accepted boards disjoint'
    return {'status': 'passed', 'checker': 'independent-array-rules-and-seeded-regeneration-v1',
            'python_implementation': platform.python_implementation(), 'python_version': platform.python_version(),
            'rng': 'CPython random.Random(seed); uniform randrange over ascending a1..h8 legal placements',
            'process_nice': os.getpriority(os.PRIO_PROCESS, 0) if hasattr(os, 'getpriority') else None,
            'cases_regenerated': sum(report['case_count'] for report in reports),
            'banks': reports, 'cross_bank_disjointness': cross,
            'wall_seconds': time.monotonic() - started}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank', action='append', type=Path, required=True, help='Repeat for both frozen banks')
    parser.add_argument('--output', type=Path, help='Optional JSON report')
    args = parser.parse_args()
    try:
        result = check_files(args.bank)
    except (GenerationMismatch, KeyError, TypeError, IndexError, OSError, ValueError) as exc:
        result = {'status': 'failed', 'reason': str(exc)}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
