"""WSL public profile: serial, durable SQLite queue and independently verified records."""
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import select
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cloud'))
import records
DB = Path(os.environ.get('STATE_DB', ROOT / 'state' / 'jobs.sqlite3'))
ID = re.compile(r'[A-Za-z0-9_-]{6,80}\Z')
MAX_SECONDS = 300
STOP = threading.Event()
CURRENT = {}
POOL = None
CURRENT_LOCK = threading.Lock()


def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def connect():
    db = sqlite3.connect(DB, timeout=15)
    db.row_factory = sqlite3.Row
    return db

def setup():
    DB.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with connect() as db:
        db.executescript('''PRAGMA journal_mode=WAL;
          CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,request TEXT NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL,started_at TEXT,finished_at TEXT,result TEXT);
          CREATE TABLE IF NOT EXISTS limits(day TEXT NOT NULL,owner TEXT NOT NULL,count INTEGER NOT NULL,PRIMARY KEY(day,owner));
          CREATE TABLE IF NOT EXISTS usage(id TEXT PRIMARY KEY,body TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,sort_key TEXT NOT NULL,body TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS records_sort ON records(sort_key DESC);''')
        # A process restart cannot resume child solvers; finish interrupted jobs explicitly.
        for row in db.execute("SELECT * FROM jobs WHERE state='running'").fetchall():
            finalize(db, row, {'status':'error','reason':'サーバー再起動により探索が中断しました'}, 'failed')
    os.chmod(DB, 0o600)


def finalize(db, row, result, state='done'):
    # Treat solver output as untrusted until strict forward replay succeeds.
    if result.get('status') == 'found':
        try:
            normalized, _ = records.verify(result.get('moves'), json.loads(row['request'])['board'])
            result = {**result, 'moves':normalized}
        except (ValueError, TypeError, KeyError):
            result = {'status':'error','reason':'探索結果の棋譜を合法手の再生で検証できませんでした'}
            state = 'failed'
    finished = now()
    db.execute('UPDATE jobs SET state=?,finished_at=?,result=? WHERE id=?', (state,finished,json.dumps(result),row['id']))
    old = db.execute('SELECT body FROM usage WHERE id=?',(row['id'],)).fetchone()
    usage = json.loads(old['body'])
    usage.update(state=state,status=result['status'],finished_at=finished,
                 elapsed_seconds=result.get('time'),method=result.get('method'),
                 wall_seconds=(dt.datetime.fromisoformat(finished)-dt.datetime.fromisoformat(row['started_at'])).total_seconds() if row['started_at'] else 0)
    db.execute('UPDATE usage SET body=? WHERE id=?',(json.dumps(usage),row['id']))
    record = records.make_record(row['id'], {'kind':'solve','request':json.loads(row['request']),
             'created_at':row['created_at'],'started_at':row['started_at']}, result, finished, environment=os.environ.get('EXECUTION_ENVIRONMENT', 'local CPU'))
    if record:
        db.execute('INSERT OR IGNORE INTO records VALUES(?,?,?)',(record['id'],record['sort_key'],json.dumps(record)))


def reserve(data, owner):
    created = now()
    day = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime('%Y%m%d')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT * FROM jobs WHERE id=?',(data['id'],)).fetchone()
        if old:
            if old['owner'] != owner or json.loads(old['request']) != data: raise ValueError('この探索IDは既に使われています')
            return
        for who, limit in [('*',1000),(owner,100)]:
            row = db.execute('SELECT count FROM limits WHERE day=? AND owner=?',(day,who)).fetchone()
            if row and row['count'] >= limit: raise ValueError('本日の探索上限に達しました。明日またお試しください')
        # Bound outstanding work, while allowing the active job and a short durable queue.
        if db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0] >= 20:
            raise ValueError('探索が混み合っています。少し待ってからお試しください')
        for who in ('*',owner):
            db.execute('INSERT INTO limits VALUES(?,?,1) ON CONFLICT(day,owner) DO UPDATE SET count=count+1',(day,who))
        db.execute('INSERT INTO jobs(id,owner,request,state,created_at) VALUES(?,?,?,?,?)',
                   (data['id'],owner,json.dumps(data),'queued',created))
        usage = {'job_id':data['id'],'browser_id':owner,'kind':'solve','accepted_at':created,'day_jst':day,
                 'state':'queued','requested_seconds':data['time'],'board_sha256':hashlib.sha256(data['board'].encode()).hexdigest()}
        db.execute('INSERT INTO usage VALUES(?,?)',(data['id'],json.dumps(usage)))


def stop_process(proc):
    if proc.poll() is not None: return
    proc.terminate() # benchmark child handles SIGTERM by killing tracked solver/model groups.
    try: proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid,signal.SIGKILL)
        proc.wait()


