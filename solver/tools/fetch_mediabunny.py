#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fetch pinned Mediabunny sources and browser ESM input, not a solver/model.

The downloaded library remains MPL-2.0, not MIT. No package code is executed.
"""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request

VERSION = '1.62.1'
URL = 'https://registry.npmjs.org/mediabunny/-/mediabunny-1.62.1.tgz'
INTEGRITY = 'lYzeerDwo9QLhBCipqQDXOSV7InvaIFplllZQviPO5rPwH+IUr8M1uvumk1olIUgMRGkPiInRriv25WFErUgMw=='
ARCHIVE_SHA256 = 'bf97e177e9a86a115f04cd92af4255617e8b73e33628d98594c372235ab61e53'


def acquire(destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('destination already exists; choose a new directory')
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read(20_000_001)
    if len(data) > 20_000_000:
        raise ValueError('archive exceeds pinned package size limit')
    if base64.b64encode(hashlib.sha512(data).digest()).decode() != INTEGRITY or hashlib.sha256(data).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('upstream archive hash mismatch')
    archive = tarfile.open(fileobj=io.BytesIO(data), mode='r:gz')
    selected = []
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'package':
            raise ValueError('unexpected package path')
        relative = PurePosixPath(*path.parts[1:])
        if (str(relative).startswith('src/') or str(relative) in {'LICENSE', 'README.md', 'package.json', 'dist/bundles/mediabunny.mjs'}):
            if not member.isfile():
                if member.isdir():
                    continue
                raise ValueError('links are not extracted')
            selected.append((member, relative))
    metadata = json.load(archive.extractfile('package/package.json'))
    if metadata['name'] != 'mediabunny' or metadata['version'] != VERSION or metadata['license'] != 'MPL-2.0':
        raise ValueError('unexpected upstream identity/license')
    destination.mkdir(parents=True)
    hashes = {}
    for member, relative in selected:
        target = destination / str(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        content = archive.extractfile(member).read()
        target.write_bytes(content)
        hashes[str(relative)] = hashlib.sha256(content).hexdigest()
    manifest = {'name': 'mediabunny', 'version': VERSION, 'license': 'MPL-2.0',
                'url': URL, 'archive_sha256': ARCHIVE_SHA256, 'integrity': 'sha512-' + INTEGRITY,
                'upstream_source_files': sum(name.startswith('src/') for name in hashes), 'files_sha256': hashes}
    (destination / 'acquisition.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    result = acquire(args.destination)
    print(json.dumps({key: result[key] for key in ['name', 'version', 'license', 'archive_sha256', 'upstream_source_files']}))


if __name__ == '__main__':
    main()
