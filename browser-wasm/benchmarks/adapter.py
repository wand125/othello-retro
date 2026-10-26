#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Resident JSONL adapter: cold per-trial browser Worker, no wall deadline.

Only static files from --ui-dir are served on an ephemeral loopback port. Chrome
and its empty harness start before ready; WASM/ONNX initialization is in trial.
Requires Python Playwright and an installed Chrome/Chromium. No installation,
reference lookup, Service Worker, persistent profile, or external service.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import signal
import sys
import threading
import urllib.parse

ASSETS = ('solver-worker.js', 'verify.js', 'engine.js', 'encoder.wasm',
          'kissat.js', 'kissat.wasm', 'auto.js', 'inference/infer.js',
          'inference/ort.wasm.min.js', 'inference/ort-wasm-simd-threaded.mjs',
          'inference/ort-wasm-simd-threaded.wasm', 'models/model.fused.onnx',
          'models/model_passes.fused.onnx')
HARNESS = '/__retro_benchmark__.html'
TIMING = 'fresh-worker-cold-wasm-models-browser-ready-v1'

# No setTimeout, deadline, cached witness, or main app code. Proof checking in
# this harness is separate from the Worker's own check and the runner's Python
# replay. Its receipt clock is diagnostic; runner wall includes this JS check.
TRIAL_JS = r"""args => new Promise(resolve => {
  const started = performance.now();
  let worker, settled = false, progressCount = 0;
  const events = [];
  function finish(result) {
    if (settled) return;
    settled = true;
    const receipt = (performance.now() - started) / 1000;
    worker?.terminate(); window.__retroAdapterCurrent = null;
    let checked = null;
    if (result?.status === 'found') {
      try { checked = RetroRules.verify(result.moves, args.board); }
      catch (_) { result = {status:'error', reason:'independent_js_replay_failed'}; }
    }
    if (!['found','unreachable','error'].includes(result?.status))
      result = {status:'error', reason:'unexpected_worker_status', original_status:result?.status};
    const stats = {...(result.stats || {}), worker_wall_seconds:result.wall_seconds ?? null,
      proof_receipt_seconds:receipt, independent_js_verified:!!checked,
      progress_events:progressCount, progress:events, trial_time_limit_seconds:null,
      final_sat_time_limit_seconds:null};
    resolve({...result, ...(checked ? {moves:checked.moves} : {}), stats});
  }
  window.__retroAdapterCurrent = {cancel() {worker?.terminate();}};
  try {
    worker = new Worker(args.workerURL);
    worker.onmessage = event => {
      const value = event.data;
      if (value?.type === 'progress') {
        progressCount++;
        if (events.length < 128) events.push({...value, elapsed_seconds:(performance.now()-started)/1000});
      } else if (value?.type === 'result') finish(value);
    };
    worker.onerror = event => {event.preventDefault();finish({status:'error',reason:'worker_error'});};
    worker.onmessageerror = () => finish({status:'error',reason:'worker_message_error'});
    worker.postMessage({type:'solve',board:args.board,engine:args.engine});
  } catch (_) { finish({status:'error',reason:'worker_start_failed'}); }
})"""


def validate_request(value):
    if not isinstance(value, dict):
        raise ValueError('request_must_be_object')
    board = value.get('board')
    if not isinstance(board, str) or not re.fullmatch('[XO-]{64}', board):
        raise ValueError('board_must_be_64_X_O_dash_cells')
    if not isinstance(value.get('id'), (str, int)) or isinstance(value.get('id'), bool) or value['id'] == '':
        raise ValueError('request_id_required')
    return {'id': value['id'], 'board': board}


