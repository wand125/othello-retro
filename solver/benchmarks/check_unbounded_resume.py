"""Control fixture only: manual interrupt a pilot and resume its exact frozen order."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--bank',type=Path,default=ROOT/'benchmarks/study-midgame-cpu222-unbounded-v1.json');args=p.parse_args()
with tempfile.TemporaryDirectory(prefix='unbounded-resume-check-') as td:
    out=Path(td)/'fixture';command=[os.sys.executable,str(ROOT/'benchmarks/benchmark_unbounded.py'),'run','--bank',str(args.bank),'--split','pilot','--output',str(out)]
    groups=[]
    with (Path(td)/'stdout.log').open('w') as log:
        proc=subprocess.Popen(command,stdout=log,stderr=log,start_new_session=True)
        try:
            end=time.monotonic()+20
            while time.monotonic()<end:
                try:
                    state=json.loads((out/'progress.json').read_text());runtime=json.loads((out/'.runtime-groups.json').read_text())
                    if state.get('stage')=='final_exact_sat' and runtime['groups']:
                        groups=[g['pgid'] for g in runtime['groups']];break
                except (FileNotFoundError,json.JSONDecodeError):pass
                assert proc.poll() is None,'fixture ended before manual interrupt'
                time.sleep(.005)
            else:raise AssertionError('fixture never reached active final SAT')
            proc.send_signal(signal.SIGTERM);assert proc.wait(timeout=5)==130
            meta=json.loads((out/'metadata.json').read_text());assert meta['status']=='interrupted'
            assert json.loads((out/'.runtime-groups.json').read_text())['groups']==[]
            for group in groups:
                end=time.monotonic()+3
                while time.monotonic()<end:
                    try:os.killpg(group,0)
                    except ProcessLookupError:break
                    time.sleep(.02)
                else:raise AssertionError('interrupted engine left a process group')
            resumed=subprocess.run([*command,'--resume'],stdout=log,stderr=log,timeout=60)
            assert resumed.returncode==0
            rows=[json.loads(x) for x in (out/'runs.jsonl').read_text().splitlines()]
            bank=json.loads(args.bank.read_text());schedule=bank['splits']['pilot']['schedule']
            assert len(rows)==len(schedule)==20
            for row,expected in zip(rows,schedule):
                assert all(row[k]==expected[k] for k in ['case','repeat','method'])
                assert row['verified'] and row['status']=='found' and row['global_deadline'] is None
            assert json.loads((out/'metadata.json').read_text())['status']=='complete'
            assert json.loads((out/'.runtime-groups.json').read_text())['groups']==[]
            interrupted=[json.loads(x) for x in (out/'interruptions.jsonl').read_text().splitlines()]
            assert interrupted and any(r['interrupted_work_seconds']>0 for r in rows)
        except BaseException:
            print((Path(td)/'stdout.log').read_text()[-5000:])
            raise
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    print(json.dumps({'fixture_only':True,'manual_interrupt_exit130':'passed','native_child_cleanup':'passed','durable_interruption_record':'passed','resume_same_case_order':'passed','completed_found_after_resume':20,'prior_work_retained':'passed','final_private_group_registry_empty':'passed'}))
