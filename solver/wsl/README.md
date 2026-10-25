# Linux / WSL durable backend

MIT-licensed source for the serial SQLite queue, quota accounting and independent record verification used by the WSL profile. It uses `ui/server.py` and `cloud/records.py` under the same solver/ root. State, usage logs, cookies, service accounts, tunnels and host configuration are not included.

Linux/WSL用の永続キューbackendです。リポジトリrootから `cd solver` し、Rust/KissatとPython推論環境・2重みをREADMEの通り準備してから起動します。Windowsネイティブ用ではありません。

```sh
# From solver/; use a state path outside the published source tree.
STATE_DB=/tmp/othello-retro-user-state/jobs.sqlite3 OTHELLO_DEVICE=cpu RETRO_HALF=0 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python wsl/app.py
```

The server binds127.0.0.1:18766 unless PORT changes. This backend alone does not serve the web UI; the separate API/UI proxy may use its HTTPS origin. It retains the original limit of100/browser/day and1000/global/day. The worker checks `/proc/meminfo` and waits while available memory is below6GiB; ensure the guest has adequate available memory. Per-job solve time is at most300s. These operational settings differ from the unbounded benchmark.

実行記録には既定の「local CPU」または `EXECUTION_ENVIRONMENT` を記録します。元配備の機器名を他環境へ誤記しないための配布時差分であり、探索コードは変更していません。
