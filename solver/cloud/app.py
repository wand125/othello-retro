"""Cloud Run API and private task worker. Existing local server remains standalone."""
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import signal
import sys
import threading
import time
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import urllib.request
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))
import server as local
import records

ROLE = os.environ.get("APP_ROLE", "api")
API_BACKEND = os.environ.get("API_BACKEND_URL", "").rstrip("/")
if API_BACKEND and (urlsplit(API_BACKEND).scheme != "https" or urlsplit(API_BACKEND).path not in {"", "/"}):
    raise ValueError("API_BACKEND_URL must be an HTTPS origin")
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
REGION = os.environ.get("REGION", "asia-northeast1")
MAX_SECONDS = int(os.environ.get("MAX_SOLVE_SECONDS", "300"))
GLOBAL_DAILY = int(os.environ.get("GLOBAL_DAILY_JOBS", "1000"))
SESSION_DAILY = int(os.environ.get("SESSION_DAILY_JOBS", "100"))
TERMINAL = {"done", "cancelled", "failed"}
ID = re.compile(r"^[a-zA-Z0-9_-]{6,80}$")
_db = _tasks = None


def now():
    return dt.datetime.now(dt.timezone.utc)


def database():
    global _db
    if _db is None:
        from google.cloud import firestore
        _db = firestore.Client(project=PROJECT)
    return _db


def ref(job):
    return database().collection("othello_retro_jobs").document(job)


def usage_ref(job):
    # Audit records have no job-expiry TTL, so usage history survives job cleanup.
    return database().collection("othello_retro_usage").document(job)


def usage_identity(job, item):
    return {"job_id": job, "browser_id": item["owner"], "kind": item["kind"],
            "accepted_at": item["created_at"], "requested_seconds": item["request"]["time"],
            "day_jst": item["created_at"].astimezone(dt.timezone(dt.timedelta(hours=9))).strftime("%Y%m%d"),
            "board_sha256": hashlib.sha256(item["request"]["board"].encode()).hexdigest()}


def validate(kind, req):
    if kind not in {"solve", "fix", "optimize"}:
        raise ValueError("不明な探索です")
    if not isinstance(req, dict) or not ID.fullmatch(str(req.get("id", ""))):
        raise ValueError("探索IDが不正です")
    board = req.get("board", "")
    if not isinstance(board, str) or len(board) != 64 or set(board) - set("XO-"):
        raise ValueError("board は X/O/- の64文字で指定してください")
    def integer(key, default, low, high):
        v = req.get(key, default)
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(f"{key} は整数で指定してください")
        return max(low, min(v, high))
    data = {"id": req["id"], "board": board, "time": integer("time", 60, 10, MAX_SECONDS)}
    if kind == "fix":
        protected = req.get("protect", [])
        if not isinstance(protected, list) or any(type(s) is not int or not 0 <= s < 64 for s in protected):
            raise ValueError("保護するマスが不正です")
        data.update(k=integer("k", 2, 1, 3), solutions=integer("solutions", 3, 1, 5), protect=protected)
    if kind == "optimize":
        moves, objective = req.get("moves"), req.get("objective", "last:1")
        if objective not in local.Handler.OBJECTIVES or not isinstance(moves, list) or not 1 <= len(moves) <= 60:
            raise ValueError("棋譜・最適化の目的が不正です")
        if any(not isinstance(m, str) or not re.fullmatch(r"[a-h][1-8]", m) for m in moves):
            raise ValueError("棋譜が不正です")
        data.update(moves=moves, objective=objective, solutions=integer("solutions", 3, 1, 5))
    return data


