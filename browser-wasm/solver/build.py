#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the vendored Kissat library C API, without application/CLI code."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'vendor/kissat-4.0.3'
OUTPUT = HERE.parent / 'ui'
BUILD = HERE / 'build'
EMCC = os.environ.get('EMCC') or shutil.which('emcc')
CACHE = Path(os.environ.get('EM_CACHE', '/private/tmp/othello-browser-wasm-emcache'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if not EMCC:
        raise SystemExit('emcc was not found; set EMCC or add Emscripten to PATH')
    node = os.environ.get('EM_NODE_JS') or shutil.which('node')
    if not node:
        raise SystemExit('node was not found; set EM_NODE_JS or add Node.js to PATH')
    assert (SOURCE/'VERSION').read_text().strip() == '4.0.3'
    BUILD.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    # Keep build strings deterministic and free of hostnames/absolute paths.
    (BUILD/'build.h').write_text('#define VERSION "4.0.3"\n#define ID "rel-4.0.3"\n#define COMPILER "Emscripten"\n#define BUILD "single-thread WebAssembly library"\n#define DIR "."\n')
    excluded = {'main.c', 'application.c', 'handle.c', 'parse.c', 'witness.c'}
    sources = sorted(p for p in (SOURCE/'src').glob('*.c') if p.name not in excluded)
    exports = ['kissat_init', 'kissat_add', 'kissat_add_buffer', 'kissat_solve', 'kissat_value',
               'kissat_release', 'kissat_set_option', 'kissat_get_option', 'kissat_terminate',
               'kissat_reserve', 'kissat_set_conflict_limit', 'kissat_set_decision_limit', 'kissat_signature', 'kissat_version', 'malloc', 'free']
    path_maps = [(SOURCE, 'kissat-4.0.3'), (HERE, 'browser-wasm/solver')]
    flags = ['-O3', '-DNDEBUG', '-DQUIET',
             *['-ffile-prefix-map='+str(source)+'='+replacement for source, replacement in path_maps],
             '-I'+str(SOURCE/'src'), '-I'+str(BUILD),
             '--no-entry', '-sMODULARIZE=1', '-sEXPORT_NAME=createKissat',
             '-sENVIRONMENT=worker,node', '-sALLOW_MEMORY_GROWTH=1',
             '-sINITIAL_MEMORY=33554432', '-sMAXIMUM_MEMORY=1073741824',
             '-sSTACK_SIZE=1048576', '-sFILESYSTEM=0', '-sEXIT_RUNTIME=0',
             '-sEXPORTED_FUNCTIONS='+json.dumps(['_'+n for n in exports]),
             '-sEXPORTED_RUNTIME_METHODS='+json.dumps(['UTF8ToString', 'HEAP32'])]
    env = {**os.environ, 'EM_CACHE': str(CACHE), 'EMCC_CORES': '2',
           'EM_NODE_JS': node}
    compiler = subprocess.check_output([EMCC, '--version'], text=True).splitlines()[0]
    started = time.monotonic()
    subprocess.run([EMCC, *map(str,sources), str(HERE/'kissat_bulk.c'), *flags,
                    '-o', str(OUTPUT/'kissat.js')], env=env, check=True)
    tracked = sorted(p for p in SOURCE.rglob('*') if p.is_file())
    source_hashes = {str(p.relative_to(SOURCE)): sha(p) for p in tracked}
    source_digest = hashlib.sha256(json.dumps(source_hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    manifest = {'kissat_version':'4.0.3', 'upstream':'https://github.com/arminbiere/kissat/tree/rel-4.0.3',
                'source_origin':'Existing local official release source copy; no source download performed in this build',
                'source_files_sha256':source_hashes, 'source_tree_sha256':source_digest,
                'compiler':compiler, 'single_thread':True, 'factory':'createKissat',
                'environments':['worker','node'],
                'flags':[f.replace(str(SOURCE), '<KISSAT_SOURCE>').replace(str(HERE), '<SOLVER_SOURCE>')
                         for f in flags if not f.startswith('-I')],
                'source_path_normalization':{'compiler_option':'-ffile-prefix-map',
                    'maps':[{'from':'<KISSAT_SOURCE>','to':'kissat-4.0.3'},
                            {'from':'<SOLVER_SOURCE>','to':'browser-wasm/solver'}],
                    'scope':'Compile-path normalization only; C source and algorithms unchanged'},
                'exports':exports, 'build_seconds':time.monotonic()-started,
                'adapter_sha256':sha(HERE/'kissat_bulk.c'), 'build_script_sha256':sha(Path(__file__)),
                'source_origin_sha256':sha(HERE/'source-origin.json'),
                'portability_patch_sha256':sha(HERE/'wasm32-portability.patch'),
                'license_file':'KISSAT-LICENSE', 'license_sha256':sha(HERE/'KISSAT-LICENSE'),
                'runtime_notice_sha256':sha(OUTPUT/'kissat.LICENSES.txt'),
                'artifacts':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in [OUTPUT/'kissat.js',OUTPUT/'kissat.wasm']}}
    (HERE/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'status':'built','artifacts':manifest['artifacts'],'seconds':manifest['build_seconds']}))

if __name__ == '__main__':
    main()
