"""盤面から棋譜を復元する UI のローカルサーバー（標準ライブラリのみ）。

usage: python3 ui/server.py [--host 127.0.0.1] [--port 8765]
ブラウザで http://HOST:PORT/ を開く。ソルバーは ../target/release/othello-retro（要 cargo build --release）。
"""
import glob, json, os, select, signal, subprocess, sys, tempfile, threading, time
from auto_policy import incomplete_terminal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "..", "target", "release", "othello-retro")
JOBS = {}  # 探索 ID → Popen
LOCK = threading.Lock()
MAX_JOBS = 2  # 常時起動するので同時探索数を絞る（1 探索で kissat を 3 本使う）
SLOTS = threading.BoundedSemaphore(MAX_JOBS)
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "ml", "model.pt")
BEAM_MIN_MOVES = 40  # これ以上石が置かれた盤面は、先に学習モデル＋SAT（ビーム）を試す


class Worker:
    """ml/worker.py（評価器付きビームサーチ）の常駐プロセス。torch の読み込みが重いので使い回す。
    同時に使えるのは 1 件だけ。中止されたらプロセスごと止め、次に使うときに起動し直す。"""

    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.cancelled = False

    @staticmethod
    def _readline(proc, timeout):
        # 中止で別スレッドが self.proc を消しても困らないよう、プロセスは引数で受け取る
        try:
            r, _, _ = select.select([proc.stdout], [], [], max(0, timeout))
            return proc.stdout.readline() if r else None
        except (OSError, ValueError):
            return None

    def _ensure(self):
        if self.proc and self.proc.poll() is None:
            return True
        self.proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "ml", "worker.py"), MODEL], cwd=ROOT,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, start_new_session=True)
        line = self._readline(self.proc, 120)
        if not line or json.loads(line).get("status") != "ready":
            self.kill()
            return False
        return True

    def solve(self, board, budget):
        """見つかれば着手列、見つからなければ None（呼び出し側は self.lock を持っていること）"""
        t0 = time.time()
        if not self._ensure():
            return None
        left = budget - (time.time() - t0)
        proc = self.proc
        if left < 5 or proc is None:
            return None
        try:
            proc.stdin.write(json.dumps({"board": board, "time": left}) + "\n")
            proc.stdin.flush()
        except (OSError, ValueError):
            return None
        line = self._readline(proc, left + 30)
        if not line:  # 応答が無い（止まった・中止された）→ 作り直す
            self.kill()
            return None
        res = json.loads(line)
        return res["moves"] if res.get("status") == "found" else None

    def kill(self):
        if self.proc:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        self.proc = None


WORKER = Worker()

# 探索の結果は ID ごとにしばらく取っておく。ページを再読み込みして接続が切れても、
# 探索は続け、新しいページが /api/result で受け取れるようにする
RUNNING = set()
RESULTS = {}  # 探索 ID → (終了時刻, 結果)
PROGRESS = {}  # 最適化 ID → 途中経過（最新の改善・見つけた別解の数）
RESULT_TTL = 3600


def keep_result(job, payload):
    now = time.time()
    with LOCK:
        for k in [k for k, (t, _) in RESULTS.items() if now - t > RESULT_TTL]:
            del RESULTS[k]
        RESULTS[job] = (now, payload)


