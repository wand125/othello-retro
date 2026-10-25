# Formal benchmark harness / 正式ベンチマークの測定コード

This directory contains the original unbounded measurement harness and two unchanged fixed banks. It is separate from the generic, standard-library-only `runner/` at the repository root. Run commands from `solver/` so the Rust, ML, UI and benchmark directories retain their original relative layout.

正式測定で使用した無制限harnessと固定bankです。汎用の外部プログラムを測る場合は、リポジトリ直下の `runner/` と日英手順を使ってください。ここでは同じソース・重み・CPU環境を照合します。

## Requirements and preparation

Build Rust with toolchain1.98.0 and the unchanged Cargo.lock, install Kissat4.0.3 and `requirements-inference.txt`, and place the Release weights in `ml/`. CPU FP32, Torch2.2.2/NumPy1.26.4 and2 inference threads are required. The two banks preserve their original hashes and resource requirements.

```sh
# From solver/, after building/installing the dependencies described in README.md:
export REAL_KISSAT="$(command -v kissat)"
mkdir -p .bench-bin
cp benchmarks/kissat_gate.py .bench-bin/kissat
chmod 755 .bench-bin/kissat
mkdir -m 700 .bench-locks
export KISSAT_GATE_DIR="$(pwd)/.bench-locks"
export KISSAT_GATE_SLOTS=2
export PATH="$(pwd)/.bench-bin:$PATH"
```

Set REAL_KISSAT before putting the wrapper on PATH. It must point to the actual solver, never recursively to the wrapper. The exec/flock gate permits at most2 real Kissat processes; its startup and queued waiting remain in the measured wall time. Python inference threads are a separate cap.

`REAL_KISSAT` はPATH変更前に実ソルバーを指定します。gateは専用ディレクトリを所有者だけが読める0700で使います。

## Pilot and main

```sh
# macOS: small pilot, then inspect its own records before considering main.
nice -n 19 python benchmarks/benchmark_unbounded.py run --bank benchmarks/study-midgame-cpu222-unbounded-v1.json --split pilot --output .bench-runs/pilot
# Linux: the frozen protocol specifically requires guest CPU affinity16–19.
taskset -c 16-19 nice -n 19 python benchmarks/benchmark_unbounded.py run --bank benchmarks/study-midgame-cpu222-unbounded-v1.json --split pilot --output .bench-runs/pilot-linux
```

Use `--split main` for400 midgame cases; the separate endgame bank has20 main cases and no pilot split. Each main suite runs SAT/auto three times per case. Trials and final SAT have no deadline; the internal2s and20s candidate probes remain part of the algorithm. Ctrl-C records the interrupted trial, cleans up only owned process groups, and `--resume` resumes with consumed work retained. A pause file pauses between trials.

The frozen Linux CPU list is deliberately checked, not automatically adapted to smaller or other machines. If the exact source, weights or resource protocol do not match, preflight stops. To measure a different execution configuration, retain fixed cases/schedule and record a new protocol or use the generic public runner; do not silently rewrite a published bank or relabel it as the original conditions.

固定Linux CPU集合やsource/model hashが一致しない場合は停止します。別の構成では別条件として記録してください。旧測定のM1/Intelのnice20という逸脱も結果資料に残しており、ここで19に修正したことにはしません。

Raw outputs contain local execution metadata. For redistribution use `export_unbounded.py` to sanitize, then independently check published data with the generic runner in the repository root. The generic runner's NumPy CI checker can independently recompute the original summary. Raw logs are not automatically suitable for publication.

## Legacy timed helper

`run.py` and the eight-case `cases.json` support the earlier time-bounded SAT/auto comparison and optional cloud helper. They use finite deadlines and a separate schema; they are not the formal400+20 unbounded experiment. The historical results are not recomputed by this source release.

旧8ケースの有限時間比較は `run.py` です。正式な無制限400＋20例とは別の実験として扱います。
