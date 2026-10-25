#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 wand125 and contributors.
"""Assemble a serverless SAT application in a new directory; never deploy it."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ID = re.compile(r'[A-Za-z0-9_-]{1,100}\Z')
PAPER_NAMES = ('paper.html', 'paper.css', 'paper.js', 'paper-data.json')
FIELDS = ('id', 'title', 'board', 'moves', 'terminal', 'source', 'elapsed_seconds',
          'wall_seconds', 'requested_seconds', 'method', 'environment', 'created_at',
          'started_at', 'finished_at', 'timing_note')


def sha(data): return hashlib.sha256(data).hexdigest()
def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode()


def read_regular(path):
    if path.is_symlink() or not path.is_file(): raise ValueError('missing or nonregular asset: '+path.name)
    return path.read_bytes()


def redirect(target):
    """Static fallback plus JS redirect preserving incoming query/hash.

    Fixed target selectors come first so a legacy query cannot override record
    identity. Duplicate incoming parameters are otherwise retained.
    """
    literal = json.dumps(target).replace('<', '\\u003c')
    escaped = html.escape(target, quote=True)
    return (f'<!doctype html><html lang="en"><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="refresh" content="0;url={escaped}">'
            f'<title>Othello Retro</title><script>const destination=new URL({literal},location.href);'
            'for(const [key,value] of new URLSearchParams(location.search))destination.searchParams.append(key,value);'
            'destination.hash=location.hash;location.replace(destination.href);</script>'
            f'<a href="{escaped}">Continue to Othello Retro</a></html>\n').encode()


def static_paper(source):
    """Change URL references only; preserve prose, math, styling and i18n."""
    rendered = dict(source)
    text = source['paper.html'].decode()
    # Literal and HTML-escaped attribute values share the same URL text.
    for original, replacement in [
        ('https://othello-retro.logicpuzzle.app/examples/', '../examples/'),
        ('https://othello-retro.logicpuzzle.app/', '../'),
        ('/paper-data.json', 'paper-data.json'), ('/paper.css', 'paper.css'), ('/paper.js', 'paper.js')]:
        text = text.replace(original, replacement)
    text = re.sub(r'((?:href|src)=([\"\x27]))/examples(?:/)?(?=[\"\x27])', r'\1../examples/', text)
    text = text.replace('href=&quot;/examples&quot;', 'href=&quot;../examples/&quot;')
    text = re.sub(r'(href=([\"\x27]))/(?=[\"\x27])', r'\1../', text)
    text = text.replace('href=&quot;/&quot;', 'href=&quot;../&quot;')
    rendered['paper.html'] = text.encode()
    script = source['paper.js'].decode()
    fetch_original = "fetch('/paper-data.json')"
    link_original = "'https://othello-retro.logicpuzzle.app/examples/'+example.id"
    if script.count(fetch_original) != 1 or script.count(link_original) != 1:
        raise ValueError('paper URL hooks changed; review asset-only transformation')
    # Capture the executing script URL before the asynchronous callbacks run.
    script = script.replace("(() => {", "(() => {\n  const staticAssetBase = new URL('.', document.currentScript.src);", 1)
    script = script.replace(fetch_original, "fetch(new URL('paper-data.json', staticAssetBase))")
    script = script.replace(link_original, "new URL('../examples/'+encodeURIComponent(example.id)+'/', staticAssetBase).href")
    rendered['paper.js'] = script.encode()
    return rendered


def verified_records(data, verify_path):
    rows = data.get('examples') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows: raise ValueError('records must contain a nonempty examples array')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not ID.fullmatch(row['id']):
            raise ValueError('invalid public record ID')
        if row['id'] in seen: raise ValueError('duplicate public record ID')
        seen.add(row['id'])
    program = """const fs=require('node:fs');const rules=require(process.argv[1]);
