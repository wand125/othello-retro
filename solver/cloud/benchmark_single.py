"""Private administrative benchmark: run the identical local CLI in a fresh process.

Never exposed through the public solve request schema. Cloud app integration must
require a server-created Firestore item with benchmark=True.
"""
import functools
import hashlib
import importlib.metadata
import json
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@functools.lru_cache(maxsize=1)
def environment():
    # Introspect the actual worker environment, outside the measured CLI process.
    sys.path.insert(0, str(ROOT / 'ml'))
    import search
    import torch
    paths = ['target/release/othello-retro', 'ml/model.pt', 'ml/model_passes.pt',
             'ml/worker.py', 'ml/search.py', 'ui/server.py', 'benchmarks/run.py']
    kissat = subprocess.run(['kissat', '--version'], text=True, capture_output=True,
                            check=True, timeout=10).stdout.strip()
    return {'platform': platform.platform(), 'machine': platform.machine(),
            'python': platform.python_version(), 'logical_cpus_visible': os.cpu_count(),
            'torch_version': torch.__version__, 'numpy_version': importlib.metadata.version('numpy'),
            'device': str(search.DEV), 'torch_threads': torch.get_num_threads(),
            'thread_environment': {k: os.environ.get(k) for k in
                ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OTHELLO_DEVICE', 'RETRO_DEVICE', 'RETRO_TORCH_THREADS']},
            'kissat_version': kissat,
            'hashes': {p: _sha(ROOT / p) for p in paths},
            'note': 'Fresh CLI subprocess per trial; OS caches are not reset. Times exclude Cloud Tasks, HTTP, polling and this metadata collection.'}


def _terminate(process):
    if process.poll() is None:
        # run.py handles SIGTERM and cleans model/SAT subprocesses, including
        # their separate process groups. Give that handler time to complete.
        process.terminate()
        try:
            process.communicate(timeout=7)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate(timeout=5)
    else:
        process.communicate()


def run(request, job=None):
    """Return normal solver result plus benchmark measurement and environment.

    request = {board: 64-char X/O/- string, method: sat|auto,
               model_start: cold|warm, limit: integer seconds}.
    job optionally connects the subprocess to the Cloud worker cancellation map.
    """
    board, method = request.get('board'), request.get('method')
    model_start, limit = request.get('model_start'), request.get('limit')
    if not isinstance(board, str) or len(board) != 64 or set(board) - set('XO-'):
        raise ValueError('invalid benchmark board')
    if method not in ('sat', 'auto') or model_start not in ('cold', 'warm'):
        raise ValueError('invalid benchmark method/start condition')
    if type(limit) is not int or not 2 <= limit <= 300:
        raise ValueError('invalid benchmark time limit')
    normalized = {'board': board, 'method': method, 'model_start': model_start, 'limit': limit}
    env = environment()
    process = subprocess.Popen([sys.executable, str(ROOT / 'benchmarks/run.py'), '--_single'],
                               cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    local = None
    if job:
        sys.path.insert(0, str(ROOT / 'ui'))
        import server as local
        with local.LOCK:
            local.JOBS[job] = process
    started = time.monotonic()
    try:
        stdout, stderr = process.communicate(json.dumps(normalized),
                         timeout=limit + (75 if model_start == 'warm' else 15))
        if process.returncode:
            raise RuntimeError('benchmark CLI exit ' + str(process.returncode) + ': ' + stderr[-1000:])
        measured = json.loads(stdout.strip().splitlines()[-1])
        result = measured.pop('result')
        if not isinstance(result, dict) or 'status' not in result:
            raise ValueError('invalid benchmark CLI response')
        measured.update({'request': normalized, 'environment': env,
                         'invocation_seconds': round(time.monotonic() - started, 6)})
        result['benchmark'] = measured
        return result
    finally:
        _terminate(process)
        if local is not None:
            with local.LOCK:
                if local.JOBS.get(job) is process:
                    del local.JOBS[job]
