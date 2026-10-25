"""One serial solver process, with a reusable model worker and hard per-job timers."""
import json
import signal
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ui'))
import server

class Runner:
    result=None
    def finish_job(self,job,result): self.result=result

class Deadline(Exception): pass

def cleanup():
    model=server.WORKER.proc
    server.WORKER.kill()
    if model:
        try: model.wait(timeout=3)
        except Exception: model.kill(); model.wait()
    for proc in list(server.JOBS.values()):
        if hasattr(proc,'pid'): server.kill_job(proc)
    server.JOBS.clear()

def alarm(*_):
    signal.setitimer(signal.ITIMER_REAL,0)
    cleanup()
    raise Deadline()

def stop(*_):
    signal.setitimer(signal.ITIMER_REAL,0)
    cleanup()
    raise SystemExit(0)

signal.signal(signal.SIGALRM,alarm)
signal.signal(signal.SIGTERM,stop)
for line in sys.stdin:
    req=json.loads(line)
    runner=Runner(); started=time.monotonic()
    try:
        signal.setitimer(signal.ITIMER_REAL,req['time']+1)
        server.Handler.run_solver(runner,req['board'],req['time'],req['id'])
        result=runner.result or {'status':'error','reason':'探索結果がありません'}
    except Deadline: result={'status':'unknown','reason':'制限時間に達しました'}
    except Exception:
        cleanup()
        result={'status':'error','reason':'探索処理でエラーが発生しました'}
    finally: signal.setitimer(signal.ITIMER_REAL,0)
    print(json.dumps({'result':result,'wall_seconds':time.monotonic()-started}),flush=True)
cleanup()
