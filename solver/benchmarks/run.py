"""Local, sequential SAT vs production-pipeline benchmark. No browser or network."""
import argparse
import csv
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cloud'))
from build_examples import verify


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Deadline(Exception): pass


def single(request):
    sys.path.insert(0, str(ROOT / 'ui'))
    import server
    class Runner:
        result = None
        def finish_job(self, job, result): self.result = result

    def cleanup():
        model = server.WORKER.proc
        server.WORKER.kill()
        if model:
            try: model.wait(timeout=3)
            except subprocess.TimeoutExpired: model.kill(); model.wait()
        for process in list(server.JOBS.values()):
            if isinstance(process, subprocess.Popen): server.kill_job(process)

    def timeout(signum, frame):
        signal.setitimer(signal.ITIMER_REAL, 0)
        cleanup()  # Kill tracked children before stack unwinding removes their job entries.
        raise Deadline()

    signal.signal(signal.SIGALRM, timeout)
    signal.signal(signal.SIGTERM, timeout)
    if request['method'] == 'sat': server.BEAM_MIN_MOVES = 1000
    runner, preload, started = Runner(), 0, time.monotonic()
    try:
        if request['model_start'] == 'warm' and request['method'] == 'auto' and request['board'].count('-') <= 20:
            signal.setitimer(signal.ITIMER_REAL, 60)
            if not server.WORKER._ensure(): raise RuntimeError('model worker could not start')
            preload = time.monotonic() - started
        started = time.monotonic()
        signal.setitimer(signal.ITIMER_REAL, request['limit'] + 1)
        server.Handler.run_solver(runner, request['board'], request['limit'], 'local_benchmark')
        result = runner.result or {'status':'error', 'reason':'missing result'}
    except Deadline:
        result = {'status':'unknown', 'reason':'external deadline'}
    except Exception as error:
        result = {'status':'error', 'reason':str(error)}
    finally:
        elapsed = time.monotonic() - started
        signal.setitimer(signal.ITIMER_REAL, 0)
        cleanup()
    # ru_maxrss is the largest single-process peak, not a sum or GPU-memory estimate.
    peak = max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    peak /= 1024 * 1024 if sys.platform == 'darwin' else 1024
    print(json.dumps({'result':result, 'wall_seconds':round(elapsed, 6),
                      'model_preload_seconds':round(preload, 6),
                      'largest_process_peak_rss_mib':round(peak, 2)}), flush=True)


