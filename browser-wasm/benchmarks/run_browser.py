#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure real desktop Chrome Workers; no smartphone or Worker throttle claim.

Requires Python 3.10+ and Playwright (no package installation is performed).
Example:
  python3 run_browser.py --url http://127.0.0.1:18821/ --cases cases.json \
    --output results/browser-auto --engines auto --repeats 1 --deadline 60

The output must be new/empty. Each observation is appended and fsynced to
runs.jsonl. The observational watchdog terminates its Worker and records unknown,
never unreachable. The browser context blocks Service Workers and network routes
disable the HTTP cache: every trial is a fresh Worker, including runtime/model
initialization and resource fetch. This differs from resident/warm native runs.
The main-page independent rules checker runs after proof receipt, outside timing.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BASE_ASSETS = ('solver-worker.js', 'verify.js', 'engine.js', 'encoder.wasm', 'kissat.js', 'kissat.wasm')
AUTO_ASSETS = ('auto.js', 'inference/infer.js', 'inference/ort.wasm.min.js',
               'inference/ort-wasm-simd-threaded.mjs', 'inference/ort-wasm-simd-threaded.wasm',
               'models/model.fused.onnx', 'models/model_passes.fused.onnx')


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def write_json(path, value):
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)


def append(path, value):
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
        f.flush(); os.fsync(f.fileno())


def read_cases(paths):
    rows, banks, seen = [], [], set()
    for path in paths:
        raw = path.read_bytes(); data = json.loads(raw)
        cases = data if isinstance(data, list) else data.get('cases')
        if not isinstance(cases, list) or not cases:
            raise ValueError('case file must contain a nonempty cases array')
        banks.append({'name': path.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                      'source_sha256': data.get('source_sha256') if isinstance(data, dict) else None,
                      'selection': data.get('selection') if isinstance(data, dict) else None,
                      'cases': len(cases)})
        for case in cases:
            if not isinstance(case, dict) or not isinstance(case.get('id'), str) or case['id'] in seen:
                raise ValueError('invalid or duplicate case ID')
            if not isinstance(case.get('board'), str) or not re.fullmatch('[XO-]{64}', case['board']):
                raise ValueError('invalid 64-cell target for ' + case['id'])
            if case.get('expected') not in (None, 'reachable', 'unreachable', 'unknown'):
                raise ValueError('invalid expected status for ' + case['id'])
            seen.add(case['id']); rows.append(case)
    return rows, banks


def fetch_assets(base, engines):
    names = BASE_ASSETS + (AUTO_ASSETS if 'auto' in engines else ())
    assets = {}
    for name in names:
        request = urllib.request.Request(urllib.parse.urljoin(base, name), headers={'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(request, timeout=30) as response:
            if urllib.parse.urlsplit(response.url).netloc != urllib.parse.urlsplit(base).netloc:
                raise ValueError('cross-origin asset redirect')
            raw = response.read()
        assets[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    return assets


def host_info():
    cpu = platform.processor()
    if sys.platform == 'darwin':
        try:
            cpu = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True, timeout=3).strip()
        except (OSError, subprocess.SubprocessError):
            pass
    elif not cpu and Path('/proc/cpuinfo').exists():
        cpu = next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), '')
    try:
        nice = os.getpriority(os.PRIO_PROCESS, 0)
    except (AttributeError, OSError):
        nice = None
    return {'os': platform.system(), 'os_release': platform.release(), 'machine': platform.machine(),
            'cpu_model': cpu, 'logical_cpus': os.cpu_count(), 'controller_nice': nice,
            'python': platform.python_version(), 'environment': 'actual desktop host; not a smartphone',
            'worker_cpu_throttle': 'none', 'main_thread_throttle': 'none'}


