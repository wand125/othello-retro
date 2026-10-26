#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build only this measured experimental encoder snapshot; no models needed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-measured-hash', action='store_true')
    args = parser.parse_args()
    source = ROOT/'encoder-source'
    env = {**os.environ, 'RUSTFLAGS': '', 'CARGO_ENCODED_RUSTFLAGS': '',
           'CARGO_TARGET_DIR': str(source/'target')}
    command = ['cargo', '+1.98.0', 'build', '--manifest-path', str(source/'Cargo.toml'),
               '--target', 'wasm32-unknown-unknown', '--release', '--locked', '--offline', '-j2']
    subprocess.run(command, env=env, check=True)
    output = ROOT/'artifacts'
    output.mkdir(exist_ok=True)
    binary = output/'encoder.wasm'
    shutil.copy2(source/'target/wasm32-unknown-unknown/release/othello_retro_browser_encoder.wasm', binary)
    actual = hashlib.sha256(binary.read_bytes()).hexdigest()
    expected = json.loads((ROOT/'measurement-inputs.json').read_text())['artifact_sha256']['encoder.wasm']
    report = {'actual_sha256': actual, 'measured_sha256': expected, 'bitwise_match': actual == expected,
              'toolchain': subprocess.check_output(['rustc', '+1.98.0', '--version'], text=True).strip(),
              'target': 'wasm32-unknown-unknown', 'rustflags': [], 'models_required': False}
    (output/'build.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    if args.require_measured_hash and actual != expected:
        raise SystemExit('Rebuilt encoder differs; do not silently call it the measured artifact.')

if __name__ == '__main__':
    main()
