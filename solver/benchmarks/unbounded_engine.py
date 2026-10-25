"""True-unbounded benchmark; finite probes are algorithm policy, never trial cutoffs."""
import time
SCRIPT_STARTED=time.monotonic()
import argparse
import collections
import importlib.metadata
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid
import study_engine as common
ROOT=Path(__file__).resolve().parents[1]
ACTIVE=[]
SCRATCH=[]
RUNTIME_OUT=None

class StopStudy(BaseException):pass

def utc():return common.utc()
def write(path,obj):
    path=Path(path);tmp=path.with_name(path.name+'.tmp');common.write(tmp,obj);tmp.replace(path)
def append(path,obj):
    with Path(path).open('a') as f:
        f.write(json.dumps(obj,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
def persist_groups():
    if RUNTIME_OUT is not None:
        write(RUNTIME_OUT/'.runtime-groups.json',{'controller_pid':os.getpid(),'updated_at':utc(),'root':str(ROOT),'groups':[{'pid':p.pid,'pgid':p.pid,'command':p.args} for p in ACTIVE]})
def managed_popen(command,**kwargs):
    # Register the new process group before a manual interrupt can unwind us.
    # This parent is single-threaded during measurement; the child restores its
    # inherited signal mask before exec, so real solvers remain cancellable.
    old=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGTERM,signal.SIGINT})
    def restore():signal.pthread_sigmask(signal.SIG_SETMASK,old)
    try:
        proc=subprocess.Popen(command,start_new_session=True,preexec_fn=restore,**kwargs)
        ACTIVE.append(proc);persist_groups()
    finally:signal.pthread_sigmask(signal.SIG_SETMASK,old)
    return proc

