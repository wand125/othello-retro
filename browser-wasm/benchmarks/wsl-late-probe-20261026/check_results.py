#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the published six rows and independently replay all found witnesses."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]

def main():
    spec = importlib.util.spec_from_file_location('independent_record_verify', REPO/'runner/verify.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    rows = [json.loads(line) for line in (ROOT/'results.jsonl').read_text().splitlines()]
    plan = json.loads((ROOT/'plan.json').read_text())
    cases = {c['id']: c for c in json.loads((ROOT/'cases.json').read_text())['cases']}
    provenance = json.loads((ROOT/'source-provenance.json').read_text())
    assert hashlib.sha256((ROOT/'results.jsonl').read_bytes()).hexdigest() == provenance['measured_raw_sha256']
    assert len(rows) == len(plan) == 6
    assert [r['job'] for r in rows] == plan
    found = 0
    unknown = 0
    for row in rows:
        assert row['job']['mode'] == 2
        assert row['job']['conflicts'] == 100000 and row['job']['decisions'] == 1000000
        if row['status'] == 'found':
            proof = verifier.verify(row['moves'], cases[row['job']['case']]['board'])
            assert proof['terminal'] and row['independent_replay']
            assert row['stats']['solver_result'] == 10
            found += 1
        elif row['status'] == 'unknown':
            assert row['stats']['solver_result'] == 0
            assert row['stats']['total_seconds'] < row['job']['observe_ms']/1000
            unknown += 1
        else:
            raise AssertionError('unexpected outcome in the measured six rows')
    assert found == 4 and unknown == 2
    print(json.dumps({'status': 'passed', 'rows': 6, 'found_independently_replayed': found,
                      'work_limit_unknown': unknown, 'watchdog_unknown': 0, 'raw_bytes_hash_matches': True}))

if __name__ == '__main__':
    main()
