#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the published six observations or a fresh reproduction without solving."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--results', type=Path, help='Optional fresh results.jsonl; omit to check exact published bytes')
    args = parser.parse_args()
    repo = args.repo
    if repo is None:
        repo = next((p for p in ROOT.parents if (p/'runner/verify.py').is_file()), None)
    if repo is None:
        parser.error('Use --repo PATH_TO_PUBLIC_REPOSITORY for the independent verifier')
    source = repo/'runner/verify.py'
    spec = importlib.util.spec_from_file_location('independent_replay', source)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    measured = args.results is None
    result_file = args.results or ROOT/'results.jsonl'
    rows = [json.loads(line, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            for line in result_file.read_text().splitlines() if line.strip()]
    plan = read(ROOT/'plan.json')
    cases = {c['id']: c for c in read(ROOT/'cases.json')['cases']}
    proof = read(ROOT/'verification.json')
    assert len(rows) == len(plan) == 6
    assert [row['job'] for row in rows] == plan
    if measured:
        assert sha(result_file) == proof['byte_exact_raw_sha256']
    found = unknown = 0
    for row in rows:
        metrics = row['metrics']
        for key in ['cnn_calls_attempted', 'cnn_calls_completed', 'cnn_items_attempted',
                    'cnn_items_completed', 'cnn_failures']:
            assert isinstance(metrics[key], int) and metrics[key] >= 0
        assert metrics['cnn_calls_attempted'] >= metrics['cnn_calls_completed']
        assert metrics['cnn_items_attempted'] >= metrics['cnn_items_completed']
        assert math.isfinite(row['observed_seconds']) and row['observed_seconds'] >= 0
        if row['status'] == 'found':
            verifier.verify(row['moves'], cases[row['job']['case']]['board'])
            assert row['independent_replay'] is True
            found += 1
        else:
            assert row['status'] == 'observation_deadline_unknown'
            assert row['observational_deadline'] is True
            assert row['observed_seconds'] >= row['job']['observation_ms']/1000
            unknown += 1
    if measured:
        assert found == 5 and unknown == 1
    print(json.dumps({'status': 'passed', 'rows': len(rows), 'independently_replayed_found': found,
                      'observation_unknown': unknown, 'published_raw_hash_checked': measured,
                      'verifier_sha256': sha(source)}))

if __name__ == '__main__':
    main()