def kill_job(proc):
    """ソルバーと、その子の kissat をまとめて止め、一時 CNF を消す。"""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    for f in glob.glob(os.path.join(tempfile.gettempdir(), f"othello-retro-{proc.pid}-*.cnf")):
        try:
            os.remove(f)
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[ui] " + fmt % args + "\n")

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    # 配信するファイル（ここに無いパスは 404）
    STATIC = {
        "/": ("index.html", "text/html; charset=utf-8"),
        "/index.html": ("index.html", "text/html; charset=utf-8"),
        "/player": ("player.html", "text/html; charset=utf-8"),
        "/player.html": ("player.html", "text/html; charset=utf-8"),
        "/video": ("video.html", "text/html; charset=utf-8"),
        "/video.html": ("video.html", "text/html; charset=utf-8"),
        "/common.js": ("common.js", "text/javascript; charset=utf-8"),
        "/video-export.js": ("video-export.js", "text/javascript; charset=utf-8"),
        "/mediabunny.js": ("mediabunny.js", "text/javascript; charset=utf-8"),
        "/MEDIABUNNY-LICENSE.txt": ("MEDIABUNNY-LICENSE.txt", "text/plain; charset=utf-8"),
        "/MEDIABUNNY-VERSION.txt": ("MEDIABUNNY-VERSION.txt", "text/plain; charset=utf-8"),
        "/common.css": ("common.css", "text/css; charset=utf-8"),
    }

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/api/progress":
            job = dict(p.split("=", 1) for p in query.split("&") if "=" in p).get("id", "")
            with LOCK:
                return self.send(200, json.dumps(PROGRESS.get(job) or {}))
        if path == "/api/result":
            job = dict(p.split("=", 1) for p in query.split("&") if "=" in p).get("id", "")
            with LOCK:
                if job in RESULTS:
                    return self.send(200, json.dumps(RESULTS[job][1]))
                running = job in RUNNING
            return self.send(200, json.dumps({"status": "running" if running else "lost"}))
        hit = self.STATIC.get(path)
        if not hit:
            return self.send(404, '{"error":"not found"}')
        with open(os.path.join(HERE, hit[0]), "rb") as f:
            self.send(200, f.read(), hit[1])

    def read_json(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_POST(self):
        try:
            req = self.read_json()
        except json.JSONDecodeError:
            return self.send(400, '{"error":"bad json"}')
        if self.path == "/api/solve":
            return self.solve(req)
        if self.path == "/api/optimize":
            return self.optimize(req)
        if self.path == "/api/fix":
            return self.fix(req)
        if self.path == "/api/cancel":
            with LOCK:
                proc = JOBS.pop(str(req.get("id")), None)
            if isinstance(proc, Worker):
                proc.cancelled = True
                proc.kill()
            elif proc:
                kill_job(proc)
            return self.send(200, json.dumps({"cancelled": proc is not None}))
        self.send(404, '{"error":"not found"}')

    def solve(self, req):
        board = str(req.get("board", ""))
        if len(board) != 64 or set(board) - set("XO-"):
            return self.send(400, json.dumps({"error": "board は X/O/- の 64 文字"}))
        limit = max(1, min(int(req.get("time", 60)), 3600))
        job = str(req.get("id", ""))
        if not os.path.exists(BIN):
            return self.send(500, json.dumps({"error": f"ソルバーが無い: {BIN}（cargo build --release を実行）"}))
        if not SLOTS.acquire(blocking=False):
            return self.send(200, json.dumps({"status": "error", "reason": f"他の探索が実行中です（同時 {MAX_JOBS} 件まで）。しばらくしてから再実行してください"}))
        with LOCK:
            RUNNING.add(job)
        try:
            self.run_solver(board, limit, job)
        finally:
            with LOCK:
                RUNNING.discard(job)
            SLOTS.release()

    OBJECTIVES = {"last:1", "last:3", "last:5", "last:10", "total", "asmr"}

    def optimize(self, req):
        """見つかった棋譜を起点に、目的を最大化した棋譜と同じ値の別解を探す（othello-retro optimize）"""
        board = str(req.get("board", ""))
        moves = [m for m in req.get("moves", []) if isinstance(m, str) and len(m) == 2]
        obj = str(req.get("objective", "last:1"))
        if len(board) != 64 or set(board) - set("XO-") or not moves or obj not in self.OBJECTIVES:
            return self.send(400, json.dumps({"error": "board / moves / objective が不正"}))
        limit = max(5, min(int(req.get("time", 60)), 1800))
        nsol = max(1, min(int(req.get("solutions", 5)), 20))
        job = str(req.get("id", ""))
        if not SLOTS.acquire(blocking=False):
            return self.send(200, json.dumps({"status": "error", "reason": f"他の探索が実行中です（同時 {MAX_JOBS} 件まで）"}))
        with LOCK:
            RUNNING.add(job)
            PROGRESS[job] = {}
        try:
            proc = subprocess.Popen([BIN, "optimize", board, "--moves", "".join(moves), "--objective", obj,
                                     "--opt-time", str(limit), "--solutions", str(nsol)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            with LOCK:
                JOBS[job] = proc
            done, alts = None, 0
            for line in proc.stdout:  # 改善・別解のたびに 1 行届く
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("event") == "done":
                    done = ev
                else:
                    alts += ev.get("event") == "alternative"
                    with LOCK:
                        PROGRESS[job] = {"event": ev["event"], "value": ev["value"], "alternatives": alts}
            proc.wait()
            with LOCK:
                JOBS.pop(job, None)
            if proc.returncode is not None and proc.returncode < 0:
                return self.finish_job(job, {"status": "cancelled"})
            if not done:
                return self.finish_job(job, {"status": "error", "reason": (proc.stderr.read() or "optimize failed").strip()[-500:]})
            return self.finish_job(job, {"status": "optimized", **done})
        finally:
            with LOCK:
                RUNNING.discard(job)
                PROGRESS.pop(job, None)
            SLOTS.release()

    def fix(self, req):
        """到達不能な盤面を、なるべく少ない石の色の変更で到達可能にする（othello-retro fix --mode nearest）"""
        board = str(req.get("board", ""))
        if len(board) != 64 or set(board) - set("XO-"):
            return self.send(400, json.dumps({"error": "board は X/O/- の 64 文字"}))
        k = max(1, min(int(req.get("k", 2)), 4))
        nsol = max(1, min(int(req.get("solutions", 3)), 10))
        limit = max(10, min(int(req.get("time", 300)), 3600))
        protect = 0
        for s in req.get("protect", []):
            if isinstance(s, int) and 0 <= s < 64:
                protect |= 1 << s
        job = str(req.get("id", ""))
        if not SLOTS.acquire(blocking=False):
            return self.send(200, json.dumps({"status": "error", "reason": f"他の探索が実行中です（同時 {MAX_JOBS} 件まで）"}))
        with LOCK:
            RUNNING.add(job)
            PROGRESS[job] = {}
        try:
            # A（「k 個以下」を 1 回の SAT）。A' との同時実行（--mode nearest-both）は CPU の取り合いで負荷の高い環境では遅かったので使わない
            proc = subprocess.Popen([BIN, "fix", board, "--mode", "nearest", "--k", str(k), "--solutions", str(nsol),
                                     "--protect", f"{protect:016x}", "--opt-time", str(limit)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            with LOCK:
                JOBS[job] = proc
            fixes, status = [], "none"
            for line in proc.stdout:  # 直し方が見つかるたびに 1 行届く
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("event") == "fix":
                    fixes.append({k2: ev[k2] for k2 in ("k", "changed", "board", "moves")})
                    with LOCK:
                        PROGRESS[job] = {"fixes": len(fixes), "k": ev["k"]}
                elif ev.get("event") == "done":
                    status = ev.get("status", "none")
            proc.wait()
            with LOCK:
                JOBS.pop(job, None)
            if proc.returncode is not None and proc.returncode < 0:
                return self.finish_job(job, {"status": "cancelled", "fixes": fixes})
            return self.finish_job(job, {"status": "fixed" if fixes else status, "fixes": fixes})
        finally:
            with LOCK:
                RUNNING.discard(job)
                PROGRESS.pop(job, None)
            SLOTS.release()

    def finish_job(self, job, payload):
        """結果を保存してから返す（接続が切れていても保存は残る）"""
        keep_result(job, payload)
        try:
            self.send(200, json.dumps(payload))
        except (BrokenPipeError, ConnectionResetError):
            pass

    def run_solver(self, board, limit, job):
        t0 = time.time()
        placed = 60 - board.count("-")
        # 石が多い盤面は、先に学習モデルで候補を絞って SAT（速いが見つからないこともある）。
        # ワーカーが使用中なら飛ばして SAT に直行する
        direct_exact = os.environ.get("RETRO_AUTO_POLICY", "baseline") == "lightweight" and incomplete_terminal(board)
        if placed >= BEAM_MIN_MOVES and not direct_exact and os.path.exists(MODEL) and WORKER.lock.acquire(blocking=False):
            try:
                WORKER.cancelled = False
                with LOCK:
                    JOBS[job] = WORKER
                moves = WORKER.solve(board, min(limit, max(20, limit * 0.6)))
            finally:
                with LOCK:
                    JOBS.pop(job, None)
                WORKER.lock.release()
            if WORKER.cancelled:
                return self.finish_job(job, {"status": "cancelled"})
            if moves:
                return self.finish_job(job, {"status": "found", "reason": "", "moves": moves,
                                         "time": round(time.time() - t0, 3), "method": "beam"})
        left = int(limit - (time.time() - t0))
        if left < 1:
            return self.finish_job(job, {"status": "unknown", "reason": "", "moves": [], "time": round(time.time() - t0, 3)})
        text = "\n".join(board[i:i + 8] for i in range(0, 64, 8))
        proc = subprocess.Popen([BIN, "solve", "--json", "--time", str(left)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        with LOCK:
            JOBS[job] = proc
        try:
            out, err = proc.communicate(text, timeout=limit + 60)
        except subprocess.TimeoutExpired:
            kill_job(proc)
            out, err = "", "timeout"
        finally:
            with LOCK:
                JOBS.pop(job, None)
        if proc.returncode is not None and proc.returncode < 0:
            return self.finish_job(job, {"status": "cancelled"})
        line = out.strip().splitlines()[-1] if out.strip() else ""
        try:
            res = json.loads(line)
            res["time"], res["method"] = round(time.time() - t0, 3), "sat"
            self.finish_job(job, res)
        except json.JSONDecodeError:
            self.finish_job(job, {"status": "error", "reason": (err or out or "solver failed").strip()[-500:]})


def main():
    host = sys.argv[sys.argv.index("--host") + 1] if "--host" in sys.argv else "127.0.0.1"
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"http://{host}:{port}/", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        with LOCK:
            for p in JOBS.values():
                if isinstance(p, subprocess.Popen):
                    kill_job(p)
        WORKER.kill()


if __name__ == "__main__":
    main()
