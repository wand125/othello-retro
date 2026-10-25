"""CLI argv and cancellation regression for true-unbounded final SAT."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,default=ROOT/'target/release/othello-retro');p.add_argument('--gate',type=Path,default=ROOT/'benchmarks/kissat_gate.py');p.add_argument('--real',type=Path,required=True);args=p.parse_args()
case=next(c for c in json.loads((ROOT/'benchmarks/cases.json').read_text())['cases'] if c['id']=='game-ba2452f6e3fa')
with tempfile.TemporaryDirectory(prefix='retro-unbounded-check-') as td:
    d=Path(td);fake=d/'argv-solver';log=d/'argv.jsonl'
    fake.write_text('''#!/usr/bin/env python3
import fcntl,json,os,sys,time
with open(os.environ['ARG_LOG'],'a') as f:
 fcntl.flock(f,fcntl.LOCK_EX);f.write(json.dumps(sys.argv[1:])+'\\n');f.flush()
time.sleep(.5)
print('s UNSATISFIABLE')
''');fake.chmod(0o700)
    fixtures={}
    for name,options in [('unbounded',['--no-time-limit']),('finite',['--time','2'])]:
        log.write_text('')
        command=[str(args.binary),'solve',case['board'],'--json','--prepass-ms','0','--solver',str(fake),*options]
        subprocess.run(command,env={**os.environ,'ARG_LOG':str(log)},capture_output=True,text=True,check=True,timeout=10)
        vectors=[json.loads(x) for x in log.read_text().splitlines()]
        assert len(vectors)==3,(name,vectors)
        if name=='unbounded':assert all(not any(a.startswith('--time') for a in argv) for argv in vectors)
        else:assert all(any(a.startswith('--time=') for a in argv) for argv in vectors)
        fixtures[name]=[[a if not a.endswith('.cnf') else '<cnf>' for a in argv] for argv in vectors]
    # Real final SAT: no time flag, gated2, manual killpg cleans the native process
    # plus active/queued real solver children. This is cancellation, not a trial cutoff.
    bindir=d/'bin';bindir.mkdir();gate=bindir/'kissat';gate.write_bytes(args.gate.read_bytes());gate.chmod(0o700)
    private_tmp=d/'native-temp';private_tmp.mkdir()
    env={**os.environ,'TMPDIR':str(private_tmp),'PATH':str(bindir)+os.pathsep+os.environ['PATH'],'REAL_KISSAT':str(args.real.resolve()),'KISSAT_GATE_DIR':str(d/'locks'),'KISSAT_GATE_SLOTS':'2'}
    proc=subprocess.Popen([str(args.binary),'solve',case['board'],'--json','--no-time-limit','--prepass-ms','0'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    try:
        end=time.monotonic()+5
        while time.monotonic()<end:
            locks=list((d/'locks').glob('slot*.lock')) if (d/'locks').exists() else []
            held=0
            for file in locks:
                with file.open('r+') as f:
                    try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
                    except BlockingIOError:held+=1
            if held==2:break
            assert proc.poll() is None,'real fixture solved before cancellation'
            time.sleep(.01)
        else:raise AssertionError('real unbounded solver did not start gated children')
        os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=3)
        end=time.monotonic()+3
        while time.monotonic()<end:
            try:os.killpg(proc.pid,0)
            except ProcessLookupError:break
            time.sleep(.02)
        else:raise AssertionError('unbounded cancellation left process group members')
        for file in (d/'locks').glob('slot*.lock'):
            with file.open('r+') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    finally:
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        proc.wait()
    print(json.dumps({'unbounded_final_portfolio_real_argv':fixtures['unbounded'],'finite_portfolio_real_argv':fixtures['finite'],
      'final_three_solvers_have_no_time_flag':True,'finite_default_keeps_time_flag':True,'manual_cancel_group_cleanup':'passed','manual_cancel_slots_released':'passed'}),flush=True)
