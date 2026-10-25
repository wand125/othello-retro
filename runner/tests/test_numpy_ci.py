# SPDX-License-Identifier: MIT
"""Optional NumPy reproduction tests; the core runner needs no NumPy.

The two committed WSL datasets contain public reference measurements, not a
solver dependency. These tests never import or execute the measured engine.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

RUNNER = Path(__file__).resolve().parents[1]
REPO = RUNNER.parent
sys.path.insert(0, str(RUNNER))
import check_numpy_ci

HAS_NUMPY = importlib.util.find_spec('numpy') is not None


def paths(dataset):
    return (REPO / f'benchmarks/study-{dataset}-cpu222-unbounded-v1.json',
            REPO / f'benchmarks/wsl-cpu222-unbounded-{dataset}-main-20261025')


class MissingNumpyTests(unittest.TestCase):
    def test_cli_without_numpy_is_explicit_nonzero(self):
        # -S disables site-packages even if the invoking test environment has
        # NumPy. It does not remove the standard library or load a solver.
        bank, source = paths('midgame')
        result = subprocess.run([sys.executable, '-S', str(RUNNER / 'check_numpy_ci.py'),
                                 '--bank', str(bank), '--input', str(source)],
                                cwd=REPO, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('optional NumPy is unavailable', result.stderr)
        self.assertNotIn('Traceback', result.stderr)


@unittest.skipUnless(HAS_NUMPY, 'optional NumPy is not installed; core tests remain usable')
class NumpyCiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='numpy-ci-tests-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def copy_run(self, dataset='endgame'):
        bank, source = paths(dataset)
        target = self.root / dataset
        target.mkdir(exist_ok=True)
        for name in ('metadata.json', 'runs.jsonl', 'summary.json'):
            shutil.copyfile(source / name, target / name)
        return bank, target

    def test_both_public_wsl_summaries_reproduce_all_fields(self):
        for dataset, case_count, trial_count, fields in [('midgame', 400, 2400, 74), ('endgame', 20, 120, 54)]:
            with self.subTest(dataset=dataset):
                bank, source = paths(dataset)
                report = check_numpy_ci.check(bank, source)
                self.assertEqual(report['status'], 'match', report['mismatches'])
                self.assertEqual(report['mismatches'], [])
                self.assertEqual(report['checked_numeric_fields'], fields)
                self.assertEqual(report['independent_cases'], case_count)
                self.assertEqual(report['verified_trials'], trial_count)
                self.assertEqual(report['recalculated']['counts']['sat']['independent_cases'], case_count)
                self.assertEqual(report['recalculated']['counts']['sat']['completed_found'], trial_count // 2)
                self.assertEqual(report['recalculated']['estimates']['fixed_stratum_overall']['independent_cases'], case_count)
                self.assertEqual(report['bootstrap_seed'], 730253)
                self.assertEqual(report['bootstrap_replicates'], 3000)
                self.assertEqual(report['tolerance']['absolute'], 1e-12)
                self.assertEqual(report['tolerance']['relative'], 1e-10)

    def test_modified_ci_endpoint_and_wrong_means_are_rejected(self):
        bank, source = self.copy_run()
        original = json.loads((source / 'summary.json').read_text())
        changes = [('estimates', 'fixed_stratum_overall', 'ratio_ci95', 0),
                   ('estimates', 'early-terminal', 'auto_mean_seconds'),
                   ('counts', 'sat', 'mean_seconds')]
        for keys in changes:
            with self.subTest(field=keys):
                summary = json.loads(json.dumps(original))
                item = summary
                for key in keys[:-1]:
                    item = item[key]
                item[keys[-1]] += .25
                (source / 'summary.json').write_text(json.dumps(summary))
                report = check_numpy_ci.check(bank, source)
                self.assertEqual(report['status'], 'mismatch')
                self.assertFalse(report['numerically_matches'])
                self.assertEqual(len(report['mismatches']), 1)

    def test_mismatch_cli_exits_one_and_writes_detailed_report(self):
        bank, source = self.copy_run()
        summary = json.loads((source / 'summary.json').read_text())
        summary['estimates']['fixed_stratum_overall']['difference_ci95'][1] += 1
        (source / 'summary.json').write_text(json.dumps(summary))
        output = self.root / 'check-report.json'
        result = subprocess.run([sys.executable, str(RUNNER / 'check_numpy_ci.py'), '--bank', str(bank),
                                 '--input', str(source), '--output', str(output)],
                                cwd=REPO, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(output.read_text())
        self.assertEqual(report['status'], 'mismatch')
        self.assertEqual(report['mismatches'][0]['field'], 'estimates.fixed_stratum_overall.difference_ci95[1]')

    def test_illegal_witness_is_rejected_before_statistics(self):
        bank, source = self.copy_run()
        path = source / 'runs.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]['moves'] = ['a1']
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaises(ValueError):
            check_numpy_ci.check(bank, source)

    def test_frozen_protocol_bootstrap_settings_cannot_be_silently_changed(self):
        bank, source = self.copy_run()
        summary = json.loads((source / 'summary.json').read_text())
        summary['bootstrap_seed'] += 1
        (source / 'summary.json').write_text(json.dumps(summary))
        with self.assertRaisesRegex(ValueError, 'differs from the frozen protocol'):
            check_numpy_ci.check(bank, source)

    def test_nonreference_numpy_version_limits_the_reported_scope(self):
        bank, source = paths('endgame')
        np = check_numpy_ci.numpy_module()
        with mock.patch.object(np, '__version__', 'different-test-version'):
            report = check_numpy_ci.check(bank, source)
        self.assertTrue(report['numerically_matches'])
        self.assertFalse(report['reference_version_matches'])
        self.assertEqual(report['numpy_version'], 'different-test-version')
        self.assertIn('does not certify reference-version', report['verification_scope'])


if __name__ == '__main__':
    unittest.main()
