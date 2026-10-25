#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure external Othello reconstructors against a frozen bank (stdlib only).

Python 3.10+, POSIX (Linux, macOS, WSL). No solver or model is bundled.
Commands are arrays, never shell strings. Only {id, board} is sent to a program.
See README.md for the oneshot JSON and resident JSONL protocols.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import queue
import re
import secrets
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback

from verify import verify

MAX_OUTPUT = 8 * 1024 * 1024
PUBLIC_ENV = frozenset({
    'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
    'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'RAYON_NUM_THREADS',
    'OMP_PROC_BIND', 'OMP_PLACES', 'GOMP_CPU_AFFINITY', 'PYTHONHASHSEED',
    'OTHELLO_DEVICE', 'RETRO_HALF', 'RETRO_NSYM', 'RETRO_REFINE',
    'CUDA_VISIBLE_DEVICES', 'TOKENIZERS_PARALLELISM',
})
DECLARED_KEYS = frozenset({
    'device', 'dtype', 'python_version', 'torch_version', 'numpy_version',
    'rust_version', 'kissat_version', 'threads', 'inference_threads',
    'solver_parallelism', 'cpu_model', 'os', 'architecture', 'affinity',
})
PROFILES = {'oneshot': 'external-oneshot-startup-included-v1',
            'resident': 'external-resident-ready-before-timing-v1'}


class BenchmarkError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class Cancelled(Exception):
    pass


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:
        h = hashlib.sha256()
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
        return h.hexdigest()


def atomic(path, value, private=False):
    path = Path(path)
    data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    fd, temporary = tempfile.mkstemp(prefix='.tmp-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600 if private else 0o644)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def append(path, value, private=False):
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600 if private else 0o644)
    with os.fdopen(fd, 'ab') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n').encode())
        stream.flush()
        os.fsync(stream.fileno())


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0


def safe_declared(value):
    if not isinstance(value, dict):
        raise BenchmarkError('declared_environment_must_be_object')
    public = {}
    for key, item in value.items():
        if key not in DECLARED_KEYS:
            continue
        if isinstance(item, str):
            if len(item) <= 160 and not re.search(r'[/\\\n\r]|(?:sk-|Bearer\s)', item):
                public[key] = item
        elif isinstance(item, (int, float, bool)) and (not isinstance(item, float) or math.isfinite(item)):
            public[key] = item
        elif isinstance(item, list) and len(item) <= 256 and all(isinstance(x, int) and not isinstance(x, bool) for x in item):
            public[key] = item
    return public


def read_bank(path, split, selected):
    path = Path(path)
    bank = json.loads(path.read_text())
    if digest(bank['protocol']) != bank['protocol_sha256']:
        raise BenchmarkError('bank_protocol_hash_mismatch')
    p = bank['protocol']
    for key in ('trial_time_limit_seconds', 'final_sat_time_limit_seconds'):
        if key not in p or p[key] is not None:
            raise BenchmarkError('an_unbounded_bank_is_required')
    sidecar = Path(str(path) + '.sha256')
    if sidecar.exists() and sidecar.read_text().split()[0] != sha(path):
        raise BenchmarkError('bank_sidecar_hash_mismatch')
    section = bank['splits'][split]
    for key in ('cases', 'schedule'):
        if digest(section[key]) != section[key + '_sha256']:
            raise BenchmarkError('bank_' + key + '_hash_mismatch')
    cases = {c['id']: c for c in section['cases']}
    if len(cases) != len(section['cases']) or not cases:
        raise BenchmarkError('duplicate_or_empty_case_ids')
    for case in cases.values():
        if case.get('expected') != 'reachable':
            raise BenchmarkError('this_runner_requires_known_reachable_cases')
        checked = verify(case['reference_moves'], case['board'])
        if checked['terminal'] != case['terminal'] or checked['placements'] != case['board'].count('X') + case['board'].count('O') - 4:
            raise BenchmarkError('reference_case_mismatch')
        if 'reference_sha256' in case and digest({'board': case['board'], 'moves': case['reference_moves']}) != case['reference_sha256']:
            raise BenchmarkError('reference_record_hash_mismatch')
    identities = set()
    for item in section['schedule']:
        key = (item['case'], item['method'], item['repeat'])
        if item['case'] not in cases or item['method'] not in ('sat', 'auto') or type(item['repeat']) is not int or item['repeat'] < 1 or key in identities:
            raise BenchmarkError('invalid_schedule')
        identities.add(key)
    order = [(i, item) for i, item in enumerate(section['schedule']) if item['method'] in selected]
    if not order or any(not any(x['method'] == method for _, x in order) for method in selected):
        raise BenchmarkError('selected_method_not_in_schedule')
    return bank, section, cases, order


