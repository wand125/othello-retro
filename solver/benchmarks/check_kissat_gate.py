"""Contention, killpg and Rust-style SIGKILL-to-child-PID gate regression tests."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--real',type=Path);args=parser.parse_args()

def group_gone(pid):
    try:os.killpg(pid,0)
    except ProcessLookupError:return True
    return False

def held_slots(directory):
    held=0
    for n in range(2):
        p=directory/f'slot{n}.lock'
        if not p.exists():continue
        with p.open('r+') as f:
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
            except BlockingIOError:held+=1
    return held

with tempfile.TemporaryDirectory(prefix='othello-kissat-gate-test-') as temp:
    d=Path(temp);gate=d/'kissat';shutil.copyfile(ROOT/'kissat_gate.py',gate);gate.chmod(0o700)
    real=d/'kissat-real'
    real.write_text('''#!/usr/bin/env python3
import fcntl,json,os,signal,sys,time
from pathlib import Path
if sys.argv[1:]==['--version']:print('4.0.3');raise SystemExit(0)
p=Path(os.environ['FAKE_STATE']);pid=os.getpid()
def update(add):
 with open(str(p)+'.lock','a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  state=json.loads(p.read_text()) if p.exists() else {'active':[],'peak':0,'groups':[]}
  if add:state['active'].append(pid);state['groups'].append(os.getpgrp())
  else:state['active'].remove(pid)
  state['peak']=max(state['peak'],len(state['active']));p.write_text(json.dumps(state))
def stop(signum,_):
 signal.signal(signum,signal.SIG_IGN)
 raise SystemExit(0)
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
update(True)
try:time.sleep(float(os.environ.get('FAKE_DURATION','.3')))
finally:update(False)
''');real.chmod(0o700)
    state=d/'state.json';env={**os.environ,'REAL_KISSAT':str(real),'KISSAT_GATE_DIR':str(d/'locks'),'KISSAT_GATE_SLOTS':'2','FAKE_STATE':str(state)}
    assert subprocess.check_output([str(gate),'--version'],env=env,text=True).strip()=='4.0.3'
    assert not (d/'locks').exists()
    jobs=[subprocess.Popen([str(gate)],env=env,start_new_session=True) for _ in range(3)]
    try:
        for job in jobs:assert job.wait(timeout=3)==0
        data=json.loads(state.read_text());assert data['peak']==2 and data['active']==[]
        assert set(data['groups']).issubset({job.pid for job in jobs})
        for sig in [signal.SIGTERM,signal.SIGKILL]:
            job=subprocess.Popen([str(gate)],env={**env,'FAKE_DURATION':'5'},start_new_session=True);jobs.append(job)
            end=time.monotonic()+2
            while time.monotonic()<end:
                if json.loads(state.read_text())['active']:break
                time.sleep(.005)
            else:raise AssertionError('fake solver did not enter')
            assert json.loads(state.read_text())['active']==[job.pid],'gate must preserve real child PID'
            if sig==signal.SIGTERM:os.killpg(job.pid,sig)
            else:job.kill() # Exactly Rust Child.kill: only direct child PID receives SIGKILL.
            job.wait(timeout=2);assert group_gone(job.pid),'orphan solver survived direct child kill'
            if sig==signal.SIGKILL:
                record=json.loads(state.read_text());record['active']=[];state.write_text(json.dumps(record))
            assert json.loads(state.read_text())['active']==[]
            assert subprocess.run([str(gate)],env={**env,'FAKE_DURATION':'.01'},timeout=2).returncode==0
    finally:
        for job in jobs:
            if job.poll() is None:os.killpg(job.pid,signal.SIGKILL);job.wait()
    result={'fake_contending_jobs':3,'maximum_real_solvers':data['peak'],'cap':2,'pid_preservation':'passed','process_group_inheritance':'passed','killpg_cleanup':'passed','direct_child_sigkill_cleanup':'passed','locks_reusable':'passed','version_bypasses_gate':'passed'}
    if args.real:
        actual=args.real.resolve();assert subprocess.check_output([str(actual),'--version'],text=True).strip()=='4.0.3'
        # Hard pigeonhole CNF, independent of the measured Othello case population.
        holes=60;pigeons=holes+1;cnf=d/'php.cnf'
        with cnf.open('w') as f:
            f.write(f'p cnf {holes*pigeons} {pigeons+holes*pigeons*(pigeons-1)//2}\n')
            for p in range(pigeons):f.write(' '.join(str(p*holes+h+1) for h in range(holes))+' 0\n')
            for h in range(holes):
                for a in range(pigeons):
                    for b in range(a):f.write(f'-{a*holes+h+1} -{b*holes+h+1} 0\n')
        live_env={**env,'REAL_KISSAT':str(actual),'KISSAT_GATE_DIR':str(d/'real-locks')}
        live=[subprocess.Popen([str(gate),'-q','--time=5',str(cnf)],env=live_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True) for _ in range(3)]
        try:
            end=time.monotonic()+2
            while time.monotonic()<end:
                if held_slots(d/'real-locks')==2:break
                time.sleep(.005)
            else:raise AssertionError('two real Kissat locks were not acquired')
            time.sleep(.2)
            assert all(p.poll() is None for p in live),'hard fixture unexpectedly completed'
            assert held_slots(d/'real-locks')==2,'real Kissat closed inherited lock descriptor'
            def is_actual(job):
                if job.poll() is not None:return False
                proc=Path(f'/proc/{job.pid}/exe')
                if proc.exists():return proc.resolve()==actual
                command=subprocess.check_output(['ps','-p',str(job.pid),'-o','comm='],text=True).strip()
                return Path(command).name==actual.name
            end=time.monotonic()+2
            while time.monotonic()<end:
                active=[job for job in live if is_actual(job)]
                if len(active)==2:break
                time.sleep(.005)
            else:raise AssertionError('expected two real and one queued gate')
            queued=next(job for job in live if job not in active)
            victim=active[0];victim.kill();victim.wait(timeout=2)
            assert group_gone(victim.pid),'orphan real solver after Rust Child.kill(SIGKILL PID only)'
            end=time.monotonic()+2;maximum=0
            while time.monotonic()<end:
                count=sum(is_actual(job) for job in live);maximum=max(maximum,count)
                assert count<=2,'real solver cap exceeded after PID cancellation'
                if is_actual(queued) and held_slots(d/'real-locks')==2:break
                time.sleep(.005)
            else:raise AssertionError('queued real solver failed to enter freed slot')
            for job in live:
                if job.poll() is None:job.kill();job.wait(timeout=2)
                assert group_gone(job.pid),'real solver orphan after child.kill'
            assert held_slots(d/'real-locks')==0
            result.update(real_kissat_version='4.0.3',real_kissat_inherited_fd_retained='passed',real_direct_pid_sigkill_no_orphan='passed',queued_solver_enters_after_pid_kill='passed',maximum_real_after_pid_kill=maximum,real_locks_released='passed')
        finally:
            for job in live:
                if job.poll() is None:os.killpg(job.pid,signal.SIGKILL);job.wait()
    print(json.dumps(result),flush=True)