def asset_hashes(directory):
    directory = directory.resolve()
    hashes = {}
    for name in ASSETS:
        path = directory / name
        if not path.is_file() or path.is_symlink() or directory not in path.resolve().parents:
            raise ValueError('missing_or_unsafe_static_asset:' + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == HARNESS:
            body = b'<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,"><title>Local benchmark harness</title><script src="verify.js"></script>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
        elif path.lstrip('/') in ASSETS and path == '/' + path.lstrip('/'):
            super().do_GET()
        else:
            self.send_error(404)

    def do_HEAD(self):
        self.send_error(405)


def emit(value):
    print(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', choices=['sat', 'auto'], required=True)
    parser.add_argument('--ui-dir', type=Path, required=True, help='immutable local UI snapshot, including both ONNX models')
    parser.add_argument('--chrome', help='optional Chrome executable; otherwise installed Chrome or Playwright Chromium')
    args = parser.parse_args(argv)
    directory = args.ui_dir.resolve()
    hashes = asset_hashes(directory)
    from playwright.sync_api import sync_playwright
    chrome = args.chrome
    if not chrome:
        mac = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        chrome = str(mac) if mac.is_file() else shutil.which('google-chrome')
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(directory)))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    origin = 'http://127.0.0.1:' + str(server.server_port)
    violations = []; browser = context = None
    previous = {}

    def interrupt(signum, _frame):
        raise KeyboardInterrupt('signal ' + str(signum))

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.signal(signum, interrupt)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--disable-gpu'],
                **({'executable_path': chrome} if chrome else {}))
            try:
                context = browser.new_context(service_workers='block', accept_downloads=False)
                context.set_default_timeout(0)

                def guard(route):
                    request = route.request
                    target = urllib.parse.urlsplit(request.url)
                    allowed = request.method == 'GET' and target.scheme + '://' + target.netloc == origin
                    allowed = allowed and target.path in ({HARNESS} | {'/' + name for name in ASSETS})
                    if allowed:
                        route.continue_()
                    else:
                        violations.append({'method': request.method, 'resource_type': request.resource_type})
                        route.abort('blockedbyclient')

                context.route('**/*', guard)  # Playwright routing disables HTTP cache.
                if hasattr(context, 'route_web_socket'):
                    def block_socket(socket):
                        violations.append({'method':'WEBSOCKET','resource_type':'websocket'})
                        socket.close()
                    context.route_web_socket('**/*', block_socket)
                page = context.new_page()
                page.goto(origin + HARNESS, wait_until='load', timeout=30000)
                page.wait_for_function("typeof RetroRules==='object'", timeout=15000)
                runtime = {'browser_version': browser.version, 'browser_product':'Chrome/Chromium',
                    'engine':args.engine, 'timing_profile':TIMING, 'worker_per_trial':'fresh',
                    'device':'cpu-wasm', 'dtype':'float32', 'inference_threads':1,
                    'service_workers':'blocked', 'http_cache':'disabled', 'external_network':'blocked',
                    'trial_time_limit_seconds':None, 'final_sat_time_limit_seconds':None,
                    'asset_sha256':hashes}
                if violations:
                    raise ValueError('network_guard_initialization_violation')
                emit({'event':'ready', 'stats':runtime})
                for line in sys.stdin:
                    if not line.strip():
                        continue
                    request = None
                    try:
                        if len(line) > 1024 * 1024:
                            raise ValueError('request_too_large')
                        request = validate_request(json.loads(line))
                    except (ValueError, TypeError) as error:
                        emit({'event':'result','payload':{'status':'error','reason':str(error) if type(error) is ValueError else 'invalid_json_request'}})
                        continue
                    before = len(violations)
                    result = page.evaluate(TRIAL_JS, {'board':request['board'], 'engine':args.engine,
                        'workerURL':origin + '/solver-worker.js'})
                    if len(violations) != before:
                        result = {'status':'error','reason':'network_guard_violation'}
                    result['id'] = request['id']
                    result['stats'] = {**result.get('stats', {}), **runtime}
                    emit({'event':'result','id':request['id'],'payload':result})
            finally:
                # Close the browser directly: it owns this nonpersistent
                # context and every Worker. No profile or page state is saved.
                if browser is not None:
                    browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
        for signum, handler in previous.items():
            signal.signal(signum, handler)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as error:
        # Keep private input paths out of stdout/portable benchmark reports.
        print('browser_adapter_failed:' + type(error).__name__, file=sys.stderr, flush=True)
        sys.exit(1)