def reserve(kind, data, owner):
    """Create job and count daily quota atomically; repeat POST is idempotent."""
    from google.cloud import firestore
    db = database()
    day = now().astimezone(dt.timezone(dt.timedelta(hours=9))).strftime("%Y%m%d")
    doc = ref(data["id"])
    glob = db.collection("othello_retro_limits").document(day)
    user = db.collection("othello_retro_limits").document(day + "-" + owner)
    @firestore.transactional
    def write(tx):
        old = doc.get(transaction=tx)
        if old.exists:
            job = old.to_dict()
            if job["owner"] != owner or job["kind"] != kind or job["request"] != data:
                raise ValueError("この探索IDは既に使われています")
            return job
        g, u = glob.get(transaction=tx), user.get(transaction=tx)
        gc, uc = (g.to_dict() or {}).get("count", 0), (u.to_dict() or {}).get("count", 0)
        if gc >= GLOBAL_DAILY or uc >= SESSION_DAILY:
            raise ValueError("試験公開の本日の探索上限に達しました。明日またお試しください")
        record = {"kind": kind, "request": data, "owner": owner, "state": "queued",
                  "created_at": now(), "expires_at": now() + dt.timedelta(days=2), "cancel": False}
        tx.set(glob, {"count": gc + 1})
        tx.set(user, {"count": uc + 1})
        tx.create(doc, record)
        tx.create(usage_ref(data["id"]), {
            **usage_identity(data["id"], record), "day_jst": day, "state": "queued",
            "board_sha256": hashlib.sha256(data["board"].encode()).hexdigest()})
        return record
    return write(db.transaction())


def enqueue(job):
    global _tasks
    from google.cloud import tasks_v2
    from google.api_core.exceptions import AlreadyExists
    from google.protobuf.duration_pb2 import Duration
    if _tasks is None:
        _tasks = tasks_v2.CloudTasksClient()
    parent = _tasks.queue_path(PROJECT, REGION, "othello-retro")
    worker = os.environ["WORKER_URL"]
    task = {"name": parent + "/tasks/" + job["request"]["id"],
            "dispatch_deadline": Duration(seconds=MAX_SECONDS + 60),
            "http_request": {"http_method": tasks_v2.HttpMethod.POST,
                "url": worker + "/internal/run", "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"id": job["request"]["id"]}).encode(),
                "oidc_token": {"service_account_email": os.environ["TASK_SERVICE_ACCOUNT"], "audience": worker}}}
    try:
        _tasks.create_task(parent=parent, task=task, timeout=15)
    except AlreadyExists:
        pass


def claim(job, attempt):
    from google.cloud import firestore
    doc = ref(job)
    @firestore.transactional
    def take(tx):
        snap = doc.get(transaction=tx)
        if not snap.exists:
            return None
        item = snap.to_dict()
        if item["state"] in TERMINAL:
            return None
        if item.get("cancel"):
            tx.update(doc, {"state": "cancelled", "result": {"status": "cancelled"}})
            return None
        if item["state"] == "running" and item.get("lease_until", now()) > now():
            raise RuntimeError("探索は別の実行で処理中です")
        count = item.get("attempts", 0) + 1
        started = now()
        tx.update(doc, {"state": "running", "attempt": attempt, "attempts": count, "started_at": started, "lease_until": started + dt.timedelta(seconds=45)})
        tx.set(usage_ref(job), {**usage_identity(job, item), "state": "running", "started_at": started, "attempts": count}, merge=True)
        return item
    return take(database().transaction())


def update_attempt(job, attempt, fields):
    from google.cloud import firestore
    doc = ref(job)
    @firestore.transactional
    def change(tx):
        snap = doc.get(transaction=tx)
        item = snap.to_dict() or {}
        if item.get("attempt") != attempt or item.get("state") in TERMINAL:
            return False
        changed = dict(fields)
        if changed.get("result", {}).get("status") == "found":
            try:
                normalized, _ = records.verify(changed["result"].get("moves"), item["request"]["board"])
                changed["result"] = {**changed["result"], "moves": normalized}
            except ValueError:
                changed.update(state="failed", result={"status": "error", "reason": "棋譜の合法性と目標盤面の照合に失敗しました"})
        tx.update(doc, changed)
        if "result" in changed:
            result = changed["result"]
            finished = changed.get("finished_at", now())
            record = records.make_record(job, item, result, finished) if not item.get("benchmark") else None
            if record:
                tx.set(records.record_ref(database(), record["id"]), record)
                result["record_id"] = record["id"]
                tx.update(doc, {"result": result})
            tx.set(usage_ref(job), {**usage_identity(job, item), "state": changed.get("state", item["state"]),
                "status": result["status"], "finished_at": finished,
                "elapsed_seconds": result.get("time", (finished - item.get("started_at", item["created_at"])).total_seconds()), "method": result.get("method"),
                "moves": sum(m != "pass" for m in result.get("moves", []))}, merge=True)
        return True
    return change(database().transaction())


