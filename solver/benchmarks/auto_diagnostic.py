"""Paired, local diagnosis of guided hits and inference cost; no public API calls.

This is a separate experiment, not a replacement for the frozen benchmark.
Finite 2s/20s probes are retained; final exact SAT has no time limit.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import math
import signal
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def choose(bank, count, suite, split):
    if count == 0:
        return []
    if split not in bank['splits']:
        raise ValueError(f'{suite} bank has no {split} split')
    cases = bank['splits'][split]['cases']
    if suite == 'midgame':
        cases = [c for c in cases if c['stones'] == 44]
    # Predeclared selection, independent of observed solver outcomes.
    cases = sorted(cases, key=lambda c: hashlib.sha256(('auto-diagnostic-v1:' + c['id']).encode()).hexdigest())
    if count > len(cases):
        raise ValueError(f'{suite}: requested {count} cases, only {len(cases)} available')
    return [{**c, 'suite': suite} for c in cases[:count]]


def validate_resume(previous, rows, current, verify):
    """Accept only a durable strict prefix with identical algorithms and environment."""
    if previous.get('status') != 'interrupted':
        raise ValueError('resume requires a cleanly interrupted run')
    for key in ['platform', 'python', 'torch', 'numpy', 'threads', 'affinity', 'nice',
                'banks_sha256', 'binaries_sha256', 'selected_cases', 'schedule', 'split', 'variants']:
        if previous.get(key) != current.get(key):
            raise ValueError('resume configuration changed: ' + key)
    driver = 'benchmarks/auto_diagnostic.py'
    old = {k:v for k,v in previous['source_sha256'].items() if k != driver}
    new = {k:v for k,v in current['source_sha256'].items() if k != driver}
    if old != new:
        raise ValueError('resume algorithm/source/weights changed')
    if len(rows) != previous.get('completed_trials') or len(rows) >= len(current['schedule']):
        raise ValueError('completed count mismatch or no remaining work')
    cases = {c['id']: c for c in current['selected_cases']}
    for row, planned in zip(rows, current['schedule']):
        if any(row.get(k) != v for k,v in planned.items()):
            raise ValueError('completed rows are not an exact schedule prefix')
        if row.get('status') != 'found' or row.get('verified') is not True:
            raise ValueError('completed row is not a verified witness')
        seconds = row.get('wall_seconds')
        if isinstance(seconds, bool) or not isinstance(seconds, (int,float)) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError('invalid completed trial timing')
        verify(row['moves'], cases[row['case']]['board'])
    return rows


def main():
    program_started = time.monotonic()
    program_started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--split', choices=['pilot', 'main'], default='main')
    p.add_argument('--midgame-count', type=int, default=12)
    p.add_argument('--endgame-count', type=int, default=20)
    p.add_argument('--repeat', type=int, default=3)
    p.add_argument('--variants', nargs='+', choices=['sat', 'baseline', 'fixed_baseline', 'fused', 'channels_last', 'fused_channels_last', 'lightweight'], default=['sat', 'baseline', 'lightweight'])
    p.add_argument('--baseline-bin', type=Path)
    p.add_argument('--candidate-bin', type=Path)
    p.add_argument('--resume', action='store_true')
    args = p.parse_args()
    if args.repeat < 1 or min(args.midgame_count, args.endgame_count) < 0:
        p.error('positive repeats and nonnegative case counts required')
    if len(set(args.variants)) != len(args.variants):
        p.error('duplicate variants are not allowed')
    if args.resume:
        if not args.output.is_dir():
            p.error('--resume requires an existing output directory')
    else:
        args.output.mkdir(parents=True, exist_ok=False)
    os.environ.update(OTHELLO_DEVICE='cpu', RETRO_HALF='0', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', RETRO_INFERENCE_OPT='baseline', RETRO_AUTO_POLICY='baseline')
    sys.path[:0] = [str(ROOT / 'ml'), str(ROOT / 'cloud')]
    import torch
    import search
    import worker
    import unbounded_engine
    from records import verify

    torch.set_num_threads(2)
    banks = {s: ROOT / 'benchmarks' / f'study-{s}-cpu222-unbounded-v1.json' for s in ['midgame', 'endgame']}
    selected = []
    for suite, path in banks.items():
        selected += choose(json.loads(path.read_text()), getattr(args, suite + '_count'), suite, args.split)
    if not selected:
        p.error('no selected cases')
    for case in selected:
        verify(case['reference_moves'], case['board'])
    schedule = []
    for repeat in range(1, args.repeat + 1):
        for index, case in enumerate(selected):
            offset = (index + repeat - 1) % len(args.variants)
            order = args.variants[offset:] + args.variants[:offset]
            schedule += [{'case': case['id'], 'suite': case['suite'], 'repeat': repeat, 'variant': v} for v in order]
    protected = [ROOT / 'ml' / n for n in ['search.py', 'worker.py', 'train.py', 'model.pt', 'model_passes.pt']]
    protected += [Path(__file__), ROOT / 'benchmarks/unbounded_engine.py', ROOT / 'target/release/othello-retro']
    if (ROOT / 'ml/inference_opt.py').exists():
        protected.append(ROOT / 'ml/inference_opt.py')
    protected += [ROOT / name for name in ['ml/lightweight.py', 'ui/auto_policy.py', 'ui/server.py'] if (ROOT / name).exists()]
    meta = {'started_at': program_started_at,
            'platform': platform.platform(), 'python': platform.python_version(), 'torch': torch.__version__,
            'numpy': __import__('numpy').__version__, 'threads': torch.get_num_threads(),
            'affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
            'nice': os.getpriority(os.PRIO_PROCESS, 0), 'banks_sha256': {s: sha(f) for s, f in banks.items()},
            'source_sha256': {str(f.relative_to(ROOT)): sha(f) for f in protected},
            'binaries_sha256': {k: sha(v) for k, v in [('baseline', args.baseline_bin), ('candidate', args.candidate_bin)] if v},
            'selected_cases': selected, 'schedule': schedule, 'split': args.split,
            'timing': 'Preloaded/warmed models. Same local in-process harness for baseline/optimized. Instrumentation is included. Final replay excluded from accepted-proof receipt time. No trial cutoff.',
            'scope': 'Exploratory selected active-route cases; not a replacement for 400-case/four-environment results.',
            'variants': {'sat': 'original native exact SAT', 'baseline': 'original native and inference',
                'fixed_baseline': 'terminal-undo native correction, original inference',
                'fused_channels_last': 'candidate native plus Conv-BN fusion and channels-last inference',
                'lightweight': 'candidate native, fused channels-last; incomplete-terminal exact routing; width16/nsym1/refine0 single guided stage'},
            'status': 'running'}
    rows = []
    attempts = []
    if args.resume:
        previous = json.loads((args.output / 'metadata.json').read_text())
        rows = [json.loads(line) for line in (args.output / 'runs.jsonl').read_text().splitlines() if line.strip()]
        validate_resume(previous, rows, meta, verify)
        attempts = previous.get('attempts') or [{
            'started_at': previous['started_at'], 'finished_at': previous['finished_at'],
            'program_wall_seconds': previous['program_wall_seconds'],
            'model_preparation_seconds': previous.get('model_preparation_seconds'),
            'initial_completed_trials': 0, 'completed_trials': len(rows), 'status': previous['status'],
            'runner_sha256': previous['source_sha256']['benchmarks/auto_diagnostic.py']}]
        archive = args.output / 'attempt-history'
        archive.mkdir(exist_ok=True)
        write(archive / ('before-resume-%03d.json' % (len(attempts)+1)), previous)
        (archive / ('runner-attempt-%03d.py' % (len(attempts)+1))).write_bytes(Path(__file__).read_bytes())
        meta['started_at'] = previous['started_at']
        meta['resume_history'] = previous.get('resume_history', []) + [{
            'at': program_started_at, 'resumed_schedule_index': len(rows),
            'old_runner_sha256': previous['source_sha256']['benchmarks/auto_diagnostic.py'],
            'new_runner_sha256': meta['source_sha256']['benchmarks/auto_diagnostic.py'],
            'algorithm_hashes_unchanged': True, 'completed_prefix_strictly_replayed': True}]
        meta['interrupted_work_accounting'] = 'Previous unfinished work has no exact trial timer. Its saved interruption audit is retained separately, never imputed into a completed row or counted as failure. Program wall includes executed interrupted work and preparation; excludes between-attempt pauses.'
    attempt = {'started_at': program_started_at, 'initial_completed_trials': len(rows),
               'runner_sha256': meta['source_sha256']['benchmarks/auto_diagnostic.py']}
    meta['attempts'] = attempts + [attempt]
    write(args.output / 'metadata.json', meta)
    children = []
    original_popen = subprocess.Popen

    def popen(*a, **kw):
        kw['start_new_session'] = True
        proc = original_popen(*a, **kw)
        children.append(proc)
        return proc

    subprocess.Popen = popen
    metrics = {}
    stage = None

    def timed(bucket, fn):
        def call(*a, **kw):
            start = time.monotonic()
            try:
                return fn(*a, **kw)
            finally:
                entry = metrics.setdefault(bucket, {'calls': 0, 'seconds': 0.0})
                entry['calls'] += 1
                entry['seconds'] += time.monotonic() - start
        return call

    search.score = timed('score_pipeline', search.score)
    search.planes_batch = timed('planes', search.planes_batch)
    search.Undo.many = timed('undo', search.Undo.many)
    original_find = search.findany
    original_beam = search.beam

    def find(candidates, budget):
        start = time.monotonic()
        result = original_find(candidates, budget)
        metrics.setdefault('sat_calls', []).append({'stage': stage, 'candidate_count': len(candidates),
            'requested_per_solver_limit_seconds': budget, 'seconds': time.monotonic() - start,
            'found': result.get('index') is not None, 'winning_index_in_chunk': result.get('index'),
            'unsat': result.get('unsat'), 'candidates_hex': candidates})
        return result

    def beam(*a, **kw):
        start = time.monotonic()
        result = original_beam(*a, **kw)
        metrics.setdefault('beams', []).append({'stage': stage, 'seconds': time.monotonic() - start,
            'candidate_count': len(result), 'width': a[3], 'nsym': kw.get('nsym'), 'refine': kw.get('refine'), 'passes': kw.get('passes')})
        return result

    search.findany, search.beam = find, beam

    def emit(event):
        nonlocal stage
        stage = event.get('stage', stage)
        write(args.output / 'progress.json', {**current, **event})

    def cleanup(*_):
        for proc in children:
            if proc.poll() is not None:
                continue
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for proc in children:
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()

    def interrupt(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    models, undos = {}, {}
    try:
        preparation_started = time.monotonic()
        for variant in args.variants:
            if variant == 'sat':
                continue
            pair = [worker.load(str(ROOT / 'ml' / name)) for name in ['model.pt', 'model_passes.pt']]
            if variant not in ['baseline', 'fixed_baseline']:
                from inference_opt import optimize
                pair = [optimize(net, 'fused_channels_last' if variant == 'lightweight' else variant) for net in pair]
            for net in pair:
                x = torch.zeros((256, 5, 8, 8))
                with torch.inference_mode():
                    for _ in range(3):
                        net(x, None)
                original_forward = net.forward
                net.forward = timed('cnn_forward', original_forward)
            models[variant] = pair
            binary = args.baseline_bin if variant == 'baseline' else args.candidate_bin
            search.BIN = str(binary.resolve()) if binary else str(ROOT / 'target/release/othello-retro')
            undos[variant] = search.Undo()
        attempt['model_preparation_seconds'] = time.monotonic() - preparation_started
        meta['model_preparation_seconds'] = sum(a.get('model_preparation_seconds') or 0 for a in meta['attempts'])
        write(args.output / 'metadata.json', meta)
        case_map = {c['id']: c for c in selected}
        for current in schedule[len(rows):]:
            case = case_map[current['case']]
            metrics, stage = {}, None
            binary = args.baseline_bin if current['variant'] in ['baseline', 'sat'] else args.candidate_bin
            search.BIN = str(binary.resolve()) if binary else str(ROOT / 'target/release/othello-retro')
            start = time.monotonic()
            result = None
            guided_seconds = 0.0
            rejected = False
            miss_reason = None
            if current['variant'] != 'sat':
                net, passes = models[current['variant']]
                try:
                    if current['variant'] == 'lightweight':
                        from lightweight import handle as light_handle
                        candidate = light_handle(net, undos[current['variant']], {'board': case['board'], 'time': None}, passes, emit)
                    else:
                        candidate = unbounded_engine.guided(net, passes, undos[current['variant']], {'board': case['board']}, emit)
                except Exception as exc:
                    metrics['guided_exception_type'] = type(exc).__name__
                    candidate = {'status': 'miss', 'reason': 'guided_exception:' + type(exc).__name__}
                received = time.monotonic()
                guided_seconds = received - start
                miss_reason = candidate.get('reason')
                if candidate.get('status') == 'found':
                    try:
                        normalized, _ = verify(candidate['moves'], case['board'])
                        result = {**candidate, 'moves': normalized}
                    except (ValueError, KeyError):
                        rejected = True
            if result is None:
                sat_start = time.monotonic()
                proc = subprocess.run([search.BIN, 'solve', case['board'], '--json', '--no-time-limit'], capture_output=True, text=True, check=True)
                result = json.loads(proc.stdout.strip().splitlines()[-1])
                received = time.monotonic()
                metrics['final_sat_seconds'] = received - sat_start
            normalized, _ = verify(result['moves'], case['board'])
            assert result['status'] == 'found'
            cnn_used = metrics.get('cnn_forward', {}).get('calls', 0) > 0
            row = {**current, 'stones': case['stones'], 'status': result['status'], 'verified': True,
                'wall_seconds': received - start, 'guided_seconds': guided_seconds,
                'stage': result.get('stage', 'final_exact_sat'), 'cnn_used': cnn_used,
                'guided_hit': result.get('stage') in ['fast', 'careful', 'with-passes'],
                'guided_candidate_rejected': rejected,
                'guided_miss_reason': miss_reason,
                'planned_exact_route': miss_reason == 'incomplete_terminal_exact_route',
                'fallback': current['variant'] != 'sat' and 'final_sat_seconds' in metrics,
                'moves': normalized, 'metrics': metrics}
            rows.append(row)
            with (args.output / 'runs.jsonl').open('a') as f:
                f.write(json.dumps(row) + '\n')
                f.flush()
                os.fsync(f.fileno())
            write(args.output / 'progress.json', {'completed': len(rows), 'planned': len(schedule), **current,
                'seconds': row['wall_seconds'], 'stage': row['stage']})
            print(json.dumps({k: row[k] for k in ['case', 'suite', 'repeat', 'variant', 'wall_seconds', 'stage', 'cnn_used', 'guided_hit']}), flush=True)
        summary = {}
        for suite in ['midgame', 'endgame']:
            for variant in args.variants:
                group = [r for r in rows if r['suite'] == suite and r['variant'] == variant]
                if group:
                    summary[suite + ':' + variant] = {'trials': len(group), 'independent_cases': len({r['case'] for r in group}),
                        'mean_seconds': statistics.mean(r['wall_seconds'] for r in group),
                        'median_seconds': statistics.median(r['wall_seconds'] for r in group),
                        'stages': dict(collections.Counter(r['stage'] for r in group)),
                        'cnn_used': sum(r['cnn_used'] for r in group), 'guided_hits': sum(r['guided_hit'] for r in group),
                        'fallbacks': sum(r['fallback'] for r in group)}
        write(args.output / 'summary.json', summary)
        meta['status'] = 'complete'
        meta['completed_trials'] = len(rows)
    except BaseException as exc:
        meta['status'] = 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'error'
        meta['error_type'] = type(exc).__name__
        meta['completed_trials'] = len(rows)
        raise
    finally:
        cleanup()
        meta['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        attempt.update(finished_at=meta['finished_at'], program_wall_seconds=time.monotonic() - program_started,
                       completed_trials=len(rows), status=meta['status'])
        meta['program_wall_seconds'] = sum(a['program_wall_seconds'] for a in meta['attempts'])
        meta['overall_calendar_span_seconds'] = (dt.datetime.fromisoformat(meta['finished_at']) - dt.datetime.fromisoformat(meta['started_at'])).total_seconds()
        write(args.output / 'metadata.json', meta)


if __name__ == '__main__':
    main()