def program_specs(config, configpath, selected):
    if not isinstance(config, dict) or not isinstance(config.get('programs'), dict):
        raise BenchmarkError('config_programs_required')
    global_env = config.get('env', {})
    if not isinstance(global_env, dict):
        raise BenchmarkError('env_must_be_object')
    result = {}
    for slot in selected:
        entry = config['programs'].get(slot)
        if not isinstance(entry, dict):
            raise BenchmarkError('missing_program_slot_' + slot)
        command = entry.get('command')
        if not isinstance(command, list) or not command or any(not isinstance(x, str) or not x or '\0' in x for x in command):
            raise BenchmarkError('command_must_be_nonempty_string_array')
        mode = entry.get('mode')
        if mode not in PROFILES:
            raise BenchmarkError('mode_must_be_oneshot_or_resident')
        cwd = entry.get('cwd')
        if cwd is not None and (not isinstance(cwd, str) or not cwd):
            raise BenchmarkError('cwd_must_be_nonempty_string')
        cwd = (configpath.parent / cwd).resolve() if isinstance(cwd, str) else Path.cwd().resolve()
        if not cwd.is_dir():
            raise BenchmarkError('program_cwd_is_not_directory')
        if not isinstance(entry.get('env', {}), dict):
            raise BenchmarkError('env_must_be_object')
        extra = {**global_env, **entry.get('env', {})}
        if any(not isinstance(k, str) or '=' in k or '\0' in k or not isinstance(v, str) or '\0' in v for k, v in extra.items()):
            raise BenchmarkError('environment_keys_and_values_must_be_strings')
        env = {**os.environ, **extra}
        executable = command[0]
        if '/' in executable:
            resolved = (cwd / executable).resolve()
        else:
            resolved = shutil.which(executable, path=env.get('PATH'))
            if resolved is None:
                raise BenchmarkError('executable_not_found')
            resolved = Path(resolved).resolve()
        if not resolved.is_file():
            raise BenchmarkError('executable_is_not_file')
        artifacts = {'executable': {'path': str(resolved), 'sha256': sha(resolved)}}
        for index, argument in enumerate(command[1:], 1):
            candidate = cwd / argument
            # Hash interpreter entry scripts automatically. Mutable state or
            # output paths can also be arguments; freeze other dependencies
            # explicitly with artifacts rather than treating every file as code.
            if (not argument.startswith('-') and candidate.suffix.lower() in
                    {'.py', '.pyc', '.sh', '.js', '.mjs', '.cjs', '.rb', '.pl', '.lua', '.jar', '.wasm'}
                    and candidate.is_file()):
                artifacts['argument_file_' + str(index)] = {'path': str(candidate.resolve()), 'sha256': sha(candidate)}
        for index, artifact in enumerate(entry.get('artifacts', [])):
            if not isinstance(artifact, dict) or not isinstance(artifact.get('path'), str):
                raise BenchmarkError('invalid_artifact')
            name = artifact.get('name', 'artifact_' + str(index))
            if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', name) or name in artifacts:
                raise BenchmarkError('invalid_or_duplicate_artifact_name')
            candidate = (cwd / artifact['path']).resolve()
            artifacts[name] = {'path': str(candidate), 'sha256': sha(candidate)}
        fixture = bool(config.get('fixture') or entry.get('fixture'))
        label = entry.get('label', slot)
        if not isinstance(label, str) or not label or len(label) > 256:
            raise BenchmarkError('invalid_program_label')
        public = {'label': label, 'mode': mode, 'timing_profile': PROFILES[mode],
                  'fixture': fixture, 'environment': {k: env[k] for k in sorted(PUBLIC_ENV) if k in env},
                  'redacted_configured_env_count': len(set(extra) - PUBLIC_ENV),
                  'artifact_hashes': {k: v['sha256'] for k, v in artifacts.items()},
                  'declared_environment': safe_declared(entry.get('declared_environment', config.get('declared_environment', {})))}
        result[slot] = {'command': command, 'cwd': str(cwd), 'env': env, 'configured_env': extra,
                        'artifacts': artifacts, 'mode': mode, 'fixture': fixture, 'public': public}
    return result


