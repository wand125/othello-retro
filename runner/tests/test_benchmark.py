# SPDX-License-Identifier: MIT
"""Subprocess integration tests for the public, solver-free benchmark driver.

All adapters here are harness fixtures, never performance evidence. Test waits
have finite safety budgets; they do not add a deadline to benchmark trials.
Run from a fresh checkout with:
    python3 -m unittest discover -s runner/tests -v
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest

RUNNER = Path(__file__).resolve().parents[1]
REPO = RUNNER.parent
BANK = REPO / 'benchmarks/study-midgame-cpu222-unbounded-v1.json'
sys.path.insert(0, str(RUNNER))
from verify import verify


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


# This adapter deliberately has its own fixture references. The driver may send
# only {id, board}; the adapter asserts that no reference answer was supplied.
MOCK = r'''
import json, os, pathlib, signal, subprocess, sys, time
bank = json.load(open(sys.argv[1]))
records = {c['board']: c['reference_moves'] for s in bank['splits'].values() for c in s['cases']}
state = pathlib.Path(sys.argv[2])
mode = sys.argv[3]
request = json.load(sys.stdin)
assert set(request) == {'id', 'board'}, 'driver leaked more than id and board'
state.with_suffix('.request').write_text(json.dumps(request))
if mode == 'pause':
    state.with_suffix('.started').write_text('ready')
    while not state.with_suffix('.release').exists():
        time.sleep(.01)
if mode == 'cancel' and not state.exists():
    state.write_text('first attempt')
    child_code = 'import os,pathlib,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); pathlib.Path(' + repr(str(state.with_suffix('.pid'))) + ').write_text(str(os.getpid())); time.sleep(120)'
    subprocess.Popen([sys.executable, '-c', child_code], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while not state.with_suffix('.pid').exists():
        time.sleep(.01)
    time.sleep(120)
result = {'id': request['id'], 'status': 'found', 'moves': records[request['board']],
          'fixture': True, 'measurement_kind': 'harness-smoke-only'}
if mode == 'unknown':
    result.update(status='unknown', moves=[])
elif mode == 'invalid':
    result['moves'] = ['a1']
# Exercise pretty, multiline JSON in oneshot mode.
print(json.dumps(result, indent=2), flush=True)
'''


@unittest.skipUnless(os.name == 'posix', 'driver requires POSIX process groups')
class BenchmarkIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='public-benchmark-tests-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bank = read_json(BANK)
        self.cases = {c['id']: c for c in self.bank['splits']['pilot']['cases']}

    def command(self, config, output, *options, bank=BANK):
        return [sys.executable, str(RUNNER / 'benchmark.py'), 'run', '--bank', str(bank),
                '--split', 'pilot', '--config', str(config), '--output', str(output), *options]

    def run_cli(self, config, output, *options, bank=BANK):
        return subprocess.run(self.command(config, output, *options, bank=bank), cwd=REPO,
                              capture_output=True, text=True, timeout=30)

    def spawn(self, config, output, *options, bank=BANK):
        process = subprocess.Popen(self.command(config, output, *options, bank=bank), cwd=REPO,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop_driver, process)
        return process

    @staticmethod
    def stop_driver(process):
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)

    def wait_for(self, predicate, message, process=None, timeout=8):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            try:
                if predicate():
                    return
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            if process is not None and process.poll() is not None:
                stdout, stderr = process.communicate()
                self.fail(f'{message}: driver exited {process.returncode}: {stdout} {stderr}')
            time.sleep(.02)
        self.fail(message)

    def small_bank(self):
        # An explicitly derived test plan, not a replacement for the frozen bank.
        bank = read_json(BANK)
        section = bank['splits']['pilot']
        section['schedule'] = section['schedule'][:2]
        ids = {trial['case'] for trial in section['schedule']}
        section['cases'] = [c for c in section['cases'] if c['id'] in ids]
        for name in ('cases', 'schedule'):
            section[name + '_sha256'] = digest(section[name])
        path = self.root / 'derived-fixture-bank.json'
        path.write_text(json.dumps(bank))
        return path

    def mock_config(self, mode):
        script = self.root / 'mock_adapter.py'
        if not script.exists():
            script.write_text(MOCK)
        bank = self.small_bank()
        state = self.root / (mode + '.state')
        config = self.root / (mode + '.json')
        secret = 'SYNTHETIC_TEST_SECRET_DO_NOT_EXPORT'
        config.write_text(json.dumps({'env': {'TEST_PRIVATE_TOKEN': secret}, 'programs': {
            slot: {'label': 'test-only reference fixture', 'mode': 'oneshot',
                   'command': [sys.executable, str(script), str(bank), str(state), mode]}
            for slot in ('sat', 'auto')}}))
        return config, bank, state

    def assert_rows(self, output, expected_count):
        rows = read_rows(output / 'runs.jsonl')
        self.assertEqual(len(rows), expected_count)
        for index, row in enumerate(rows):
            self.assertEqual(row['trial_index'], index)
            self.assertEqual(row['status'], 'found')
            self.assertIs(row['verified'], True)
            self.assertIs(row['fixture'], True)
            self.assertEqual(row['measurement_kind'], 'harness-smoke-only')
            normalized = verify(row['moves'], self.cases[row['case']]['board'])
            for key in ('moves', 'placements', 'passes', 'terminal'):
                self.assertEqual(row[key], normalized[key])
            self.assertGreater(row['wall_seconds'], 0)
            self.assertAlmostEqual(row['effective_wall_seconds'], row['wall_seconds'] +
                                   row['interrupted_work_seconds'], places=7)
        meta = read_json(output / 'metadata.json')
        self.assertEqual(meta['status'], 'complete')
        self.assertEqual(meta['completed_trials'], expected_count)
        self.assertIs(meta['fixture'], True)
        self.assertIs(meta['performance_claims_allowed'], False)
        self.assertEqual(stat.S_IMODE((output / 'private-runtime.json').stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((output / '.private-logs').stat().st_mode), 0o700)
        for path in (output / '.private-logs').iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        return rows, meta

    def test_public_pilot_oneshot_single_slot_keeps_filtered_order(self):
        output = self.root / 'oneshot'
        result = self.run_cli(RUNNER / 'examples/fixture-oneshot.json', output, '--method', 'sat')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows, meta = self.assert_rows(output, 10)
        original = self.bank['splits']['pilot']['schedule']
        wanted = [(i, trial) for i, trial in enumerate(original) if trial['method'] == 'sat']
        self.assertEqual([row['original_trial_index'] for row in rows], [i for i, _ in wanted])
        self.assertEqual(read_json(output / 'schedule.json'), [trial for _, trial in wanted])
        self.assertEqual(meta['original_schedule_sha256'], self.bank['splits']['pilot']['schedule_sha256'])
        self.assertEqual(meta['schedule_sha256'], digest([trial for _, trial in wanted]))
        self.assertTrue(all(r['timing_profile'] == 'external-oneshot-startup-included-v1' for r in rows))

    def test_public_pilot_resident_both_slots(self):
        output = self.root / 'resident'
        result = self.run_cli(RUNNER / 'examples/fixture-resident.json', output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows, _ = self.assert_rows(output, 20)
        self.assertEqual(read_json(output / 'schedule.json'), self.bank['splits']['pilot']['schedule'])
        self.assertTrue(all(r['timing_profile'] == 'external-resident-ready-before-timing-v1' for r in rows))
        preparations = read_rows(output / 'preparation.jsonl')
        self.assertEqual({row['method'] for row in preparations}, {'sat', 'auto'})
        self.assertEqual(len(preparations), 2)
        self.assertTrue(all(row['preparation_wall_seconds'] >= 0 for row in preparations))

    def test_unknown_and_invalid_proof_stop_with_error_not_zero_cost_success(self):
        for mode in ('unknown', 'invalid'):
            with self.subTest(mode=mode):
                config, bank, _ = self.mock_config(mode)
                output = self.root / ('error-' + mode)
                result = self.run_cli(config, output, bank=bank)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                meta = read_json(output / 'metadata.json')
                self.assertEqual(meta['status'], 'error')
                self.assertEqual(meta['completed_trials'], 0)
                self.assertFalse((output / 'runs.jsonl').exists())
                errors = read_rows(output / 'errors.jsonl')
                self.assertEqual(len(errors), 1)
                self.assertEqual(errors[0]['status'], 'error')
                interrupted = read_rows(output / 'interruptions.jsonl')
                self.assertEqual(len(interrupted), 1)
                self.assertGreater(interrupted[0]['elapsed_seconds'], 0)

    def test_completed_resume_same_config_and_changed_config_rejection(self):
        config, bank, state = self.mock_config('normal')
        output = self.root / 'resume'
        result = self.run_cli(config, output, bank=bank)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_rows(output, 2)
        before = (output / 'runs.jsonl').read_bytes()
        resumed = self.run_cli(config, output, '--resume', bank=bank)
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        self.assertEqual((output / 'runs.jsonl').read_bytes(), before)
        value = read_json(config)
        value['programs']['sat']['label'] = 'changed configuration'
        config.write_text(json.dumps(value))
        rejected = self.run_cli(config, output, '--resume', bank=bank)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn('resume_bank_config_code_or_program_changed', rejected.stderr)
        self.assertEqual((output / 'runs.jsonl').read_bytes(), before)
        request = read_json(state.with_suffix('.request'))
        self.assertEqual(set(request), {'id', 'board'})
        for path in output.iterdir():
            if path.is_file() and path.name != 'private-runtime.json':
                self.assertNotIn('SYNTHETIC_TEST_SECRET_DO_NOT_EXPORT', path.read_text(errors='replace'))
        self.assertIn('SYNTHETIC_TEST_SECRET_DO_NOT_EXPORT', (output / 'private-runtime.json').read_text())

    def test_pause_created_during_trial_waits_only_between_trials(self):
        config, bank, state = self.mock_config('pause')
        output = self.root / 'pause'
        pause = self.root / 'between-trials.flag'
        process = self.spawn(config, output, '--pause-file', str(pause), bank=bank)
        self.wait_for(lambda: state.with_suffix('.started').exists(), 'mock did not start', process)
        pause.touch()
        # The current trial must still finish despite PAUSE being present.
        state.with_suffix('.release').touch()
        self.wait_for(lambda: read_json(output / 'metadata.json')['status'] == 'paused',
                      'driver did not pause between trials', process)
        self.assertEqual(len(read_rows(output / 'runs.jsonl')), 1)
        time.sleep(.15)
        self.assertEqual(len(read_rows(output / 'runs.jsonl')), 1)
        self.assertIsNone(process.poll())
        pause.unlink()
        stdout, stderr = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, stdout + stderr)
        self.assert_rows(output, 2)

    @staticmethod
    def pid_running(pid):
        try:
            os.getpgid(pid)
        except ProcessLookupError:
            return False
        # An orphan can briefly remain a zombie until the host's init reaps it.
        # It has exited and no longer executes; do not require a particular init.
        procstat = Path('/proc') / str(pid) / 'stat'
        try:
            if procstat.read_text().rsplit(')', 1)[1].split()[0] == 'Z':
                return False
        except FileNotFoundError:
            pass
        return True

    @staticmethod
    def stop_grandchild(pid, group):
        # Best-effort fixture cleanup even if a regression makes the driver fail.
        try:
            if BenchmarkIntegrationTests.pid_running(pid) and os.getpgid(pid) == group:
                os.killpg(group, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def test_sigterm_resume_retains_work_and_cleans_only_owned_grandchild(self):
        config, bank, state = self.mock_config('cancel')
        output = self.root / 'cancel'
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
        self.addCleanup(self.stop_driver, unrelated)
        process = self.spawn(config, output, bank=bank)
        self.wait_for(lambda: state.with_suffix('.pid').exists(), 'grandchild did not start', process)
        child_pid = int(state.with_suffix('.pid').read_text())
        self.addCleanup(self.stop_grandchild, child_pid, os.getpgid(child_pid))
        self.assertTrue(self.pid_running(child_pid))
        time.sleep(.15)
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 130, stdout + stderr)
        self.wait_for(lambda: not self.pid_running(child_pid), 'owned grandchild survived cleanup')
        self.assertIsNone(unrelated.poll(), 'unrelated process group was terminated')
        meta = read_json(output / 'metadata.json')
        self.assertEqual(meta['status'], 'interrupted')
        self.assertEqual(meta['completed_trials'], 0)
        self.assertFalse((output / 'runs.jsonl').exists())
        interrupted = read_rows(output / 'interruptions.jsonl')
        self.assertEqual(len(interrupted), 1)
        self.assertEqual(interrupted[0]['reason'], 'manual_cancel')
        self.assertGreater(interrupted[0]['elapsed_seconds'], .1)
        self.assertEqual(read_json(output / 'private-runtime.json')['owned_process_groups'], [])
        result = self.run_cli(config, output, '--resume', bank=bank)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows, _ = self.assert_rows(output, 2)
        self.assertAlmostEqual(rows[0]['interrupted_work_seconds'], interrupted[0]['elapsed_seconds'], places=7)
        self.assertEqual(rows[1]['interrupted_work_seconds'], 0)
        self.assertGreater(rows[0]['effective_wall_seconds'], rows[0]['wall_seconds'])
        self.assertIsNone(unrelated.poll())


if __name__ == '__main__':
    unittest.main()