def available_memory():
    for line in Path(os.environ.get('MEMINFO_PATH','/proc/meminfo')).read_text().splitlines():
        if line.startswith('MemAvailable:'): return int(line.split()[1])*1024
    return 0


def work():
    global POOL
    while not STOP.wait(.3):
        if available_memory() < 6*1024**3:
            if POOL and POOL.poll() is None: stop_process(POOL)
            POOL=None
            continue
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1").fetchone()
            if row is None: continue
            started = now()
            db.execute("UPDATE jobs SET state='running',started_at=? WHERE id=?",(started,row['id']))
            usage=json.loads(db.execute('SELECT body FROM usage WHERE id=?',(row['id'],)).fetchone()['body'])
            usage.update(state='running',started_at=started)
            db.execute('UPDATE usage SET body=? WHERE id=?',(json.dumps(usage),row['id']))
        request=json.loads(row['request'])
        if POOL is None or POOL.poll() is not None:
            POOL=subprocess.Popen([sys.executable,str(ROOT/'wsl/runner.py')],stdin=subprocess.PIPE,
                      stdout=subprocess.PIPE,stderr=sys.stderr,text=True,start_new_session=True)
        proc=POOL
        with CURRENT_LOCK: CURRENT.update(id=row['id'],proc=proc)
        reason=None
        result=None
        try:
            proc.stdin.write(json.dumps(request)+'\n'); proc.stdin.flush()
            deadline=time.monotonic()+request['time']+8
            while proc.poll() is None:
                with connect() as db: state=db.execute('SELECT state FROM jobs WHERE id=?',(row['id'],)).fetchone()['state']
                if state=='cancelled' or STOP.is_set(): reason='cancelled'
                elif available_memory()<6*1024**3: reason='memory'
                elif time.monotonic()>deadline: reason='deadline'
                if reason: stop_process(proc); break
                ready,_,_=select.select([proc.stdout],[],[],.2)
                if ready:
                    line=proc.stdout.readline()
                    if line: result=json.loads(line)['result']
                    break
        except (OSError,ValueError,KeyError) as exc:
            print('solver:',type(exc).__name__,flush=True)
            stop_process(proc)
        if reason=='cancelled': result={'status':'cancelled'}
        elif reason=='memory': result={'status':'error','reason':'サーバーの空きメモリ不足により探索を中断しました'}
        elif reason=='deadline': result={'status':'unknown','reason':'制限時間に達しました'}
        elif result is None: result={'status':'error','reason':'探索処理でエラーが発生しました'}
        with CURRENT_LOCK: CURRENT.clear()
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT * FROM jobs WHERE id=?',(row['id'],)).fetchone()
            if current['state']!='cancelled': finalize(db,current,result,'done' if result['status']!='error' else 'failed')


