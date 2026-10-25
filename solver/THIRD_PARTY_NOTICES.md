# Third-party notices

This nonvendored source distribution lists external dependencies and includes their exact upstream notices. All selectable dependencies use the MIT option for this distribution. No solver binary, Cargo registry source, C/C++ source, compiled library or Python package is bundled.

| Component | Version | Declared / selected | Notice |
|---|---|---|---|
| cadical | 0.1.16 | MIT / MIT | [licenses/cadical-0.1.16/LICENSE](licenses/cadical-0.1.16/LICENSE) |
| CaDiCaL | 1.9.5 | MIT / MIT | [licenses/cadical-1.9.5/LICENSE](licenses/cadical-1.9.5/LICENSE) |
| cc | 1.6.0 | MIT OR Apache-2.0 / MIT | [licenses/cc-1.6.0/LICENSE-MIT](licenses/cc-1.6.0/LICENSE-MIT) |
| cfg-if | 1.0.5 | MIT OR Apache-2.0 / MIT | [licenses/cfg-if-1.0.5/LICENSE-MIT](licenses/cfg-if-1.0.5/LICENSE-MIT) |
| find-msvc-tools | 0.1.14 | MIT OR Apache-2.0 / MIT | [licenses/find-msvc-tools-0.1.14/LICENSE-MIT](licenses/find-msvc-tools-0.1.14/LICENSE-MIT) |
| getrandom | 0.4.3 | MIT OR Apache-2.0 / MIT | [licenses/getrandom-0.4.3/LICENSE-MIT](licenses/getrandom-0.4.3/LICENSE-MIT) |
| jobserver | 0.1.35 | MIT OR Apache-2.0 / MIT | [licenses/jobserver-0.1.35/LICENSE-MIT](licenses/jobserver-0.1.35/LICENSE-MIT) |
| libc | 0.2.190 | MIT OR Apache-2.0 / MIT | [licenses/libc-0.2.190/LICENSE-MIT](licenses/libc-0.2.190/LICENSE-MIT) |
| r-efi | 6.0.0 | MIT OR Apache-2.0 OR LGPL-2.1-or-later / MIT | [licenses/r-efi-6.0.0/AUTHORS](licenses/r-efi-6.0.0/AUTHORS) |
| shlex | 2.0.1 | MIT OR Apache-2.0 / MIT | [licenses/shlex-2.0.1/LICENSE-MIT](licenses/shlex-2.0.1/LICENSE-MIT) |
| Kissat | 4.0.3 | MIT / MIT | [licenses/kissat-4.0.3/LICENSE](licenses/kissat-4.0.3/LICENSE) |

`cadical` is the Rust binding by Miklos Maroti. Its published crate license is
copied verbatim; its bundled CaDiCaL1.9.5 has a separate notice retaining all
listed upstream authors. Cargo downloads the locked crate and compiles its
C++17 implementation during the build, including for this SAT CLI package.
The binding is linked because the preserved Rust source also contains repair
and incremental-solving functionality. Those commands are outside the primary
SAT CLI usage documented here; their presence has not been hidden by deleting
source files.

The remaining locked crates are `cc`, `cfg-if`, `find-msvc-tools`, `getrandom`,
`jobserver`, `libc`, `r-efi`, and `shlex`. Dual/triple license expressions are
alternatives; this distribution selects MIT and preserves the corresponding notice.
`r-efi6.0.0` stores its complete MIT permission and copyright notices in AUTHORS,
not a standalone LICENSE file. The included AUTHORS comes from the exact
crates.io archive whose SHA-256 equals Cargo.lock. It is selected by getrandom
only under `cfg(all(target_os = "uefi", getrandom_backend = "efi_rng"))`.
The documented macOS/Linux builds do not select that conditional dependency;
its notice is nevertheless included for the complete lockfile inventory.

Kissat4.0.3 is a separate runtime process, obtained and installed by the user.
Its notice is included for clarity. If a later release distributes compiled
binaries, a container, Cargo-vendored source, a solver archive, or a WASM build,
its actual bundled contents and additional native/toolchain runtime notices
must be reviewed separately. This source-only checklist is not that audit.

Version/source/notice hashes are in `DEPENDENCIES.json`. Public upstream sources:
- https://github.com/mmaroti/cadical-rs/
- https://github.com/arminbiere/cadical/tree/rel-1.9.5
- https://github.com/arminbiere/kissat/tree/rel-4.0.3
- https://github.com/r-efi/r-efi/blob/v6.0.0/AUTHORS


Python source is also original MIT code. Python packages are external dependencies, not vendored implementations. See PYTHON_DEPENDENCIES.md, requirements-inference.txt and requirements-training.txt for license/version evidence and exact upstream notices.
