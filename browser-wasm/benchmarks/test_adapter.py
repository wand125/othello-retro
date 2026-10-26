# SPDX-License-Identifier: MIT
"""Small adapter tests; opt-in real browser tests never run the benchmark bank."""
import importlib.util
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('browser_adapter', HERE / 'adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class AdapterUnitTests(unittest.TestCase):
    def test_strict_request(self):
        valid = {'id':'trial-1','board':'-' * 64}
        self.assertEqual(adapter.validate_request(valid), valid)
        for value in (None, [], {}, {'id':False,'board':'-' * 64},
                      {'id':float('nan'),'board':'-' * 64},
                      {'id':'a','board':'x' * 64}, {'id':'a','board':'-' * 63}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                adapter.validate_request(value)

    def test_all_thirteen_assets_are_fingerprinted(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in adapter.ASSETS:
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            hashes = adapter.asset_hashes(directory)
            self.assertEqual(len(hashes), 13)
            (directory / 'encoder.wasm').write_bytes(b'changed')
            self.assertNotEqual(hashes['encoder.wasm'], adapter.asset_hashes(directory)['encoder.wasm'])
            (directory / 'encoder.wasm').unlink()
            (directory / 'encoder.wasm').symlink_to(directory / 'engine.js')
            with self.assertRaises(ValueError):
                adapter.asset_hashes(directory)

    def test_example_config_artifacts_and_no_fixture(self):
        config = json.loads((HERE / 'browser-programs.json').read_text())
        for engine in ('sat', 'auto'):
            program = config['programs'][engine]
            self.assertEqual(program['mode'], 'resident')
            self.assertFalse(program.get('fixture', False))
            self.assertEqual(len(program['artifacts']), 13)
            self.assertIn(engine, program['command'])
        self.assertNotIn('setTimeout', adapter.TRIAL_JS)
        self.assertNotIn('deadline', adapter.TRIAL_JS)


@unittest.skipUnless(os.environ.get('RETRO_BROWSER_TEST_UI'), 'set RETRO_BROWSER_TEST_UI to immutable snapshot')
class BrowserIntegrationTests(unittest.TestCase):
    def read_event(self):
        # Test supervision only: adapter/solver have no wall deadline.
        item = self.lines.get(timeout=45)
        self.assertIsNotNone(item, 'adapter exited before event')
        return json.loads(item)

    def test_real_workers_protocol_and_independent_replay(self):
        sys.path.insert(0, str(HERE.parents[1] / 'runner'))
        from verify import verify
        cases = json.loads((HERE.parent / 'tests/cases.json').read_text())['cases']
        selected = [next(c for c in cases if c['id'] == name)
                    for name in ('one-move', 'main-n12-s202610250000000', 'missing-center')]
        for engine in ('sat', 'auto'):
            with self.subTest(engine=engine), tempfile.TemporaryFile(mode='w+') as errors:
                command = [sys.executable, str(HERE / 'adapter.py'), '--engine', engine,
                           '--ui-dir', os.environ['RETRO_BROWSER_TEST_UI']]
                if os.environ.get('RETRO_BROWSER_TEST_CHROME'):
                    command += ['--chrome', os.environ['RETRO_BROWSER_TEST_CHROME']]
                proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=errors, text=True)
                self.lines = queue.Queue()
                def read_lines():
                    for line in proc.stdout:
                        self.lines.put(line)
                    self.lines.put(None)
                thread = threading.Thread(target=read_lines, daemon=True); thread.start()
                try:
                    ready = self.read_event()
                    self.assertEqual(ready['event'], 'ready')
                    self.assertEqual(len(ready['stats']['asset_sha256']), 13)
                    self.assertTrue(ready['stats']['browser_version'])
                    proc.stdin.write('{"id":"bad","board":"bad"}\n'); proc.stdin.flush()
                    self.assertEqual(self.read_event()['payload']['status'], 'error')
                    for case in selected:
                        proc.stdin.write(json.dumps({'id':case['id'], 'board':case['board']}) + '\n')
                        proc.stdin.flush()
                        event = self.read_event(); result = event['payload']
                        self.assertEqual(event['id'], case['id'])
                        self.assertEqual(result['status'], 'unreachable' if case['id'] == 'missing-center' else 'found')
                        if result['status'] == 'found':
                            verify(result['moves'], case['board'])
                            self.assertTrue(result['stats']['independent_js_verified'])
                        self.assertIsNone(result['stats']['trial_time_limit_seconds'])
                    if engine == 'auto':
                        # SIGTERM while the resident is idle must close its
                        # browser/server; it does not manufacture a verdict.
                        proc.terminate()
                        self.assertEqual(proc.wait(timeout=15), 130)
                    else:
                        proc.stdin.close()
                        self.assertEqual(proc.wait(timeout=15), 0)
                finally:
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            proc.kill(); proc.wait()
                    if not proc.stdin.closed:
                        proc.stdin.close()
                    proc.stdout.close(); thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
