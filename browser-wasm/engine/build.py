#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the dependency-free Rust browser encoder from its audited snapshot."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    snapshot = json.loads((HERE / 'native/SOURCE.json').read_text())
    for file, expected in snapshot['sha256'].items():
        if sha(HERE / 'native' / file) != expected:
            raise RuntimeError('native snapshot differs from its source manifest: ' + file)
    subprocess.run(['rustup', 'run', '1.98.0', 'cargo', 'build', '--offline', '--locked',
                    '--release', '--target', 'wasm32-unknown-unknown', '--manifest-path', str(HERE / 'Cargo.toml'), '-j2'], check=True)
    wasm = HERE / 'target/wasm32-unknown-unknown/release/othello_retro_browser_encoder.wasm'
    destination = HERE.parent / 'ui/encoder.wasm'
    shutil.copy2(wasm, destination)
    files = [HERE / 'Cargo.toml', HERE / 'Cargo.lock', HERE / 'src/lib.rs', Path(__file__)]
    manifest = {'rust': '1.98.0', 'target': 'wasm32-unknown-unknown', 'dependencies': [],
                'native_source_manifest': 'native/SOURCE.json',
                'operations': 'Pure preprocessing, CNF generation, and legal predecessor generation with optional cheap ranking. Native process/thread/time routines are not called.',
                'source_sha256': {str(p.relative_to(HERE)): sha(p) for p in files},
                'encoder_wasm': {'bytes': destination.stat().st_size, 'sha256': sha(destination)}}
    (HERE / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest['encoder_wasm']))


if __name__ == '__main__':
    main()