const rows=JSON.parse(fs.readFileSync(0,'utf8'));const out=[];
for(let i=0;i<rows.length;i++){try{out.push(rules.verify(rows[i].moves,rows[i].board));}
catch(error){process.stderr.write(JSON.stringify({index:i,reason:error.message}));process.exit(2);}}
process.stdout.write(JSON.stringify(out));"""
    result = subprocess.run(['node', '-e', program, str(verify_path)], input=json.dumps(rows),
                            text=True, capture_output=True, check=False)
    if result.returncode: raise ValueError('independent record replay failed: '+result.stderr[:300])
    proofs = json.loads(result.stdout)
    clean = []
    for row, proof in zip(rows, proofs):
        if 'terminal' in row and row['terminal'] is not proof['terminal']:
            raise ValueError('record terminal flag differs from independent replay: '+row['id'])
        item = {key: row[key] for key in FIELDS if key in row}
        # Public record metadata is scalar; never copy arbitrary nested objects.
        for key, value in item.items():
            if key not in ('board','moves') and value is not None and not isinstance(value, (str,int,float,bool)):
                raise ValueError('unexpected nested public metadata: '+key)
        item.update(moves=proof['moves'], terminal=proof['terminal'])
        item['verification'] = {'legal':True,'target_matches':True,
            'record_sha256':sha((item['board']+'|'+''.join(item['moves'])).encode())}
        clean.append(item)
    if len(proofs) != len(rows): raise ValueError('record replay count mismatch')
    return {'version':1, 'examples':clean}


def build(public_repo, output, records_path=None):
    public_repo, output = Path(public_repo).resolve(), Path(output)
    if output.exists() or output.is_symlink(): raise ValueError('output must be a new directory')
    ui = HERE/'ui'
    resolved_output = output.resolve()
    if resolved_output.is_relative_to(public_repo) or resolved_output.is_relative_to(ui.resolve()):
        raise ValueError('output must be outside the read-only public repository and UI source tree')
    assets, watched = {}, {}
    for path in sorted(ui.rglob('*')):
        if path.is_symlink(): raise ValueError('UI assets must not contain symlinks')
        if not path.is_file() or any(part.startswith('.') for part in path.relative_to(ui).parts): continue
        content = read_regular(path); assets[path.relative_to(ui).as_posix()] = content; watched[path] = content
    required = ('index.html','short.css','short.js','verify.js','engine.js','solver-worker.js',
                'encoder.wasm','kissat.js','kissat.wasm','kissat.LICENSES.txt','register-sw.js','sw.js')
    for name in required:
        if name not in assets: raise ValueError('required UI asset not ready: '+name)
    template = assets.pop('sw.js').decode()
    if template.count('__ASSET_VERSION__') != 1: raise ValueError('SW must contain exactly one version token')
    for forbidden in ('asset-manifest.json','paper.html','paper','examples'):
        if forbidden in assets or any(name.startswith(forbidden+'/') for name in assets):
            raise ValueError('UI conflicts with generated route: '+forbidden)
    paper = {}
    for name in PAPER_NAMES:
        path=public_repo/'solver'/'ui'/name
        paper[name]=read_regular(path);watched[path]=paper[name]
    for name, content in static_paper(paper).items():
        assets['paper/'+('index.html' if name=='paper.html' else name)] = content
    assets['paper.html'] = redirect('paper/')
    assets['examples/index.html'] = redirect('../?library=1')
    records_path = Path(records_path) if records_path else ui/'public-examples.json'
    raw = read_regular(records_path);watched[records_path] = raw
    records = verified_records(json.loads(raw), ui/'verify.js')
    assets['public-examples.json'] = json_bytes(records)
    for record in records['examples']:
        ident = record['id']
        assets['examples/'+ident+'/index.html'] = redirect('../../?record='+ident)
    # Version has no self-reference: both manifest and generated SW are excluded.
    core_hashes = {name:sha(content) for name,content in sorted(assets.items())}
    version = sha(json.dumps(core_hashes,sort_keys=True,separators=(',',':')).encode())
    assets['sw.js'] = template.replace('__ASSET_VERSION__',version).encode()
    manifest = {'version':version,'files':sorted(core_hashes),
        'files_sha256':{name:sha(content) for name,content in sorted(assets.items())},
        'version_digest_rule':'SHA256 of UTF-8 compact sorted-key JSON mapping relative asset paths to SHA256; manifest and sw.js excluded.',
        'self_hash_note':'asset-manifest.json excludes its own hash; files_sha256 covers all other output files including generated sw.js.',
        'records':{'count':len(records['examples']),'snapshot_sha256':sha(raw),'independently_replayed':True},
        'paper_source_sha256':{name:sha(content) for name,content in paper.items()},
        'paper_changes':'Asset/link URLs only. Prose, CSS, mathematical content, i18n and figure data preserved.'}
    assets['asset-manifest.json'] = json_bytes(manifest)
    # Reject a mixed snapshot if another workflow edits input while assembling.
    if any(read_regular(path) != content for path,content in watched.items()):
        raise ValueError('an input asset changed during assembly; retry with stable inputs')
    output.mkdir(parents=True,exist_ok=False)
    for name, content in sorted(assets.items()):
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-repo',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--records',type=Path,help='Public API snapshot with {examples:[...]}; otherwise bundled7 records')
    args=parser.parse_args()
    try:
        manifest=build(args.public_repo,args.output,args.records)
    except (ValueError,OSError,json.JSONDecodeError) as exc:
        parser.exit(1,'build failed: '+str(exc)+'\n')
    print(json.dumps({'status':'built','version':manifest['version'],'records':manifest['records']['count'],
                      'precache_assets':len(manifest['files']),'deployed':False}))

if __name__=='__main__':main()
