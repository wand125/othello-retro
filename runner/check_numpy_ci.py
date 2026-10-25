#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independently reproduce a legacy NumPy PCG64 benchmark summary.

Optional NumPy is used only here. The public runner, replay checker and paired
analysis remain standard-library tools. No private solver or engine is imported.
"""
from __future__ import annotations
import argparse
import collections
import importlib
import json
import math
from pathlib import Path
import sys

import analyze

ABS_TOLERANCE = 1e-12
REL_TOLERANCE = 1e-10
REFERENCE_NUMPY = '1.26.4'


def numpy_module():
    try:
        return importlib.import_module('numpy')
    except ImportError:
        raise ValueError('optional NumPy is unavailable; install numpy==1.26.4 for the reference check') from None


def wilson_all_success(n):
    z = 1.959963984540054
    denominator = 1 + z * z / n
    center = (1 + z * z / (2 * n)) / denominator
    radius = z * math.sqrt(z * z / (4 * n * n)) / denominator
    return [max(0., center - radius), min(1., center + radius)]


def recalculate(run, seed, replicates, np):
    """Case clusters follow bank order; one PCG64 stream follows stratum order.

    Repeats are averaged within each independent case before any resampling.
    Each bootstrap index selects both method means together. Individual strata
    consume the RNG first; a fresh stratified draw then supplies overall CIs.
    """
    samples = collections.defaultdict(list)
    for row in run['rows']:
        samples[row['case'], row['method']].append(row['effective_wall_seconds'])
    groups = collections.defaultdict(list)
    for case_id, case in run['cases'].items():
        groups[str(case.get('stratum', case['stones']))].append([
            float(np.mean(samples[case_id, method])) for method in ('sat', 'auto')])
    arrays = {key: np.asarray(values, dtype=np.float64) for key, values in groups.items()}
    n = len(run['cases'])
    counts = {}
    for method in ('sat', 'auto'):
        values = [row['effective_wall_seconds'] for row in run['rows'] if row['method'] == method]
        counts[method] = {'completed_found': len(values), 'independent_cases': n,
                          'mean_seconds': float(np.mean(values)), 'median_seconds': float(np.median(values)),
                          'p95_seconds': float(np.quantile(values, .95, method='linear')),
                          'all_repeats_success_case_wilson95': wilson_all_success(n)}
    rng = np.random.default_rng(seed)
    if type(rng.bit_generator).__name__ != 'PCG64':
        raise ValueError('default_rng is not PCG64 in this NumPy version')

    def draw(array):
        indices = rng.integers(0, len(array), size=(replicates, len(array)))
        return array[indices].mean(axis=1)

    def estimate(point, bootstrap, count):
        sat, auto = map(float, point)
        if sat <= 0 or auto <= 0 or np.any(bootstrap[:, 0] <= 0):
            raise ValueError('strictly positive method means are required for ratio CIs')
        ratio = auto / sat
        ci = np.quantile(bootstrap[:, 1] / bootstrap[:, 0], [.025, .975], method='linear')
        difference = np.quantile(bootstrap[:, 1] - bootstrap[:, 0], [.025, .975], method='linear')
        return {'sat_mean_seconds': sat, 'auto_mean_seconds': auto, 'auto_div_sat': ratio,
                'ratio_ci95': list(map(float, ci)),
                'ratio_ci_relative_radius': max(abs(float(v) - ratio) for v in ci) / abs(ratio),
                'auto_minus_sat_seconds': auto - sat, 'difference_ci95': list(map(float, difference)),
                'independent_cases': count}

    estimates = {}
    for name, array in arrays.items():
        estimates[name] = estimate(array.mean(axis=0), draw(array), len(array))
    overall_point = np.zeros(2, dtype=np.float64)
    overall_bootstrap = np.zeros((replicates, 2), dtype=np.float64)
    for array in arrays.values():
        weight = len(array) / n
        overall_point += array.mean(axis=0) * weight
        overall_bootstrap += draw(array) * weight
    estimates['fixed_stratum_overall'] = estimate(overall_point, overall_bootstrap, n)
    return {'counts': counts, 'estimates': estimates}, list(arrays)


def compare(recorded, calculated):
    mismatches = []
    checked = 0

    def visit(actual, expected, path):
        nonlocal checked
        if isinstance(expected, dict):
            if not isinstance(actual, dict) or set(actual) != set(expected):
                mismatches.append({'field': path, 'reason': 'missing or unexpected keys'})
                return
            for key, value in expected.items():
                visit(actual[key], value, path + '.' + key)
        elif isinstance(expected, list):
            if not isinstance(actual, list) or len(actual) != len(expected):
                mismatches.append({'field': path, 'reason': 'wrong interval shape'})
                return
            for i, value in enumerate(expected):
                visit(actual[i], value, path + '[' + str(i) + ']')
        else:
            checked += 1
            valid = not isinstance(actual, bool) and isinstance(actual, (float, int)) and math.isfinite(actual)
            allowed = ABS_TOLERANCE + REL_TOLERANCE * abs(expected)
            exact_integer = isinstance(expected, int)
            if not valid or (actual != expected if exact_integer else abs(actual - expected) > allowed):
                mismatches.append({'field': path, 'recorded': actual if valid else None,
                                   'recalculated': expected, 'allowed_absolute_error': 0 if exact_integer else allowed})
    for key in ('counts', 'estimates'):
        visit(recorded.get(key), calculated[key], key)
    return checked, mismatches


def check(bankpath, directory, split='main', np=None):
    np = numpy_module() if np is None else np
    directory = Path(directory)
    run = analyze.load_run(directory, bankpath, split)
    if not run['complete'] or set(run['methods']) != {'sat', 'auto'}:
        raise ValueError('a complete two-method schedule is required; unfinished trials are not finite costs')
    summary = json.loads((directory / 'summary.json').read_text(encoding='utf-8'))
    seed, replicates = summary['bootstrap_seed'], summary['bootstrap_replicates']
    if type(seed) is not int or seed < 0 or type(replicates) is not int or replicates < 100:
        raise ValueError('invalid recorded bootstrap seed or replicate count')
    rule = run['bank']['protocol'].get('precision_rule', {})
    for key, value in [('bootstrap_seed', seed), ('bootstrap_replicates', replicates)]:
        if key in rule and rule[key] != value:
            raise ValueError('summary bootstrap setting differs from the frozen protocol: ' + key)
    source_meta = summary.get('metadata', {})
    for key in ('bank_sha256', 'protocol_sha256', 'cases_sha256', 'schedule_sha256'):
        if key in source_meta and source_meta[key] != run['metadata'].get(key):
            raise ValueError('summary metadata differs from validated run: ' + key)
    calculated, strata = recalculate(run, seed, replicates, np)
    checked, mismatches = compare(summary, calculated)
    recorded_version = source_meta.get('versions', {}).get('numpy', REFERENCE_NUMPY)
    return {'schema_version': 1, 'status': 'match' if not mismatches else 'mismatch',
            'numerically_matches': not mismatches, 'checked_numeric_fields': checked, 'mismatches': mismatches,
            'bank_sha256': analyze.sha(bankpath), 'protocol_sha256': run['bank']['protocol_sha256'],
            'runs_sha256': analyze.sha(directory / 'runs.jsonl'), 'summary_sha256': analyze.sha(directory / 'summary.json'),
            'split': split, 'independent_cases': len(run['cases']), 'verified_trials': len(run['rows']),
            'fixture': run['metadata'].get('fixture', False),
            'numpy_version': np.__version__, 'recorded_numpy_version': recorded_version,
            'reference_numpy_version': REFERENCE_NUMPY, 'reference_version_matches': np.__version__ == REFERENCE_NUMPY,
            'verification_scope': ('Reference-version PCG64 numerical reproduction within stated floating-point tolerance.'
                if np.__version__ == REFERENCE_NUMPY else
                'This installed NumPy version only; numerical agreement does not certify reference-version reproducibility.'),
            'rng': 'numpy.random.default_rng / PCG64', 'bootstrap_seed': seed,
            'bootstrap_replicates': replicates, 'stratum_iteration_order': strata,
            'case_iteration_order': 'bank case order within each stratum',
            'bootstrap_order': 'each stratum in order; then independent stratified overall draws in the same order',
            'bootstrap_unit': 'paired independent case; all repeats averaged within the case, never resampled as independent cases',
            'interval': '95% percentile, NumPy linear quantile',
            'tolerance': {'absolute': ABS_TOLERANCE, 'relative': REL_TOLERANCE,
                          'rule': 'abs(recorded-recalculated) <= absolute + relative*abs(recalculated); integer counts exact'},
            'recalculated': calculated,
            'note': 'Reproducing a descriptive CI does not establish population precision, environment comparability, or solver correctness beyond independently replayed witnesses.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--split', choices=('main', 'pilot'), default='main')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        report = check(args.bank, args.input, args.split)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print('NumPy CI check failed: ' + str(exc), file=sys.stderr)
        return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'checked_numeric_fields', 'numpy_version', 'reference_version_matches')}))
    return 0 if report['numerically_matches'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
