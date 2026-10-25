# Third-party Web dependency

The local video editor uses **Mediabunny 1.62.1**, by Vanilagy and contributors, under **MPL-2.0**. The Short and simplified public interfaces do not require this video-export library. No Mediabunny bundle or third-party source tree is bundled in this source stage.

- Upstream: <https://github.com/Vanilagy/mediabunny>
- Published package/source archive: <https://registry.npmjs.org/mediabunny/-/mediabunny-1.62.1.tgz>
- Archive SHA-256: `bf97e177e9a86a115f04cd92af4255617e8b73e33628d98594c372235ab61e53`
- npm integrity: `sha512-lYzeerDwo9QLhBCipqQDXOSV7InvaIFplllZQviPO5rPwH+IUr8M1uvumk1olIUgMRGkPiInRriv25WFErUgMw==`
- License text: `licenses/MPL-2.0-mediabunny.txt`; official text: <https://www.mozilla.org/en-US/MPL/2.0/>

Run the commands below from the release repository root. This document, the acquisition helper and license notices are installed under `solver/`.

The archive contains the preferred TypeScript source (`src/`, 67 files), package metadata, and the browser ESM bundle. To obtain these without executing a package installer:

```sh
python3 solver/tools/fetch_mediabunny.py --destination vendor/mediabunny-1.62.1
```

The helper verifies both the published SHA-512 integrity and SHA-256, verifies package identity/license, extracts only named regular files, and refuses an existing destination. It leaves the upstream license intact and writes a file-hash manifest.

`solver/ui/video.html` expects a browser global named `Mediabunny`. With Node.js/npm available, convert the pinned upstream ESM bundle using the separately licensed MIT esbuild 0.25.11:

```sh
npx --yes --package=esbuild@0.25.11 -- esbuild \
  vendor/mediabunny-1.62.1/dist/bundles/mediabunny.mjs \
  --format=iife --global-name=Mediabunny --legal-comments=inline \
  --outfile=solver/ui/mediabunny.js
```

The historical local bundle was 1,608,208 bytes with SHA-256 `ef4c10b8850e825aabcc4e05bcad21d572f676d2dae744517f099d2696283886`. That bundle is omitted; this recipe does not promise an identical byte sequence from a different bundler invocation. Keep the upstream notices and make its corresponding source and MPL available when redistributing a generated bundle. MPL applies to its covered files; the application's own separate files remain under their stated licenses.

Cloud runtime Python dependencies are installed separately and are not vendored here: Google Cloud Firestore/Tasks clients (Apache-2.0), NumPy/scikit-learn (BSD-3-Clause), and PyTorch (BSD-style). Their license notices remain with their packages. `solver/cloud/requirements.txt` describes the application runtime; the benchmark's separately pinned CPU222 environment is a different profile.