def cancel_owned(job, owner):
    from google.cloud import firestore
    doc = ref(job)
    @firestore.transactional
    def cancel(tx):
        item = doc.get(transaction=tx).to_dict() or {}
        if item.get("owner") != owner:
            return False
        if item["state"] not in TERMINAL:
            finished = now()
            tx.update(doc, {"cancel": True, "state": "cancelled", "result": {"status": "cancelled"}})
            tx.set(usage_ref(job), {**usage_identity(job, item), "state": "cancelled", "status": "cancelled", "finished_at": finished,
                "elapsed_seconds": (finished - item["started_at"]).total_seconds() if item.get("started_at") else 0}, merge=True)
        return True
    return cancel(database().transaction())


def stop_process(job):
    with local.LOCK:
        proc = local.JOBS.get(job)
    if isinstance(proc, local.Worker):
        proc.cancelled = True
        proc.kill()
    elif proc:
        local.kill_job(proc)


class Runner(local.Handler):
    """Reuse the proven solver operations without binding them to a browser request."""
    def __init__(self):
        self.payload = None

    def send(self, code, body, ctype=None):
        self.payload = json.loads(body) if isinstance(body, str) else body
        if code >= 400:
            self.payload = {"status": "error", "reason": self.payload.get("error", "探索失敗")}

    def finish_job(self, job, payload):
        self.payload = payload


def execute(job):
    attempt = secrets.token_hex(16)
    item = claim(job, attempt)
    if item is None:
        return
    req, runner = item["request"], Runner()
    done, cancelled, deadline_hit = threading.Event(), threading.Event(), threading.Event()
    hard_deadline = time.monotonic() + req["time"] + (90 if item.get("benchmark_request", {}).get("model_start") == "warm" else 20)
    def monitor():
        while not done.wait(2):
            try:
                snap = ref(job).get(timeout=10).to_dict() or {}
                if snap.get("cancel") or snap.get("attempt") != attempt:
                    cancelled.set()
                    stop_process(job)
                if time.monotonic() > hard_deadline:
                    deadline_hit.set()
                    stop_process(job)
                with local.LOCK:
                    progress = dict(local.PROGRESS.get(job) or {})
                if not update_attempt(job, attempt, {"lease_until": now() + dt.timedelta(seconds=45), "progress": progress}):
                    stop_process(job)
            except Exception as exc:
                print("monitor:", type(exc).__name__, flush=True)
                # A storage outage must not permit an orphaned expensive solver.
                if time.monotonic() > hard_deadline:
                    deadline_hit.set()
                    stop_process(job)
    watch = threading.Thread(target=monitor, daemon=True)
    watch.start()
    try:
        if item.get("benchmark") and item.get("benchmark_request"):
            import benchmark_single
            result = benchmark_single.run(item["benchmark_request"], job=job)
        else:
            getattr(runner, item["kind"])(req)
            result = runner.payload or {"status": "error", "reason": "探索結果がありません"}
        if cancelled.is_set():
            result = {"status": "cancelled"}
        elif deadline_hit.is_set():
            result = {"status": "unknown", "reason": "制限時間に達しました"}
    except Exception as exc:
        print("solver:", repr(exc), flush=True)
        stop_process(job)
        result = {"status": "error", "reason": "探索処理でエラーが発生しました"}
    finally:
        done.set()
        watch.join(timeout=15)
    # Concurrent cancellation wins over a late solve result.
    if (ref(job).get().to_dict() or {}).get("cancel"):
        result = {"status": "cancelled"}
    update_attempt(job, attempt, {"state": "cancelled" if result["status"] == "cancelled" else "done",
                                  "result": result, "finished_at": now()})