def stop_all():
    for p in ACTIVE:
        try:os.killpg(p.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    for p in ACTIVE:
        try:p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            p.wait()
    ACTIVE.clear();persist_groups()
    for d in SCRATCH:shutil.rmtree(d,ignore_errors=True)
    SCRATCH.clear()
def scratch():
    d=tempfile.mkdtemp(prefix='othello-unbounded-');SCRATCH.append(d);return d

def guided(net,passes,undo,request,emit):
    import worker,search
    target=worker.to_hex(request['board'])
    emit({'stage':'pass_check','internal_limit_seconds':2})
    r=search.findany([target],2)
    if r['index'] is not None:return {'status':'found','moves':r['moves'],'stage':'direct'}
    stages=[('with-passes',worker.WITH_PASSES)] if r.get('unsat') else [('fast',worker.FAST),('careful',worker.CAREFUL)]
    for name,cfg in stages:
        emit({'stage':'beam_'+name,'global_deadline':None})
        model=passes if cfg['passes'] else net
        candidates=search.beam(model,undo,target,cfg['width'],cap=4 if cfg['width']<=32 else 8,stop=30,
          nsym=cfg['nsym'],refine=cfg['refine'],passes=cfg['passes'],deadline=None,
          progress=lambda event:emit({'stage':'beam_'+name,**event}))
        for i in range(0,min(len(candidates),18),6):
            chunk=candidates[i:i+6]
            emit({'stage':'candidate_sat','candidates':len(chunk),'internal_limit_seconds':20})
            result=search.findany([c for c,_ in chunk],20)
            if result['index'] is not None:
                moves=result['moves']+chunk[result['index']][1]
                if search.verify(moves,target):return {'status':'found','moves':moves,'stage':name}
    return {'status':'miss','reason':'finite guided candidate stages exhausted'}

def model_worker():
    sys.path.insert(0,str(ROOT/'ml'))
    before=time.monotonic()
    import torch,worker
    torch.set_num_threads(2)
    imported=time.monotonic();net=worker.load(str(ROOT/'ml/model.pt'));passes=worker.load(str(ROOT/'ml/model_passes.pt'));undo=worker.Undo();loaded=time.monotonic()
    x=torch.zeros((256,5,8,8),device=worker.DEV,dtype=next(net.parameters()).dtype)
    with torch.inference_mode():
        for _ in range(3):net(x,None).float().cpu().numpy()
    counters=collections.Counter()
    def enter(*_):counters['cnn_forward_attempts']+=1
    def done(*_):counters['cnn_forward_completed']+=1
    for model in [net,passes]:model.register_forward_pre_hook(enter);model.register_forward_hook(done)
    print(json.dumps({'event':'ready','device':worker.DEV,'dtype':str(next(net.parameters()).dtype),'torch_version':torch.__version__,'torch_threads':torch.get_num_threads(),
       'imports_seconds':imported-before,'model_load_seconds':loaded-imported,'warmup_seconds':time.monotonic()-loaded,
       'warmup_batch':256,'warmup_forwards':3,'cpu_backend':{'mkldnn_available':torch.backends.mkldnn.is_available(),'mkl_available':torch.backends.mkl.is_available(),'cpu_capability':torch.backends.cpu.get_cpu_capability(),'build_config':torch.__config__.show()}}),flush=True)
    for line in sys.stdin:
        request=json.loads(line);counters.clear();stages=collections.Counter()
        def emit(event):
            if event.get('stage'):stages[event['stage']]+=1
            print(json.dumps({'event':'progress','payload':event}),flush=True)
        try:result=guided(net,passes,undo,request,emit)
        except Exception as exc:result={'status':'miss','reason':type(exc).__name__+':'+str(exc)}
        result['diagnostic']={'stage_counts':dict(stages),**dict(counters),'cnn_used':counters.get('cnn_forward_completed',0)>0,'found_via':result.get('stage'),'global_deadline':None}
        print(json.dumps({'event':'result','payload':result}),flush=True)

class ResidentModel:
    def __init__(self,out,progress):self.proc=None;self.buffer=b'';self.out=out;self.progress=progress
    def recv(self):
        while True:
            if b'\n' in self.buffer:
                line,self.buffer=self.buffer.split(b'\n',1);event=json.loads(line)
                if event['event']=='progress':self.progress(event['payload']);continue
                return event
            ready,_,_=select.select([self.proc.stdout],[],[],.5)
            if ready:
                data=os.read(self.proc.stdout.fileno(),65536)
                if not data:raise RuntimeError('model worker ended before result')
                self.buffer+=data
            if self.proc.poll() is not None and not self.buffer:raise RuntimeError('model worker exited')
    def prepare(self):
        if self.proc and self.proc.poll() is None:return None
        before=time.monotonic();directory=scratch();self.buffer=b''
        error=(self.out/'model-stderr.log').open('ab')
        self.proc=managed_popen([sys.executable,str(Path(__file__).resolve()),'model-worker'],cwd=ROOT,env={**os.environ,'TMPDIR':directory},stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=error)
        error.close()
        event=self.recv()
        if event['event']!='ready':raise RuntimeError('model readiness protocol error')
        return {'event':'model_ready','wall_seconds':time.monotonic()-before,**event}
    def solve(self,case):
        self.proc.stdin.write(json.dumps({'board':case['board']}).encode()+b'\n');self.proc.stdin.flush()
        event=self.recv()
        if event['event']!='result':raise RuntimeError('model result protocol error')
        return event['payload']

def preflight(bank,bankpath):
    p=bank['protocol'];sha=common.sha;digest=common.digest
    if digest(p)!=bank['protocol_sha256']:raise RuntimeError('protocol hash mismatch')
    if p['trial_time_limit_seconds'] is not None or p['final_sat_time_limit_seconds'] is not None:raise RuntimeError('this runner requires true-unbounded protocol')
    for file,expected in p['common_source_hashes'].items():
        if sha(ROOT/file)!=expected:raise RuntimeError('source/model hash mismatch: '+file)
    native={str(f.relative_to(ROOT)):sha(f) for f in [ROOT/'Cargo.toml',ROOT/'Cargo.lock',*sorted((ROOT/'src').rglob('*.rs'))]}
    if digest(native)!=p['native_source_aggregate_sha256']:raise RuntimeError('native source mismatch')
    versions={name:importlib.metadata.version(name) for name in ['torch','numpy']}
    if versions['torch'].split('+')[0]!=p['torch_version'] or versions['numpy']!=p['numpy_version']:raise RuntimeError('package version mismatch '+str(versions))
    actual=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None
    if sys.platform=='linux' and actual!=p['benchmark_cpu_affinity_linux']:raise RuntimeError('Linux affinity mismatch')
    rustup=shutil.which('rustup') or str(Path.home()/'.cargo/bin/rustup')
    compiler=subprocess.check_output([rustup,'run','1.98.0','rustc','--version'],text=True).strip()
    if not compiler.startswith('rustc 1.98.0 '):raise RuntimeError('Rust1.98.0 required')
    gate=shutil.which('kissat');real=Path(os.environ.get('REAL_KISSAT',''))
    if not gate or sha(gate)!=p['sat_concurrency']['gate_sha256']:raise RuntimeError('execFD gate mismatch')
    if not real.is_absolute() or not real.is_file():raise RuntimeError('REAL_KISSAT required')
    version=subprocess.check_output([gate,'--version'],text=True).strip()
    if version!='4.0.3' or os.environ.get('KISSAT_GATE_SLOTS','2')!='2':raise RuntimeError('Kissat4.0.3/cap2 required')
    directory=Path(os.environ.get('KISSAT_GATE_DIR',''))
    if not directory.is_absolute():raise RuntimeError('absolute private gate directory required')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    if directory.stat().st_uid!=os.getuid() or directory.stat().st_mode&0o077:raise RuntimeError('gate directory must be owned mode0700')
    capability=subprocess.run([str(ROOT/'target/release/othello-retro')],capture_output=True,text=True)
    if '--no-time-limit' not in capability.stdout+capability.stderr:raise RuntimeError('native --no-time-limit capability missing')
    return {'bank_sha256':sha(bankpath),'protocol_sha256':bank['protocol_sha256'],'versions':versions,'native_source_hashes':native,'native_source_aggregate_sha256':digest(native),
      'native_binary_sha256':sha(ROOT/'target/release/othello-retro'),'rust_compiler':compiler,'host_descriptor':common.host_descriptor(),'affinity':actual,'nice':os.getpriority(os.PRIO_PROCESS,0),
      'real_kissat_sha256':sha(real),'gate_sha256':sha(gate),'gate_directory':str(directory),'real_solver_cap':2,'global_deadline':None,'final_sat_argv_policy':'--no-time-limit at native solve; no --time forwarded to final Kissat'}

def native_solve(case,progress):
    directory=scratch();command=[str(ROOT/'target/release/othello-retro'),'solve',case['board'],'--json','--no-time-limit']
    assert not any(a.startswith('--time') for a in command)
    progress({'stage':'final_exact_sat','global_deadline':None,'kissat_time_option':None})
    proc=managed_popen(command,env={**os.environ,'TMPDIR':directory},stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    stdout,stderr=proc.communicate() # Intentionally has no timeout.
    # Also clean descendants after an abnormal native exit; normal portfolio
    # completion has already killed its direct execFD solver children.
    try:os.killpg(proc.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    ACTIVE.remove(proc);persist_groups();shutil.rmtree(directory,ignore_errors=True);SCRATCH.remove(directory)
    if proc.returncode:raise RuntimeError('unbounded native failed: '+stderr.decode(errors='replace')[-1000:])
    result=json.loads(stdout.decode().strip().splitlines()[-1])
    if result.get('status')!='found':raise RuntimeError('unbounded known-reachable case returned '+result.get('status','missing status'))
    return result

def analyze(rows,cases,replicates=3000):
    import numpy as np
    grouped=collections.defaultdict(list)
    for row in rows:grouped[row['case']].append(row)
    strata={}
    for case in cases:strata.setdefault(case.get('stratum',case['stones']),[]).append(case)
    rng=np.random.default_rng(730253);output={}
    def one(groups):
        total=sum(len(g) for g in groups.values());sd=np.zeros(replicates);ad=np.zeros(replicates);sm=am=0
        for group in groups.values():
            sat=np.array([np.mean([r['effective_wall_seconds'] for r in grouped[c['id']] if r['method']=='sat']) for c in group]);auto=np.array([np.mean([r['effective_wall_seconds'] for r in grouped[c['id']] if r['method']=='auto']) for c in group])
            indices=rng.integers(0,len(group),size=(replicates,len(group)));weight=len(group)/total
            sd+=sat[indices].mean(axis=1)*weight;ad+=auto[indices].mean(axis=1)*weight;sm+=sat.mean()*weight;am+=auto.mean()*weight
        ratio=am/sm;ci=np.quantile(ad/sd,[.025,.975]).tolist()
        return {'sat_mean_seconds':sm,'auto_mean_seconds':am,'auto_div_sat':ratio,'ratio_ci95':ci,'ratio_ci_relative_radius':max(abs(v-ratio) for v in ci)/abs(ratio),
          'auto_minus_sat_seconds':am-sm,'difference_ci95':np.quantile(ad-sd,[.025,.975]).tolist(),'independent_cases':total}
    for name,group in strata.items():output[str(name)]=one({name:group})
    output['fixed_stratum_overall']=one(strata)
    counts={}
    for method in ['sat','auto']:
        values=[r['effective_wall_seconds'] for r in rows if r['method']==method]
        counts[method]={'completed_found':len(values),'independent_cases':len(cases),'mean_seconds':float(np.mean(values)),'median_seconds':float(np.median(values)),'p95_seconds':float(np.quantile(values,.95)),
           'all_repeats_success_case_wilson95':common.wilson(len(cases),len(cases))}
    return {'counts':counts,'estimates':output,'bootstrap_seed':730253,'bootstrap_replicates':replicates,'bootstrap_unit':'independent case, all method/repeat pairs kept together within stratum',
      'global_deadline':None,'timeout_count':0,'cost_precision_met':bool(len(cases)>=400 and output['fixed_stratum_overall']['ratio_ci95'][0]!=output['fixed_stratum_overall']['ratio_ci95'][1] and output['fixed_stratum_overall']['ratio_ci_relative_radius']<=.05),'primary_cost':'effective_wall_seconds, including interrupted attempt work','precision_met':False,'precision_note':'All completed known-reachable cases are found; this boundary observation does not establish zero success uncertainty. Descriptive cost ratio CI is reported. N20 is auxiliary, never treated as60 independent cases.'}

def run(bankpath,split,out,resume=False,pausefile=None):
    global RUNTIME_OUT
    os.environ.update(OTHELLO_DEVICE='cpu',RETRO_HALF='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2')
    bank=json.loads(bankpath.read_text());section=bank['splits'][split]
    for key,field in [('cases','cases_sha256'),('schedule','schedule_sha256')]:
        if common.digest(section[key])!=section[field]:raise RuntimeError('frozen '+key+' hash mismatch')
    info=preflight(bank,bankpath)
    sys.path.insert(0,str(ROOT/'cloud'));from records import verify
    cases={c['id']:c for c in section['cases']}
    for case in cases.values():assert verify(case['reference_moves'],case['board'])[1] is case['terminal']
    rows=[];interruptions=[]
    if resume:
        meta=json.loads((out/'metadata.json').read_text())
        if meta['bank_sha256']!=info['bank_sha256']:raise RuntimeError('resume bank mismatch')
        path=out/'runs.jsonl';raw=path.read_bytes() if path.exists() else b'';good=0
        for line in raw.splitlines(keepends=True):
            try:row=json.loads(line)
            except json.JSONDecodeError:
                if good+len(line)!=len(raw):raise
                path.write_bytes(raw[:good]);break
            expected=section['schedule'][len(rows)]
            if any(row[k]!=expected[k] for k in ['case','repeat','method']):raise RuntimeError('resume order mismatch')
            verify(row['moves'],cases[row['case']]['board']);rows.append(row);good+=len(line)
        if (out/'interruptions.jsonl').exists():interruptions=[json.loads(x) for x in (out/'interruptions.jsonl').read_text().splitlines()]
    else:
        out.mkdir(parents=True,exist_ok=False)
        meta={**info,'started_at':utc(),'split':split,'cases_sha256':section['cases_sha256'],'schedule_sha256':section['schedule_sha256'],'planned_trials':len(section['schedule']),
          'independent_cases':len(cases),'protocol':bank['protocol'],'attempts':[],'timing':'accepted-proof receipt excludes model preparation/final independent replay; rejected-guided proof checks count before exact fallback. Interrupted attempt work is retained separately and added to effective cost.'}
    RUNTIME_OUT=out
    attempt={'started_at':utc(),'first_trial_index':len(rows),'host_before':common.host_snapshot()};meta['attempts'].append(attempt);meta['status']='running';write(out/'metadata.json',meta)
    current=None;started=None;last_progress=0;last_payload={};pausefile=pausefile or out/'PAUSE'
    def progress(event,force=False):
        nonlocal last_progress,last_payload
        stage_changed=event.get('stage')!=last_payload.get('stage')
        last_payload={**(current or {}),**event,'updated_at':utc()}
        if force or stage_changed or time.monotonic()-last_progress>=1:write(out/'progress.json',last_payload);last_progress=time.monotonic()
    model=ResidentModel(out,progress)
    def cancel(*_):raise StopStudy()
    signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)
    try:
        for index in range(len(rows),len(section['schedule'])):
            trial=section['schedule'][index];case=cases[trial['case']];current={'trial_index':index,**trial,'stones':case['stones'],'stratum':case.get('stratum',case['stones'])};started=None
            while pausefile.exists():
                meta['status']='paused';write(out/'metadata.json',meta);progress({'stage':'paused_between_trials'},True);time.sleep(.5)
            meta['status']='running'
            host=common.host_snapshot()
            if host['mem_available_bytes'] is not None and host['mem_available_bytes']<6*1024**3:raise RuntimeError('MemAvailable below6GiB; study interrupted, no result recorded')
            if case['stones']>=44:
                preparation=model.prepare()
                if preparation:append(out/'preparation.jsonl',{**current,**preparation})
            progress({'stage':'trial_start','started_at':utc(),'global_deadline':None},True);started=time.monotonic();diagnostic=None;fallback=False;guided_rejected=False;result=None
            if trial['method']=='auto' and case['stones']>=44:
                candidate=model.solve(case);diagnostic=candidate.get('diagnostic')
                if candidate.get('status')=='found':
                    received=time.monotonic()
                    try:
                        normalized,_=verify(candidate['moves'],case['board']);result={**candidate,'moves':normalized}
                    except (ValueError,KeyError):guided_rejected=True
            if result is None:
                fallback=trial['method']=='auto' and case['stones']>=44
                result=native_solve(case,progress);received=time.monotonic()
                normalized,_=verify(result['moves'],case['board']);result={**result,'moves':normalized}
            elapsed=received-started;prior=sum(x['elapsed_seconds'] for x in interruptions if x['trial_index']==index)
            row={**current,'status':'found','success':1,'verified':True,'invalid_or_wrong':False,'moves':result['moves'],'wall_seconds':elapsed,'interrupted_work_seconds':prior,'effective_wall_seconds':elapsed+prior,
              'global_deadline':None,'final_sat_time_limit':None,'guided_diagnostic':diagnostic,'guided_candidate_rejected':guided_rejected,'fallback_observed':fallback,'host_before':host,'host_after':common.host_snapshot()}
            append(out/'runs.jsonl',row);rows.append(row);started=None
            meta['completed_trials']=len(rows);write(out/'metadata.json',meta);progress({'stage':'trial_complete','wall_seconds':elapsed},True)
            print(json.dumps({k:row[k] for k in ['trial_index','case','repeat','method','status','wall_seconds']},ensure_ascii=False),flush=True)
        meta['status']='complete'
    except (StopStudy,KeyboardInterrupt):
        if current is not None and started is not None:
            item={**current,'elapsed_seconds':time.monotonic()-started,'interrupted_at':utc(),'reason':'manual_cancel'};append(out/'interruptions.jsonl',item)
        meta['status']='interrupted';progress({'stage':'manual_interrupt'},True)
    except BaseException as exc:
        if current is not None and started is not None:append(out/'interruptions.jsonl',{**current,'elapsed_seconds':time.monotonic()-started,'interrupted_at':utc(),'reason':type(exc).__name__+':'+str(exc)})
        meta['status']='error';write(out/'error.json',{'current':current,'reason':type(exc).__name__+':'+str(exc)});raise
    finally:
        stop_all();attempt.update(finished_at=utc(),host_after=common.host_snapshot(),completed_trials=len(rows));meta['completed_trials']=len(rows);meta['finished_at']=utc();write(out/'metadata.json',meta)
    if meta['status']=='complete':
        analysis_started=time.monotonic();summary=analyze(rows,list(cases.values()));meta['analysis_wall_seconds']=time.monotonic()-analysis_started;meta['program_wall_seconds']=time.monotonic()-SCRIPT_STARTED;summary['metadata']=meta
        write(out/'metadata.json',meta);write(out/'summary.json',summary)
    print(json.dumps({'output':str(out),'status':meta['status'],'completed_trials':len(rows),'program_wall_seconds':time.monotonic()-SCRIPT_STARTED}),flush=True)
    if meta['status']!='complete':raise SystemExit(130)

def main():
    parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest='command',required=True)
    r=subs.add_parser('run');r.add_argument('--bank',type=Path,required=True);r.add_argument('--split',choices=['pilot','main'],default='main');r.add_argument('--output',type=Path,required=True);r.add_argument('--resume',action='store_true');r.add_argument('--pause-file',type=Path)
    subs.add_parser('model-worker');args=parser.parse_args()
    if args.command=='model-worker':model_worker()
    else:run(args.bank,args.split,args.output,args.resume,args.pause_file)
if __name__=='__main__':main()