class Process:
    """A single owned process group with concurrent, bounded stdout reading."""
    def __init__(self, owner, slot, spec):
        self.owner, self.slot, self.spec = owner, slot, spec
        self.id = secrets.token_hex(8)
        self.events = queue.Queue(maxsize=256)
        self.closing = threading.Event()
        self.stdout_done, self.stderr_done = threading.Event(), threading.Event()
        self.proc = None
        self.threads = []

    def start(self):
        self.owner.check_cancel()
        started = time.monotonic()
        # Signal handlers set a flag instead of unwinding Popen before registration.
        self.proc = subprocess.Popen(self.spec['command'], cwd=self.spec['cwd'], env=self.spec['env'],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     start_new_session=True, shell=False)
        self.owner.processes.append(self)
        self.owner.private_state()
        os.set_blocking(self.proc.stdin.fileno(), False)
        for kind, stream, done in [('stdout', self.proc.stdout, self.stdout_done),
                                   ('stderr', self.proc.stderr, self.stderr_done)]:
            target = self.owner.logs / (self.slot + '-' + self.id + '.' + kind + '.log')
            t = threading.Thread(target=self.read_stream, args=(kind, stream, done, target), daemon=True)
            t.start()
            self.threads.append(t)
        return started

    def enqueue(self, event):
        while not self.closing.is_set():
            try:
                self.events.put(event, timeout=.2)
                return
            except queue.Full:
                continue

    def read_stream(self, kind, stream, done, target):
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'wb') as log:
                if kind == 'stderr':
                    for chunk in iter(lambda: stream.read(8192), b''):
                        log.write(chunk)
                else:
                    while True:
                        line = stream.readline(MAX_OUTPUT + 1)
                        received = time.monotonic()
                        if not line:
                            self.enqueue(('eof', received, None))
                            break
                        log.write(line)
                        if len(line) > MAX_OUTPUT:
                            self.enqueue(('error', received, 'stdout_line_too_large'))
                            break
                        try:
                            text = line.decode('utf-8')
                        except UnicodeDecodeError:
                            self.enqueue(('error', received, 'stdout_not_utf8'))
                            break
                        self.enqueue(('line', received, text))
        except Exception:
            if kind == 'stdout':
                self.enqueue(('error', time.monotonic(), 'stdout_read_error'))
        finally:
            stream.close()
            done.set()

    def send(self, request, close=False):
        payload = (json.dumps(request, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
        offset = 0
        while offset < len(payload):
            self.owner.check_cancel()
            if not select.select([], [self.proc.stdin], [], .2)[1]:
                self.owner.heartbeat()
                continue
            try:
                offset += os.write(self.proc.stdin.fileno(), payload[offset:])
            except BlockingIOError:
                continue
        if close:
            self.proc.stdin.close()

    def event(self):
        while True:
            self.owner.check_cancel()
            self.owner.heartbeat()
            try:
                kind, received, value = self.events.get(timeout=.2)
            except queue.Empty:
                continue
            if kind != 'line':
                raise BenchmarkError(value if kind == 'error' else 'program_stdout_closed_before_result')
            return received, value

    def json_event(self):
        received, line = self.event()
        try:
            value = json.loads(line)
        except (ValueError, TypeError):
            raise BenchmarkError('resident_output_must_be_jsonl') from None
        if not isinstance(value, dict):
            raise BenchmarkError('program_response_must_be_object')
        return received, value

    def prepare(self):
        started = self.start()
        if self.spec['mode'] != 'resident':
            return None
        while True:
            received, event = self.json_event()
            self.owner.detect_fixture(event, self.slot)
            if event.get('event') == 'progress':
                self.owner.external_progress(event)
                continue
            if event.get('event') == 'ready' or event.get('status') == 'ready':
                return {'method': self.slot, 'instance_id': self.id, 'ready_at': utc(),
                        'preparation_wall_seconds': received - started,
                        'timing_profile': PROFILES['resident']}
            raise BenchmarkError('resident_ready_event_required')

    def request(self, request):
        self.send(request, close=self.spec['mode'] == 'oneshot')
        if self.spec['mode'] == 'oneshot':
            text = ''
            decoder = json.JSONDecoder()
            while True:
                received, part = self.event()
                text += part
                if len(text) > MAX_OUTPUT:
                    raise BenchmarkError('oneshot_output_too_large')
                stripped = text.lstrip()
                try:
                    value, end = decoder.raw_decode(stripped)
                except json.JSONDecodeError:
                    continue
                if stripped[end:].strip():
                    raise BenchmarkError('oneshot_requires_one_json_document')
                if not isinstance(value, dict):
                    raise BenchmarkError('program_response_must_be_object')
                return received, value
        while True:
            received, value = self.json_event()
            if value.get('id') not in (None, request['id']):
                raise BenchmarkError('response_request_id_mismatch')
            if value.get('event') == 'progress':
                self.owner.external_progress(value)
                continue
            if value.get('event') == 'result':
                value = value.get('payload', value.get('result'))
                if not isinstance(value, dict):
                    raise BenchmarkError('result_payload_must_be_object')
            return received, value

    def signal_owned_group(self, sig):
        try:
            os.killpg(self.proc.pid, sig)
        except ProcessLookupError:
            return
        except PermissionError:
            # Darwin can return EPERM, rather than ESRCH, for an exited
            # session leader whose process group no longer exists. The leader
            # has not been reaped, so its PID cannot have been reused. Still
            # signal the group first: a surviving descendant may keep it alive.
            if sys.platform == 'darwin':
                try:
                    os.getpgid(self.proc.pid)
                except ProcessLookupError:
                    return
            raise

    def close(self):
        if self.proc is None:
            return
        # Do not poll/reap before signalling: the unreaped leader pins this PID,
        # preventing reuse while we signal only the process group we created.
        self.closing.set()
        self.signal_owned_group(signal.SIGTERM)
        until = time.monotonic() + .5
        while time.monotonic() < until and not (self.stdout_done.is_set() and self.stderr_done.is_set()):
            time.sleep(.01)
        self.signal_owned_group(signal.SIGKILL)
        self.proc.wait(timeout=5)
        try:
            self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        for thread in self.threads:
            thread.join(timeout=1)
        if self in self.owner.processes:
            self.owner.processes.remove(self)
        self.owner.private_state()
        self.proc = None


class Run:
    def __init__(self, args):
        self.args = args
        self.out = args.output.resolve()
        self.cancelled = False
        self.processes = []
        self.residents = {}
        self.current = None
        self.started = None
        self.attempt_id = None
        self.last_heartbeat = 0.
        self.progress_events = 0
        self.program_started = time.monotonic()
        self.selected = [args.method] if args.method else ['sat', 'auto']
        self.bank, self.section, self.cases, self.order = read_bank(args.bank, args.split, self.selected)
        self.config = json.loads(args.config.read_text())
        self.specs = program_specs(self.config, args.config.resolve(), self.selected)
        self.schedule = [item for _, item in self.order]
        self.code_hashes = {'runner/benchmark.py': sha(__file__),
                            'runner/verify.py': sha(Path(__file__).with_name('verify.py'))}
        self.identity = {'bank_sha256': sha(args.bank), 'protocol_sha256': self.bank['protocol_sha256'],
                         'split': args.split, 'cases_sha256': self.section['cases_sha256'],
                         'original_schedule_sha256': self.section['schedule_sha256'],
                         'schedule_sha256': digest(self.schedule), 'config_sha256': digest(self.config),
                         'selected_methods': self.selected, 'code_hashes': self.code_hashes,
                         'program_identity': {k: {q: v[q] for q in ('command', 'cwd', 'configured_env', 'artifacts')}
                                              for k, v in self.specs.items()},
                         'public_program_controls': {k: v['public'] for k, v in self.specs.items()},
                         'runtime_host': {'hostname': platform.node(), 'system': platform.system(),
                                          'release': platform.release(), 'machine': platform.machine(),
                                          'python': platform.python_version(), 'logical_cpus': os.cpu_count(),
                                          'affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None}}
        self.fingerprint = digest(self.identity)
        if not args.resume:
            self.out.mkdir(parents=True, exist_ok=False)
        elif not self.out.is_dir():
            raise BenchmarkError('resume_output_directory_missing')
        import fcntl
        self.lock = (self.out / '.run.lock').open('a+b')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BenchmarkError('output_directory_already_running') from None
        self.logs = self.out / '.private-logs'
        self.logs.mkdir(mode=0o700, exist_ok=True)
        os.chmod(self.logs, 0o700)
        self.pause_file = args.pause_file.resolve() if args.pause_file else self.out / 'PAUSE'
        self.rows = []
        self.interruptions = []
        if args.resume:
            self.meta = json.loads((self.out / 'metadata.json').read_text())
            if self.meta.get('run_fingerprint') != self.fingerprint:
                raise BenchmarkError('resume_bank_config_code_or_program_changed')
            previous_runtime = self.out / 'private-runtime.json'
            if previous_runtime.exists() and json.loads(previous_runtime.read_text()).get('owned_process_groups'):
                raise BenchmarkError('previous_child_cleanup_incomplete_start_a_new_run')
            self.read_completed_rows()
            if (self.out / 'interruptions.jsonl').exists():
                self.interruptions = [json.loads(x) for x in (self.out / 'interruptions.jsonl').read_text().splitlines()]
                for item in self.interruptions:
                    i = item.get('trial_index')
                    if type(i) is not int or not 0 <= i < len(self.order) or not finite(item.get('elapsed_seconds')):
                        raise BenchmarkError('resume_invalid_interruption_ledger')
                    if any(item.get(k) != self.order[i][1][k] for k in ('case', 'method', 'repeat')):
                        raise BenchmarkError('resume_interruption_schedule_mismatch')
            active = self.out / 'active-attempt.json'
            if active.exists():
                value = json.loads(active.read_text())
                accounted = any(x['attempt_id'] == value['attempt_id'] for x in self.interruptions)
                if value['trial_index'] >= len(self.rows) and not accounted:
                    raise BenchmarkError('unclean_exit_has_unmeasured_work_start_a_new_run')
                active.unlink()
        else:
            self.meta = {'schema_version': 1, 'run_id': secrets.token_hex(16), 'started_at': utc(),
                         'bank_sha256': self.identity['bank_sha256'], 'protocol_sha256': self.bank['protocol_sha256'],
                         'split': args.split, 'cases_sha256': self.section['cases_sha256'],
                         'original_schedule_sha256': self.section['schedule_sha256'],
                         'schedule_sha256': digest(self.schedule), 'derived_schedule_sha256': digest(self.schedule),
                         'schedule_derivation': 'original order preserved; filtered by selected_methods',
                         'selected_methods': self.selected, 'planned_trials': len(self.order), 'completed_trials': 0,
                         'independent_cases': len(self.cases), 'config_sha256': digest(self.config),
                         'run_fingerprint': self.fingerprint, 'code_hashes': self.code_hashes,
                         'programs': {k: v['public'] for k, v in self.specs.items()},
                         'fixture': any(v['fixture'] for v in self.specs.values()),
                         'status': 'preparing', 'global_deadline': None, 'final_sat_time_limit': None,
                         'timing_profile': 'generic-external-programs-v1',
                         'timing_note': 'oneshot includes program startup; resident excludes ready preparation. Clock ends at accepted proof receipt; final independent replay and cleanup are separate. Profiles must not be pooled with each other or an existing benchmark without matching controls.',
                         'host': {'system': platform.system(), 'release': platform.release(),
                                  'machine': platform.machine(), 'python': platform.python_version(),
                                  'logical_cpus_visible': os.cpu_count(),
                                  'affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None},
                         'attempts': []}
            atomic(self.out / 'schedule.json', self.schedule)
        self.meta['fixture'] = bool(self.meta.get('fixture') or any(v['fixture'] for v in self.specs.values()) or any(r.get('fixture') for r in self.rows))
        self.meta['measurement_kind'] = 'harness-smoke-only' if self.meta['fixture'] else 'external-program-benchmark'
        self.meta['performance_claims_allowed'] = not self.meta['fixture']
        self.private_state()
        self.save_meta()

    def read_completed_rows(self):
        path = self.out / 'runs.jsonl'
        raw = path.read_bytes() if path.exists() else b''
        offset = 0
        for line in raw.splitlines(keepends=True):
            if not line.endswith(b'\n'):
                with path.open('r+b') as stream:
                    stream.truncate(offset)
                    stream.flush()
                    os.fsync(stream.fileno())
                append(self.out / 'recovery.jsonl', {'at': utc(), 'discarded_incomplete_tail_bytes': len(line)})
                break
            row = json.loads(line)
            index = len(self.rows)
            if index >= len(self.order):
                raise BenchmarkError('resume_extra_completed_rows')
            expected = self.order[index][1]
            if row['trial_index'] != index or any(row[k] != expected[k] for k in ('case', 'method', 'repeat')):
                raise BenchmarkError('resume_completed_schedule_mismatch')
            if row.get('status') != 'found' or row.get('verified') is not True:
                raise BenchmarkError('resume_invalid_completed_row')
            verify(row['moves'], self.cases[row['case']]['board'])
            if not all(finite(row[k]) for k in ('wall_seconds', 'interrupted_work_seconds', 'effective_wall_seconds')) or abs(row['effective_wall_seconds'] - row['wall_seconds'] - row['interrupted_work_seconds']) > 1e-6:
                raise BenchmarkError('resume_invalid_timing')
            self.rows.append(row)
            offset += len(line)

    def private_state(self):
        atomic(self.out / 'private-runtime.json', {'config': self.config, 'identity': self.identity,
               'controller_pid': os.getpid(), 'owned_process_groups': [p.proc.pid for p in self.processes if p.proc is not None]}, private=True)

    def save_meta(self):
        self.meta['completed_trials'] = len(self.rows)
        self.meta['updated_at'] = utc()
        atomic(self.out / 'metadata.json', self.meta)

    def check_cancel(self):
        if self.cancelled:
            raise Cancelled()

    def heartbeat(self, force=False, phase=None):
        now = time.monotonic()
        if not force and now - self.last_heartbeat < 1:
            return
        event = {**(self.current or {}), 'updated_at': utc(),
                 'phase': phase or ('searching' if self.started is not None else 'preparing'),
                 'completed_trials': len(self.rows), 'planned_trials': len(self.order),
                 'external_progress_events': self.progress_events, 'global_deadline': None}
        if self.started is not None:
            event['elapsed_seconds'] = now - self.started
            atomic(self.out / 'active-attempt.json', {**event, 'attempt_id': self.attempt_id})
        atomic(self.out / 'progress.json', event)
        self.last_heartbeat = now

    def external_progress(self, event):
        self.progress_events += 1
        # Raw external messages may contain private paths or secrets; private logs
        # retain them, while the shareable progress file records receipt only.
        self.heartbeat(force=True)

    def detect_fixture(self, result, slot):
        if result.get('fixture') or result.get('measurement_kind') == 'harness-smoke-only':
            self.meta['fixture'] = True
            self.meta['measurement_kind'] = 'harness-smoke-only'
            self.meta['performance_claims_allowed'] = False
            self.meta['programs'][slot]['fixture'] = True
            self.save_meta()

    def prepared_process(self, slot):
        spec = self.specs[slot]
        if spec['mode'] == 'resident':
            if slot in self.residents:
                process = self.residents[slot]
                if process.stdout_done.is_set():
                    raise BenchmarkError('resident_exited_between_requests')
                return process
            process = Process(self, slot, spec)
            prep = process.prepare()
            append(self.out / 'preparation.jsonl', {**self.current, **prep})
            self.residents[slot] = process
            return process
        return Process(self, slot, spec)

    def record_interruption(self, reason):
        if self.started is None:
            return
        item = {**self.current, 'attempt_id': self.attempt_id, 'at': utc(),
                'elapsed_seconds': time.monotonic() - self.started, 'reason': reason}
        append(self.out / 'interruptions.jsonl', item)
        self.interruptions.append(item)
        self.started = None
        (self.out / 'active-attempt.json').unlink(missing_ok=True)

    def execute(self):
        old_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        for sig in old_handlers:
            signal.signal(sig, lambda signum, frame: setattr(self, 'cancelled', True))
        attempt = {'started_at': utc(), 'first_trial_index': len(self.rows)}
        self.meta['attempts'].append(attempt)
        self.meta['status'] = 'running'
        self.save_meta()
        exit_code = 0
        try:
            for index in range(len(self.rows), len(self.order)):
                self.check_cancel()
                original_index, trial = self.order[index]
                self.current = {'trial_index': index, 'original_trial_index': original_index,
                                'case': trial['case'], 'repeat': trial['repeat'], 'method': trial['method']}
                self.started = None
                while self.pause_file.exists():
                    self.meta['status'] = 'paused'
                    self.save_meta()
                    self.heartbeat(force=True, phase='paused_between_trials')
                    self.check_cancel()
                    time.sleep(.2)
                self.meta['status'] = 'running'
                slot = trial['method']
                process = self.prepared_process(slot)
                self.attempt_id = secrets.token_hex(16)
                request_id = digest([self.meta['run_id'], index, self.attempt_id])[:32]
                request = {'id': request_id, 'board': self.cases[trial['case']]['board']}
                self.check_cancel()
                self.started = time.monotonic()
                self.heartbeat(force=True, phase='trial_start')
                if process.spec['mode'] == 'oneshot':
                    process.start()
                received, result = process.request(request)
                if result.get('id') not in (None, request_id):
                    raise BenchmarkError('response_request_id_mismatch')
                self.detect_fixture(result, slot)
                if result.get('status') != 'found':
                    raise BenchmarkError('external_result_not_found')
                checking = time.monotonic()
                normalized = verify(result.get('moves'), request['board'])
                verification = time.monotonic() - checking
                self.check_cancel()
                elapsed = received - self.started
                if not finite(elapsed):
                    raise BenchmarkError('invalid_proof_receipt_time')
                prior = sum(x['elapsed_seconds'] for x in self.interruptions if x['trial_index'] == index)
                fixture = bool(self.meta['fixture'] or self.specs[slot]['fixture'])
                row = {**self.current, 'status': 'found', 'verified': True, 'success': 1,
                       'moves': normalized['moves'], 'placements': normalized['placements'],
                       'passes': normalized['passes'], 'terminal': normalized['terminal'],
                       'wall_seconds': elapsed, 'interrupted_work_seconds': prior,
                       'effective_wall_seconds': elapsed + prior, 'verification_seconds': verification,
                       'global_deadline': None, 'final_sat_time_limit': None,
                       'timing_profile': PROFILES[process.spec['mode']],
                       'label': self.meta['programs'][slot]['label'], 'request_id': request_id,
                       'fixture': fixture, 'measurement_kind': 'harness-smoke-only' if fixture else 'external-program-benchmark'}
                append(self.out / 'runs.jsonl', row)
                self.rows.append(row)
                self.started = None
                (self.out / 'active-attempt.json').unlink(missing_ok=True)
                if process.spec['mode'] == 'oneshot':
                    process.close()
                self.save_meta()
                self.heartbeat(force=True, phase='trial_complete')
                print(json.dumps({k: row[k] for k in ('trial_index', 'case', 'method', 'repeat', 'status', 'wall_seconds', 'fixture')}), flush=True)
            self.meta['status'] = 'complete'
        except Cancelled:
            self.record_interruption('manual_cancel')
            self.meta['status'] = 'interrupted'
            exit_code = 130
        except BaseException as exc:
            self.record_interruption('attempt_error')
            code = exc.code if isinstance(exc, BenchmarkError) else 'verification_or_runtime_error'
            append(self.out / 'errors.jsonl', {**(self.current or {}), 'at': utc(),
                   'attempt_id': self.attempt_id, 'category': code, 'status': 'error'})
            append(self.logs / 'errors.jsonl', {'at': utc(), 'exception': repr(exc),
                   'traceback': traceback.format_exc()}, private=True)
            self.meta['status'] = 'error'
            self.meta['last_error_category'] = code
            exit_code = 2
        finally:
            cleanup_failed = False
            for process in list(self.processes):
                try:
                    process.close()
                except BaseException as exc:
                    cleanup_failed = True
                    append(self.logs / 'errors.jsonl', {'at': utc(), 'category': 'owned_process_group_cleanup_failed',
                           'exception': repr(exc), 'traceback': traceback.format_exc()}, private=True)
            if cleanup_failed:
                self.meta['status'] = 'error'
                self.meta['last_error_category'] = 'owned_process_group_cleanup_failed'
                exit_code = 2
            attempt.update(finished_at=utc(), completed_trials=len(self.rows),
                           program_wall_seconds=time.monotonic() - self.program_started)
            self.meta['completed_trials'] = len(self.rows)
            self.meta['finished_at'] = utc()
            self.meta['program_wall_seconds'] = time.monotonic() - self.program_started
            self.save_meta()
            self.heartbeat(force=True, phase=self.meta['status'])
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)
            self.lock.close()
        print(json.dumps({'status': self.meta['status'], 'completed_trials': len(self.rows),
                          'planned_trials': len(self.order), 'fixture': self.meta['fixture']}), flush=True)
        return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run', help='run the frozen schedule without trial deadlines')
    run.add_argument('--bank', type=Path, required=True)
    run.add_argument('--config', type=Path, required=True)
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--split', choices=('main', 'pilot'), default='main')
    run.add_argument('--method', choices=('sat', 'auto'))
    run.add_argument('--resume', action='store_true')
    run.add_argument('--pause-file', type=Path)
    args = parser.parse_args()
    if os.name != 'posix':
        parser.error('this version requires POSIX process groups; use Linux, macOS, or WSL')
    try:
        return Run(args).execute()
    except Exception as exc:
        # Never expose arbitrary program stderr, command paths, configured secrets,
        # or verification payloads through the shareable terminal summary.
        code = exc.code if isinstance(exc, BenchmarkError) else 'invalid_input_or_setup'
        print('benchmark: ' + code, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