class Handler(local.Handler):
    # The public product has its own assets. Local production tools are never served.
    PUBLIC_ASSETS = {
        "/public.js": ("public.js", "text/javascript; charset=utf-8"),
        "/public.css": ("public.css", "text/css; charset=utf-8"),
        "/public-examples.json": ("public-examples.json", "application/json; charset=utf-8"),
        "/paper.css": ("paper.css", "text/css; charset=utf-8"),
        "/paper.js": ("paper.js", "text/javascript; charset=utf-8"),
        "/paper-data.json": ("paper-data.json", "application/json; charset=utf-8"),
    }

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if getattr(self, "new_session", None):
            secure = "; Secure" if os.environ.get("K_SERVICE") else ""
            self.send_header("Set-Cookie", f"othello_session={self.new_session}; HttpOnly; SameSite=Lax; Path=/; Max-Age=172800{secure}")
        self.end_headers()
        self.wfile.write(raw)

    def session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            pass
        sid = cookie.get("othello_session")
        if sid is None or not re.fullmatch(r"[0-9a-f]{64}", sid.value):
            self.new_session = secrets.token_hex(32)
        self.owner = hashlib.sha256((self.new_session if getattr(self, "new_session", None) else sid.value).encode()).hexdigest()

    def respond(self, code, obj):
        return self.send(code, json.dumps(obj, ensure_ascii=False))

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 16384:
            raise ValueError("リクエストが大きすぎるか空です")
        return json.loads(self.rfile.read(length))

    def owned(self, job):
        if not ID.fullmatch(job):
            return None
        item = ref(job).get().to_dict()
        return item if item and item.get("owner") == self.owner and item["expires_at"] > now() else None

    def proxy_backend(self, data=None):
        """Keep the public origin while the owned WSL service handles jobs/state."""
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            return self.respond(403, {"error": "リクエスト元が不正です"})
        headers = {"Accept": "application/json"}
        for name in ("Cookie", "Content-Type"):
            if self.headers.get(name): headers[name] = self.headers[name]
        if origin: headers["Origin"] = API_BACKEND
        req = urllib.request.Request(API_BACKEND + self.path, data=data, headers=headers,
                                     method="POST" if data is not None else "GET")
        try:
            try: response = urllib.request.urlopen(req, timeout=20)
            except urllib.error.HTTPError as exc: response = exc
            with response:
                raw = response.read(2_000_000)
                self.send_response(response.code)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Othello-Compute", "wsl")
                for cookie in response.headers.get_all("Set-Cookie", []):
                    self.send_header("Set-Cookie", cookie)
                self.end_headers()
                self.wfile.write(raw)
        except (OSError, TimeoutError) as exc:
            print("backend:", type(exc).__name__, flush=True)
            return self.respond(503, {"status": "error", "reason": "現在計算サーバーに接続できません。少し待ってから再実行してください"})

    def do_GET(self):
        path = urlsplit(self.path)
        if path.path in {"/healthz", "/api/health"}:
            return self.respond(200, {"ok": True, "role": ROLE})
        if ROLE != "api":
            return self.respond(404, {"error": "not found"})
        if API_BACKEND and (path.path in {"/api/result", "/api/progress", "/api/records"} or path.path.startswith("/api/records/")):
            return self.proxy_backend()
        self.session()
        if path.path in {"/api/result", "/api/progress"}:
            try:
                item = self.owned(parse_qs(path.query).get("id", [""])[0])
                if path.path == "/api/progress":
                    return self.respond(200, (item or {}).get("progress", {}))
                return self.respond(200, {"status": "lost"} if not item else item.get("result", {"status": "running", "stage": item["state"]}))
            except Exception:
                return self.respond(503, {"status": "running"})
        if path.path == "/api/records" or path.path.startswith("/api/records/"):
            try:
                if path.path == "/api/records":
                    return self.respond(200, records.list_records(database(), cursor=parse_qs(path.query).get("cursor", [None])[0]))
                record = records.get_record(database(), path.path.removeprefix("/api/records/"))
                return self.respond(200, record) if record else self.respond(404, {"error": "not found"})
            except ValueError as exc:
                return self.respond(400, {"error": str(exc)})
            except Exception as exc:
                print("records:", repr(exc), flush=True)
                return self.respond(503, {"error": "棋譜を読み込めませんでした"})
        if path.path in {"/paper", "/paper/"}:
            return self.send(200, (Path(local.HERE) / "paper.html").read_bytes(), "text/html; charset=utf-8")
        example_path = re.fullmatch(r"/examples(?:/([A-Za-z0-9_-]{1,100}))?", path.path)
        if path.path in {"/", "/index.html"} or example_path:
            example_id = example_path.group(1) if example_path else None
            if example_id:
                if API_BACKEND:
                    try:
                        with urllib.request.urlopen(API_BACKEND + "/api/records/" + example_id, timeout=15) as response:
                            response.read()
                    except urllib.error.HTTPError as exc:
                        return self.respond(exc.code if exc.code in {404, 400} else 503, {"error": "not found" if exc.code == 404 else "棋譜を読み込めませんでした"})
                    except OSError:
                        return self.respond(503, {"error": "棋譜を読み込めませんでした"})
                elif not records.get_record(database(), example_id):
                    return self.respond(404, {"error": "not found"})
            html = (Path(local.HERE) / "public.html").read_text()
            config = json.dumps({"maxSeconds": MAX_SECONDS, "library": bool(example_path), "example": example_id})
            return self.send(200, html.replace("__PUBLIC_CONFIG__", config).replace("__LIBRARY_VIEW__", "true" if example_path else "false"), "text/html; charset=utf-8")
        asset = self.PUBLIC_ASSETS.get(path.path)
        if asset:
            return self.send(200, (Path(local.HERE) / asset[0]).read_bytes(), asset[1])
        return self.respond(404, {"error": "not found"})

    def do_POST(self):
        try:
            if ROLE == "worker":
                if self.path != "/internal/run":
                    return self.respond(404, {"error": "not found"})
                job = str(self.read_json().get("id", ""))
                if not ID.fullmatch(job):
                    raise ValueError("探索IDが不正です")
                execute(job)
                return self.respond(200, {"ok": True})
            if self.path not in {"/api/solve", "/api/cancel"}:
                return self.respond(404, {"error": "not found"})
            if API_BACKEND:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("リクエストが大きすぎるか空です")
                return self.proxy_backend(self.rfile.read(length))
            self.session()
            origin = self.headers.get("Origin")
            if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                return self.respond(403, {"error": "リクエスト元が不正です"})
            req = self.read_json()
            if self.path == "/api/cancel":
                job = str(req.get("id", ""))
                item = self.owned(job)
                return self.respond(200, {"cancelled": cancel_owned(job, self.owner) if item else False})
            kind = self.path.removeprefix("/api/")
            data = validate(kind, req)
            item = reserve(kind, data, self.owner)
            if item["state"] not in TERMINAL:
                enqueue(item)
            return self.respond(202, {"status": "queued", "id": data["id"], "time": data["time"]})
        except (ValueError, TypeError, KeyError) as exc:
            return self.respond(400, {"status": "error", "error": str(exc), "reason": str(exc)})
        except Exception as exc:
            print("request:", repr(exc), flush=True)
            return self.respond(503, {"status": "error", "reason": "現在処理を受け付けられません。少し待ってから再実行してください"})


def main():
    local.MAX_JOBS = 1
    local.SLOTS = threading.BoundedSemaphore(1)
    def shutdown(signum, frame):
        for job in list(local.JOBS):
            stop_process(job)
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, shutdown)
    server = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler)
    print(f"role={ROLE} port={server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