TRIAL_JS = r"""args => new Promise(resolve => {
  const started = performance.now(), events = [];
  let worker, timer, settled = false;
  function finish(result) {
    if (settled) return;
    settled = true; clearTimeout(timer); worker?.terminate();
    window.__retroBenchCurrent = null;
    resolve({result, events, client_wall_seconds: (performance.now() - started) / 1000});
  }
  window.__retroBenchCurrent = {cancel() {
    const result = {status:'interrupted', reason:'controller interrupted observation'};
    const trace = {result, events:events.slice(), client_wall_seconds:(performance.now()-started)/1000};
    finish(result); return trace;
  }};
  timer = setTimeout(() => finish({status:'unknown', observational_deadline:true,
    reason:'Worker terminated by observational watchdog; no reachability verdict'}), args.deadline * 1000);
  try {
    worker = new Worker(args.workerURL);
    worker.onmessage = event => {
      const value = event.data;
      if (value?.type === 'progress') events.push({...value, client_elapsed_seconds:(performance.now()-started)/1000});
      else if (value?.type === 'result') finish(value);
    };
    worker.onerror = event => {event.preventDefault();finish({status:'error',reason:event.message || 'Worker error'});};
    worker.onmessageerror = () => finish({status:'error',reason:'Worker message could not be decoded'});
    // Only the target and selected program slot are sent; never a reference record.
    worker.postMessage({type:'solve',board:args.board,engine:args.engine});
  } catch(error) {finish({status:'error',reason:String(error)});}
})"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--url', required=True)
    parser.add_argument('--cases', required=True, type=Path, action='append', help='case JSON; repeat to concatenate fixed subsets in order')
    parser.add_argument('--output', required=True, type=Path, help='new or empty output directory')
    parser.add_argument('--engines', default='auto,sat', help='comma-separated auto,sat or one slot')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--deadline', type=float, default=60, help='observational seconds including startup; expiration means unknown')
    parser.add_argument('--chrome', default=os.environ.get('CHROME_PATH'), help='Chrome executable; defaults to local Chrome or Playwright Chromium')
    args = parser.parse_args(argv)
    engines = args.engines.split(',')
    if not engines or len(set(engines)) != len(engines) or any(e not in ('sat', 'auto') for e in engines):
        parser.error('--engines must contain unique auto/sat slots')
    if args.repeats < 1 or not 0 < args.deadline < 86400:
        parser.error('positive repeats and a finite observational deadline under one day are required')
    url = urllib.parse.urlsplit(args.url)
    if url.scheme not in ('http', 'https') or not url.netloc or url.username or url.password:
        parser.error('--url must be an HTTP(S) static app URL without credentials')
    cases, banks = read_cases(args.cases)
    output = args.output
    if output.exists() and any(output.iterdir()):
        parser.error('--output must be new or empty; existing observations are never overwritten')
    output.mkdir(parents=True, exist_ok=True)
    schedule = [{'trial_index': i, 'case': case['id'], 'repeat': repeat, 'engine': engine}
                for i, (repeat, case, engine) in enumerate((r, c, e) for r in range(1, args.repeats + 1) for c in cases for e in engines)]
    metadata = {'schema_version': 1, 'status': 'preparing', 'started_at': now(), 'url': args.url,
                'cases': banks, 'cases_sha256': digest([{'id': c['id'], 'board': c['board']} for c in cases]),
                'schedule': schedule, 'schedule_sha256': digest(schedule), 'selected_engines': engines,
                'repeats': args.repeats, 'planned_trials': len(schedule), 'completed_observations': 0,
                'observational_deadline_seconds': args.deadline, 'watchdog_is_not_unreachable': True,
                'host': host_info(), 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'timing_profile': {'worker': 'fresh per trial, including runtime/model loading',
                    'http_cache': 'disabled by Playwright routing', 'service_workers': 'blocked',
                    'local_result_cache': 'unused; direct Worker messages',
                    'clock': 'main-frame performance.now from Worker construction through result receipt',
                    'independent_verification': 'after proof receipt, outside primary timing',
                    'schedule_order': 'repeat, original case order, engine order',
                    'not_comparable_to': 'resident/warm native benchmark or smartphone hardware'}}
    write_json(output / 'metadata.json', metadata)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise SystemExit('Python Playwright is required; no installation was attempted') from error
    chrome = args.chrome
    if not chrome:
        mac = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        chrome = str(mac) if mac.is_file() else shutil.which('google-chrome')
    context = page = None
    requests, violations, page_errors = [], [], []
    request_offset = 0; active_trial = None; interrupted = False; fatal = False; errors = 0
    by_id = {case['id']: case for case in cases}
    old_signals = {}
    def interrupt(signum, frame):
        raise KeyboardInterrupt('signal ' + str(signum))
    for signum in (signal.SIGINT, signal.SIGTERM):
        old_signals[signum] = signal.signal(signum, interrupt)
    def flush_requests():
        nonlocal request_offset
        for row in requests[request_offset:]: append(output / 'requests.jsonl', row)
        request_offset = len(requests)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, **({'executable_path': chrome} if chrome else {}))
            try:
                context = browser.new_context(viewport={'width': 1280, 'height': 900}, is_mobile=False, service_workers='block')
                origin = (url.scheme, url.netloc)
                def guard(route):
                    request = route.request; target = urllib.parse.urlsplit(request.url)
                    row = {'trial_index': active_trial, 'url': request.url, 'method': request.method,
                           'resource_type': request.resource_type, 'at': now()}
                    requests.append(row)
                    if request.method != 'GET' or (target.scheme, target.netloc) != origin or re.search(r'(?:^|/)api(?:/|$)', target.path, re.I):
                        violations.append(row); route.abort('blockedbyclient')
                    else: route.continue_()
                context.route('**/*', guard)
                page = context.new_page(); page.on('pageerror', lambda error: page_errors.append(str(error)))
                page.goto(args.url, wait_until='networkidle', timeout=30000)
                page.wait_for_function("typeof RetroRules==='object' && typeof RetroRules.verify==='function'", timeout=15000)
                worker_url = page.evaluate("new URL('solver-worker.js',location.href).href")
                base = urllib.parse.urljoin(worker_url, './')
                metadata.update(browser={'product': 'Chrome/Chromium desktop', 'version': browser.version,
                    'executable_basename': Path(chrome).name if chrome else 'Playwright Chromium',
                    'navigator': page.evaluate('({user_agent:navigator.userAgent,hardware_concurrency:navigator.hardwareConcurrency,platform:navigator.platform})')},
                    worker_url=worker_url, asset_base=base, assets=fetch_assets(base, engines))
                if violations or page_errors: raise RuntimeError('static app initialization reported network/page errors')
                # Reference checks are not passed to the Worker or included in trial time.
                for case in cases:
                    if case.get('reference_moves') is not None:
                        page.evaluate('(c)=>RetroRules.verify(c.reference_moves,c.board)', case)
                metadata['status'] = 'running'; write_json(output / 'metadata.json', metadata); flush_requests()
                for item in schedule:
                    active_trial = item['trial_index']; case = by_id[item['case']]
                    row = {**item, 'method': item['engine'], 'board': case['board'], 'expected': case.get('expected'),
                           'stratum': case.get('stratum') or case.get('selection_stratum') or ('n' + str(case.get('stones', sum(c != '-' for c in case['board'])))),
                           'started_at': now(), 'verified': False}
                    began = time.monotonic()
                    try:
                        observation = page.evaluate(TRIAL_JS, {'workerURL': worker_url, 'board': case['board'], 'engine': item['engine'], 'deadline': args.deadline})
                    except KeyboardInterrupt:
                        interrupted = True
                        try: observation = page.evaluate('window.__retroBenchCurrent?.cancel()')
                        except Exception: observation = None
                        observation = observation or {'result': {'status': 'interrupted'}, 'events': [], 'client_wall_seconds': time.monotonic() - began}
                    row.update(finished_at=now(), controller_wall_seconds=time.monotonic() - began,
                               wall_seconds=observation['client_wall_seconds'], progress=observation['events'],
                               worker_result=observation['result'])
                    result = observation['result']; row['status'] = result.get('status', 'error')
                    row['worker_wall_seconds'] = result.get('wall_seconds'); row['stats'] = result.get('stats', {})
                    row['observational_deadline'] = bool(result.get('observational_deadline'))
                    if row['status'] == 'found':
                        try:
                            checked = page.evaluate('(r)=>{const t=performance.now();const checked=RetroRules.verify(r.moves,r.board);return{checked,seconds:(performance.now()-t)/1000}}', {'moves': result.get('moves'), 'board': case['board']})
                            row.update(verified=True, moves=checked['checked']['moves'], terminal=checked['checked']['terminal'],
                                       placements=checked['checked']['placements'], passes=checked['checked']['passes'],
                                       independent_verification_seconds=checked['seconds'])
                            if case.get('expected') == 'unreachable': raise ValueError('legal witness contradicts expected unreachability')
                        except Exception as error:
                            row.update(status='error', verification_error=str(error)); fatal = True
                    elif row['status'] == 'unreachable' and case.get('expected') == 'reachable':
                        row.update(status='error', verification_error='unreachable answer on a known-reachable target'); fatal = True
                    elif row['status'] not in ('unreachable', 'unknown', 'error', 'interrupted'):
                        row.update(status='error', verification_error='unrecognized worker status'); fatal = True
                    if violations or page_errors:
                        row.update(status='error', verification_error='network policy violation or page exception'); fatal = True
                    append(output / 'runs.jsonl', row); flush_requests()
                    errors += row['status'] == 'error'
                    metadata['completed_observations'] += row['status'] != 'interrupted'
                    write_json(output / 'progress.json', {'updated_at': now(), 'last_trial_index': item['trial_index'],
                        'case': case['id'], 'engine': item['engine'], 'status': row['status'],
                        'completed_observations': metadata['completed_observations'], 'planned_trials': len(schedule)})
                    print(json.dumps({'trial_index': item['trial_index'], 'case': case['id'], 'engine': item['engine'],
                                      'status': row['status'], 'seconds': row['wall_seconds'], 'verified': row['verified']}, separators=(',', ':')), flush=True)
                    if fatal or interrupted: break
                active_trial = None
                metadata['assets_after'] = fetch_assets(base, engines)
                metadata['assets_unchanged'] = metadata['assets_after'] == metadata['assets']
                if not metadata['assets_unchanged']: fatal = True
            finally:
                browser.close()
    except KeyboardInterrupt:
        interrupted = True
    except Exception as error:
        fatal = True; metadata['error'] = str(error)
    finally:
        for signum, handler in old_signals.items(): signal.signal(signum, handler)
        flush_requests()
        metadata.update(status='interrupted' if interrupted else 'error' if fatal or errors else 'complete',
                        finished_at=now(), error_observations=errors, network_violations=violations, page_errors=page_errors,
                        unknown_is_not_unreachable=True)
        write_json(output / 'metadata.json', metadata)
    return 130 if interrupted else 1 if fatal or errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