class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): print(fmt % args,flush=True)
    def session(self):
        jar=SimpleCookie()
        try: jar.load(self.headers.get('Cookie',''))
        except Exception: pass
        old=jar.get('othello_session')
        self.new_session=secrets.token_hex(32) if not old or not re.fullmatch('[0-9a-f]{64}',old.value) else None
        self.owner=hashlib.sha256((self.new_session or old.value).encode()).hexdigest()
    def send(self,code,body,ctype='application/json; charset=utf-8'):
        raw=body.encode() if isinstance(body,str) else body
        self.send_response(code)
        self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
        if getattr(self,'new_session',None):
            secure='; Secure' if os.environ.get('PUBLIC_HTTPS','1')=='1' else ''
            self.send_header('Set-Cookie',f'othello_session={self.new_session}; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000{secure}')
        self.end_headers()
        self.wfile.write(raw)
    def respond(self,code,obj): return self.send(code,json.dumps(obj,ensure_ascii=False))
    def owned(self,ident):
        if not ID.fullmatch(ident): return None
        with connect() as db: row=db.execute('SELECT * FROM jobs WHERE id=? AND owner=?',(ident,self.owner)).fetchone()
        return row
    def get_record(self,ident):
        with connect() as db: row=db.execute('SELECT body FROM records WHERE id=?',(ident,)).fetchone()
        if row: return records.public(json.loads(row['body']))
        return next((records.public(r) for r in records.static_records() if r['id']==ident),None)
    def do_GET(self):
        path=urlsplit(self.path); qs=parse_qs(path.query)
        if path.path in ('/healthz','/api/health'): return self.respond(200,{'ok':True,'role':'wsl','environment':'Ryzen 9 9950X / WSL / CPU affinity 20-23 / model worker reuse'})
        self.session()
        if path.path in ('/api/result','/api/progress'):
            row=self.owned(qs.get('id',[''])[0])
            if path.path=='/api/progress': return self.respond(200,{})
            return self.respond(200,{'status':'lost'} if not row else json.loads(row['result']) if row['result'] else {'status':'running','stage':row['state']})
        try:
            if path.path=='/api/records':
                raw_cursor=qs.get('cursor',[None])[0]
                cursor=records.decode_cursor(raw_cursor) if raw_cursor else None
                with connect() as db:
                    dynamic=[json.loads(r['body']) for r in db.execute('SELECT body FROM records WHERE sort_key < ? ORDER BY sort_key DESC LIMIT 21',(cursor or 'zzzz',))]
                allrows=dynamic+records.static_records()
                allrows=sorted([r for r in allrows if not cursor or r['sort_key']<cursor],key=lambda r:r['sort_key'],reverse=True)
                page=allrows[:20]
                return self.respond(200,{'records':[records.public(r) for r in page],
                   'next_cursor':records.encode_cursor(page[-1]['sort_key']) if len(allrows)>20 else None})
            if path.path.startswith('/api/records/'):
                row=self.get_record(path.path[len('/api/records/'):])
                return self.respond(200,row) if row else self.respond(404,{'error':'not found'})
        except ValueError as e: return self.respond(400,{'error':str(e)})
        example=re.fullmatch(r'/examples(?:/([A-Za-z0-9_-]{1,100}))?',path.path)
        if path.path in ('/','/index.html') or example:
            ident=example.group(1) if example else None
            if ident and not self.get_record(ident): return self.respond(404,{'error':'not found'})
            html=(ROOT/'ui/public.html').read_text()
            config=json.dumps({'maxSeconds':MAX_SECONDS,'library':bool(example),'example':ident})
            return self.send(200,html.replace('__PUBLIC_CONFIG__',config).replace('__LIBRARY_VIEW__','true' if example else 'false'),'text/html; charset=utf-8')
        assets={'/public.js':('public.js','text/javascript'),'/public.css':('public.css','text/css'),'/public-examples.json':('public-examples.json','application/json')}
        if path.path in assets:
            name,ctype=assets[path.path]; return self.send(200,(ROOT/'ui'/name).read_bytes(),ctype+'; charset=utf-8')
        return self.respond(404,{'error':'not found'})
    def do_POST(self):
        self.session()
        if self.path not in ('/api/solve','/api/cancel'): return self.respond(404,{'error':'not found'})
        origin=self.headers.get('Origin')
        if origin and urlsplit(origin).netloc!=self.headers.get('Host'): return self.respond(403,{'error':'リクエスト元が不正です'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=16384: raise ValueError('リクエストのサイズが不正です')
            req=json.loads(self.rfile.read(n))
            if not isinstance(req,dict): raise ValueError('リクエストが不正です')
            if self.path=='/api/cancel':
                row=self.owned(str(req.get('id','')))
                if row and row['state'] in ('queued','running'):
                    with connect() as db:
                        db.execute('BEGIN IMMEDIATE')
                        current=db.execute('SELECT * FROM jobs WHERE id=?',(row['id'],)).fetchone()
                        if current['state'] in ('queued','running'): finalize(db,current,{'status':'cancelled'},'cancelled')
                return self.respond(200,{'cancelled':row is not None})
            if not ID.fullmatch(str(req.get('id',''))): raise ValueError('探索IDが不正です')
            board=req.get('board')
            if not isinstance(board,str) or not re.fullmatch('[XO-]{64}',board): raise ValueError('盤面が不正です')
            seconds=req.get('time',60)
            if type(seconds) is not int: raise ValueError('時間は整数で指定してください')
            data={'id':req['id'],'board':board,'time':max(10,min(seconds,MAX_SECONDS))}
            reserve(data,self.owner)
            return self.respond(202,{'status':'queued','id':data['id'],'time':data['time']})
        except (ValueError,TypeError,KeyError) as e: return self.respond(400,{'status':'error','reason':str(e),'error':str(e)})
        except Exception as e:
            print(type(e).__name__,str(e),flush=True)
            return self.respond(503,{'status':'error','reason':'現在処理を受け付けられません'})


def main():
    setup()
    threading.Thread(target=work,daemon=True).start()
    http=ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('PORT','18766'))),Handler)
    http.daemon_threads=True
    def shutdown(*_):
        STOP.set()
        with CURRENT_LOCK: proc=CURRENT.get('proc') or POOL
        if proc: stop_process(proc)
        raise SystemExit(0)
    signal.signal(signal.SIGTERM,shutdown); signal.signal(signal.SIGINT,shutdown)
    print('WSL public listening',http.server_address,flush=True)
    http.serve_forever()

if __name__=='__main__': main()