def summarize(rows, limit):
    output = []
    for method in dict.fromkeys(row['method'] for row in rows):
        selected = [r for r in rows if r['method'] == method]
        positives = [r for r in selected if r['expected'] == 'reachable']
        negatives = [r for r in selected if r['expected'] == 'unreachable']
        successes = [r for r in positives if r['correct']]
        times = [r['wall_seconds'] for r in successes]
        output.append({'method':method, 'reachable_runs':len(positives), 'found_verified':len(successes),
                       'unreachable_runs':len(negatives), 'unreachable_correct':sum(r['correct'] for r in negatives),
                       'unknown':sum(r['status']=='unknown' for r in selected),
                       'invalid_or_wrong':sum(r['invalid_or_wrong'] for r in selected),
                       'successful_median_seconds':round(statistics.median(times), 4) if times else None,
                       'failure_penalized_mean_seconds':round(statistics.mean(r['wall_seconds'] if r['correct'] else 2*limit for r in positives),4) if positives else None})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=Path(__file__).with_name('cases.json'))
    parser.add_argument('--only', nargs='+', help='Case IDs to run')
    parser.add_argument('--methods', nargs='+', choices=['sat','auto'], default=['sat','auto'])
    parser.add_argument('--time', type=int, default=60, help='Same time budget for each method/case')
    parser.add_argument('--repeat', type=int, default=1)
    parser.add_argument('--model-start', choices=['cold','warm'], default='cold')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--_single', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._single: single(json.load(sys.stdin)); return
    if args.time < 2 or args.repeat < 1: parser.error('--time >= 2 and --repeat >= 1 required')
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    output = args.output or Path(__file__).with_name('results') / stamp
    output.mkdir(parents=True, exist_ok=False)
    cases = json.loads(args.cases.read_text())['cases']
    if args.only:
        cases = [case for case in cases if case['id'] in args.only]
        if set(args.only) != {case['id'] for case in cases}: parser.error('unknown case ID')
    for case in cases:
        if case['expected'] == 'reachable': verify(case['reference_moves'], case['board'])
        else: assert case['id']=='missing-center' and case['board'][27]=='-'
    protected = [ROOT/'target/release/othello-retro', ROOT/'ml/model.pt', ROOT/'ml/model_passes.pt',
                 ROOT/'ml/worker.py', ROOT/'ml/search.py', ROOT/'ui/server.py', ROOT/'benchmarks/run.py']
    metadata = {'started_at':dt.datetime.now(dt.timezone.utc).isoformat(), 'platform':platform.platform(),
                'machine':platform.machine(), 'python':platform.python_version(), 'logical_cpus':os.cpu_count(),
                'torch_version':importlib.metadata.version('torch'), 'time_limit_seconds':args.time,
                'repeat':args.repeat, 'model_start':args.model_start, 'cases_sha256':sha(args.cases),
                'device_requested':os.environ.get('OTHELLO_DEVICE', 'auto'),
                'environment':{key:os.environ.get(key) for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','RETRO_HALF','RETRO_NSYM','RETRO_REFINE')},
                'affinity':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
                'nice':os.getpriority(os.PRIO_PROCESS,0),
                'trial_order':'repeat outer, fixed case order, method order reversed when (case_index+repeat_index) is odd',
                'hashes':{str(p.relative_to(ROOT)):sha(p) for p in protected},
                'note':'Sequential local processes. Cold means a fresh model worker; OS caches are not reset. No public API or browser calls.'}
    (output/'metadata.json').write_text(json.dumps(metadata, indent=2))
    rows = []
    for repeat in range(args.repeat):
        for index, case in enumerate(cases):
            # Alternate order to reduce one method always getting the first filesystem read.
            order = args.methods if (index + repeat) % 2 == 0 else list(reversed(args.methods))
            for method in order:
                request = {'board':case['board'], 'method':method, 'limit':args.time, 'model_start':args.model_start}
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--_single'],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
                try:
                    stdout, stderr = process.communicate(json.dumps(request), timeout=args.time + (75 if args.model_start=='warm' else 15))
                    if process.returncode: raise RuntimeError(stderr[-1000:] or f'exit {process.returncode}')
                    measured = json.loads(stdout.strip().splitlines()[-1])
                except (subprocess.TimeoutExpired, KeyboardInterrupt):
                    process.terminate()
                    try: process.communicate(timeout=5)
                    except subprocess.TimeoutExpired: process.kill(); process.communicate()
                    raise
                result = measured.pop('result'); status = result.get('status','error')
                verified, invalid = False, False
                if status == 'found':
                    try: verify(result['moves'], case['board']); verified = True
                    except (AssertionError, KeyError, ValueError): invalid = True
                if (status=='unreachable' and case['expected']=='reachable') or (status=='found' and case['expected']=='unreachable'): invalid = True
                within = measured['wall_seconds'] <= args.time + .25
                correct = not invalid and within and (verified if case['expected']=='reachable' else status=='unreachable')
                row = {'case':case['id'], 'title':case['title'], 'public_url':case.get('public_url'),
                       'expected':case['expected'], 'method':method, 'actual_method':result.get('method'),
                       'repeat':repeat+1, 'status':status, 'verified':verified, 'within_budget':within,
                       'correct':correct, 'invalid_or_wrong':invalid, **measured, 'moves':result.get('moves',[]),
                       'reason':result.get('reason','')}
                rows.append(row)
                with (output/'runs.jsonl').open('a') as f: f.write(json.dumps(row,ensure_ascii=False)+'\n')
                print(json.dumps({k:row[k] for k in ('case','method','status','wall_seconds','correct')},ensure_ascii=False),flush=True)
    summary = summarize(rows, args.time)
    (output/'summary.json').write_text(json.dumps({'metadata':metadata,'summary':summary,'runs':rows},ensure_ascii=False,indent=2))
    columns = ['case','title','method','repeat','status','wall_seconds','verified','within_budget','correct','largest_process_peak_rss_mib','model_preload_seconds','public_url']
    with (output/'runs.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    lines = ['# ローカル復元ベンチマーク', '', f'各方式・各盤面 {args.time}秒、{args.repeat}回。モデル開始条件: {args.model_start}。',
             '公開APIの通信や待ち行列を含まない、ローカル実行時間です。', '', '| 方式 | 到達可能の復元 | 到達不能の判定 | 成功時中央値（秒） | 失敗を制限の2倍とした平均（秒） |',
             '|---|---:|---:|---:|---:|']
    for s in summary: lines.append(f"| {s['method']} | {s['found_verified']}/{s['reachable_runs']} | {s['unreachable_correct']}/{s['unreachable_runs']} | {s['successful_median_seconds']} | {s['failure_penalized_mean_seconds']} |")
    lines += ['', '中央値は成功した到達可能盤面だけを集計します。失敗を含む平均は各失敗を制限時間の2倍として集計します。異なる盤面を含む小規模セットのため、一般的な速度保証ではありません。',
              '', '| 盤面 | 方式 | 結果 | 秒 | 検証 |', '|---|---|---|---:|---|']
    for r in rows: lines.append(f"| {r['title']} | {r['method']} | {r['status']} | {r['wall_seconds']:.3f} | {'OK' if r['correct'] else '未達'} |")
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'output':str(output),'summary':summary},ensure_ascii=False),flush=True)
    if any(r['invalid_or_wrong'] for r in rows): raise SystemExit(1)


if __name__ == '__main__': main()
