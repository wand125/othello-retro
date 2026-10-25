"""Common four-environment CPU study engine. Solver policy remains frozen; versions and strata come from the bank."""
import time
SCRIPT_STARTED=time.monotonic()
import argparse
import collections
import datetime as dt
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import signal
import shutil
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
STONES=[]  # Stratum identifiers loaded from the frozen bank.
BUDGET=60
DIRS=[(r,c) for r in (-1,0,1) for c in (-1,0,1) if r or c]

def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(obj): return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(path,obj): Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def model_worker():
    sys.path.insert(0,str(ROOT/'ml'))
    started=time.monotonic()
    import torch
    import worker
    torch.set_num_threads(2)
    imported=time.monotonic()
    net=worker.load(str(ROOT/'ml/model.pt'));passes=worker.load(str(ROOT/'ml/model_passes.pt'));undo=worker.Undo()
    loaded=time.monotonic()
    x=torch.zeros((256,5,8,8),device=worker.DEV,dtype=next(net.parameters()).dtype)
    with torch.inference_mode():
        for _ in range(3):net(x,None).float().cpu().numpy()
    ready=time.monotonic()
    print(json.dumps({'status':'ready','device':worker.DEV,'dtype':str(next(net.parameters()).dtype),'torch_version':torch.__version__,'torch_threads':torch.get_num_threads(),
        'imports_seconds':imported-started,'model_load_seconds':loaded-imported,'warmup_seconds':ready-loaded,'warmup_batch':256,'warmup_forwards':3,'cpu_backend':{'mkldnn_available':torch.backends.mkldnn.is_available(),'mkldnn_enabled':torch.backends.mkldnn.enabled,'mkl_available':torch.backends.mkl.is_available(),'cpu_capability':torch.backends.cpu.get_cpu_capability(),'build_config':torch.__config__.show()}}),flush=True)
    counters=collections.Counter()
    def forward_enter(*_): counters['cnn_forward_attempts']+=1
    def forward_done(*_): counters['cnn_forward_completed']+=1
    hooks=[]
    for model in [net,passes]:
        hooks.append(model.register_forward_pre_hook(forward_enter))
        hooks.append(model.register_forward_hook(forward_done))
    for line in sys.stdin:
        req=json.loads(line);counters.clear();stages=collections.Counter();phases=collections.Counter()
        def progress(event):
            if event.get('stage'):stages[event['stage']]+=1
            if event.get('phase'):phases[event['phase']]+=1
        try:res=worker.handle(net,undo,req,passes,progress=progress)
        except Exception as exc:res={'status':'miss','reason':type(exc).__name__+':'+str(exc)}
        res['diagnostic']={'stage_counts':dict(stages),'phase_counts':dict(phases),**dict(counters),
          'cnn_evaluation_stage_entered':phases.get('evaluate',0)>0,'cnn_used':counters.get('cnn_forward_completed',0)>0,
          'found_via':res.get('stage'),'guided_status':res.get('status')}
        print(json.dumps(res),flush=True)


def host_descriptor():
    import platform
    result={'machine':platform.machine(),'platform':platform.platform(),'logical_cpus':os.cpu_count()}
    if Path('/proc/cpuinfo').exists():
        result['cpu_model']=next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),None)
    elif sys.platform=='darwin':
        for key,label in [('machdep.cpu.brand_string','cpu_model'),('hw.physicalcpu','physical_cpus')]:
            try:result[label]=subprocess.check_output(['sysctl','-n',key],text=True,timeout=3).strip()
            except (subprocess.SubprocessError,OSError):result[label]=None
    return result

def host_snapshot():
    memory=None
    if Path('/proc/meminfo').exists():
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemAvailable:'):memory=int(line.split()[1])*1024
    return {'time':utc(),'load_average':list(os.getloadavg()),'mem_available_bytes':memory}

def wilson(success,n):
    if not n:return None
    z=1.959963984540054;p=success/n;den=1+z*z/n;center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,center-half),min(1,center+half)]

def estimate(case_rows):
    means={}
    for method in ['sat','auto']:
        selected=[r for rows in case_rows for r in rows if r['method']==method]
        means[method]={key:statistics.mean(r[key] for r in selected) for key in ['success','capped_cost_seconds','par2_seconds']}
    out={}
    for key in ['success','capped_cost_seconds','par2_seconds']:
        out[key]={'sat':means['sat'][key],'auto':means['auto'][key],'auto_minus_sat':means['auto'][key]-means['sat'][key]}
        if key!='success':out[key]['auto_div_sat']=means['auto'][key]/means['sat'][key]
    return out

def analysis(rows,cases,replicates=3000):
    grouped=collections.defaultdict(list)
    for row in rows:grouped[row['case']].append(row)
    layers={s:[grouped[c['id']] for c in cases if c.get('stratum',c['stones'])==s and c['id'] in grouped] for s in STONES}
    rng=random.Random(730253);full=[r for group in layers.values() for r in group]
    def one(groups):
        flat=[r for g in groups.values() for r in g];point=estimate(flat);draws=[]
        for _ in range(replicates):
            sample=[rng.choice(group) for group in groups.values() for _ in range(len(group))]
            draws.append(estimate(sample))
        for metric,values in point.items():
            for key,value in list(values.items()):
                samples=sorted(d[metric][key] for d in draws)
                low=samples[int(.025*(replicates-1))];high=samples[int(.975*(replicates-1))]
                values[key]={'estimate':value,'ci95':[low,high]}
        point['boundary_checks']={m:{'all_trials_success':all(r['success'] for group in flat for r in group if r['method']==m),'all_trials_fail':all(not r['success'] for group in flat for r in group if r['method']==m)} for m in ['sat','auto']}
        return point
    details={str(s):one({s:g}) for s,g in layers.items() if g}
    details['fixed_stratum_overall']=one({s:g for s,g in layers.items() if g})
    counts={}
    for method in ['sat','auto']:
        selected=[r for r in rows if r['method']==method]
        clusters=[[r for r in group if r['method']==method] for group in full]
        all_success=sum(all(r['success'] for r in group) for group in clusters)
        counts[method]={'trials':len(selected),'successes':sum(r['success'] for r in selected),'timeouts_or_unknown':sum(r['status']=='unknown' for r in selected),
          'invalid_or_wrong':sum(r['invalid_or_wrong'] for r in selected),'all_repeats_success_cases':all_success,'independent_cases':len(clusters),
          'all_repeats_success_wilson95':wilson(all_success,len(clusters)),
          'successful_median_seconds':statistics.median(r['wall_seconds'] for r in selected if r['success']) if any(r['success'] for r in selected) else None}
    return {'bootstrap':'stratified independent-case cluster bootstrap; all repeat pairs remain together','bootstrap_replicates':replicates,'counts':counts,'estimates':details,'precision_met':False,'precision_note':'Pilot does not establish precision. Boundary-degenerate bootstrap CIs never establish zero uncertainty. Binary all-repeats-success Wilson CI targets a separate estimand.'}


class Deadline(Exception):pass

def run(bankpath,split,out):
    global BUDGET,STONES
    bank=json.loads(bankpath.read_text());protocol=bank['protocol'];section=bank['splits'][split]
    BUDGET=protocol['seconds_per_trial'];groups=protocol.get('strata') or protocol['target_stones'];STONES=[v['id'] if isinstance(v,dict) else v for v in groups]
    assert isinstance(BUDGET,int) and BUDGET>0
    if sys.platform=='linux' and sorted(os.sched_getaffinity(0))!=protocol['benchmark_cpu_affinity_linux']:raise RuntimeError('Linux benchmark affinity must match frozen protocol')
    assert digest(protocol)==bank['protocol_sha256']
    assert protocol['common_engine_sha256']==sha(__file__),'Common engine hash mismatch'
    assert protocol['common_runner_sha256']==sha(ROOT/'benchmarks/study_runner.py'),'Common runner hash mismatch'
    kissat_path=shutil.which('kissat')
    if not kissat_path:raise RuntimeError('Benchmark Kissat gate required on PATH')
    gate_sha=sha(ROOT/'benchmarks/kissat_gate.py')
    if sha(kissat_path)!=gate_sha or protocol['sat_concurrency']['gate_sha256']!=gate_sha:raise RuntimeError('Common Kissat gate hash mismatch')
    real_kissat=Path(os.environ.get('REAL_KISSAT') or (Path(kissat_path).absolute().parent/'kissat-real'))
    if not real_kissat.is_absolute() or not real_kissat.is_file():raise RuntimeError('REAL_KISSAT absolute executable required')
    gate_slots=int(os.environ.get('KISSAT_GATE_SLOTS','2'))
    if gate_slots!=2 or protocol['sat_concurrency']['real_solver_cap']!=2:raise RuntimeError('Controlled benchmark requires real SAT concurrency cap2')
    gate_dir=Path(os.environ.get('KISSAT_GATE_DIR',''))
    if not os.environ.get('KISSAT_GATE_DIR') or not gate_dir.is_absolute():raise RuntimeError('Explicit absolute KISSAT_GATE_DIR required')
    gate_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    if gate_dir.stat().st_uid!=os.getuid() or gate_dir.stat().st_mode&0o077:raise RuntimeError('KISSAT_GATE_DIR must be owned mode0700')
    kissat_version=subprocess.check_output([kissat_path,'--version'],text=True,timeout=5).strip()
    if kissat_version!='4.0.3':raise RuntimeError('Kissat4.0.3 required, got '+kissat_version)
    assert digest(section['cases'])==section['cases_sha256'] and digest(section['schedule'])==section['schedule_sha256']
    os.environ.update(OTHELLO_DEVICE='cpu',RETRO_HALF='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2')
    native_source_paths=[ROOT/'Cargo.toml',ROOT/'Cargo.lock',*sorted((ROOT/'src').rglob('*.rs'))]
    native_sources={str(p.relative_to(ROOT)):sha(p) for p in native_source_paths}
    native_source_aggregate=digest(native_sources)
    if native_source_aggregate!=protocol['native_source_aggregate_sha256']:raise RuntimeError('Native source aggregate mismatch')
    for relative,expected in protocol['algorithm_source_hashes'].items():
        if sha(ROOT/relative)!=expected:raise RuntimeError('Algorithm/model hash mismatch: '+relative)
    rustup=shutil.which('rustup') or str(Path.home()/'.cargo/bin/rustup')
    compiler=subprocess.check_output([rustup,'run',protocol['rust_toolchain'],'rustc','--version'],text=True,timeout=10).strip()
    if not compiler.startswith('rustc '+protocol['rust_toolchain']+' '):raise RuntimeError('Rust compiler version mismatch')
    versions={x:importlib.metadata.version(x) for x in ['torch','numpy']}
    if versions['torch'].split('+')[0]!=protocol['torch_version'].split('+')[0] or versions['numpy']!=protocol['numpy_version']:raise RuntimeError('Frozen protocol package versions do not match: '+str(versions))
    sys.path.insert(0,str(ROOT/'cloud'));from records import verify
    for case in section['cases']:assert verify(case['reference_moves'],case['board'])[1] is case['terminal']
    sys.path.insert(0,str(ROOT/'ui'));import server
    out.mkdir(parents=True,exist_ok=False)
    events=[];job='';phase='';rows=[];deadline_component=None
    program_started=SCRIPT_STARTED
    def stop_process(proc):
        if isinstance(proc,server.Worker):
            child=proc.proc;proc.kill()
        else:child=proc;server.kill_job(proc)
        if child:
            try:child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait(timeout=1)
    def clean_current():
        with server.LOCK:proc=server.JOBS.get(job)
        if proc:stop_process(proc)
    def alarm(*_):
        nonlocal deadline_component
        with server.LOCK:active=server.JOBS.get(job)
        deadline_component='guided' if isinstance(active,server.Worker) else 'native_sat' if active is not None else 'unknown'
        signal.setitimer(signal.ITIMER_REAL,0)
        if phase=='prepare':stop_process(server.WORKER)
        else:clean_current()
        raise Deadline()
    signal.signal(signal.SIGALRM,alarm)
    def terminate(*_):raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,terminate)
    class BenchWorker(server.Worker):
        last_diagnostic=None
        def _readline(self,proc,timeout):
            line=server.Worker._readline(proc,timeout)
            if line:
                value=json.loads(line)
                if isinstance(value.get('diagnostic'),dict):self.last_diagnostic=value['diagnostic']
            return line
        def _ensure(self):
            if self.proc and self.proc.poll() is None:return True
            self.proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'model-worker'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,start_new_session=True)
            line=self._readline(self.proc,40)
            if not line:self.kill();return False
            ready=json.loads(line)
            if ready.get('status')!='ready':self.kill();return False
            events.append({'event':'model_ready',**ready})
            return True
    class Runner:
        result=None
        def finish_job(self,ident,result):self.result=result
    server.WORKER=BenchWorker()
    protected=['benchmarks/study_engine.py','benchmarks/study_runner.py','benchmarks/kissat_gate.py','ml/search.py','ml/worker.py','ml/train.py','ml/model.pt','ml/model_passes.pt','ui/server.py','target/release/othello-retro']
    metadata={'started_at':utc(),'baseline_short_driver_sha256':'9d747244f67141ffc8afc39e2b1505f7ae4d40398a844ef9d9a23bd6545f4b34','split':split,'bank_sha256':sha(bankpath),'protocol_sha256':bank['protocol_sha256'],'cases_sha256':section['cases_sha256'],'schedule_sha256':section['schedule_sha256'],
      'independent_cases':len(section['cases']),'planned_trials':len(section['schedule']),'protocol':protocol,'versions':versions,
      'source_hashes':{p:sha(ROOT/p) for p in protected},'native_source_hashes':native_sources,'native_source_aggregate_sha256':native_source_aggregate,'rust_compiler':compiler,'kissat':{'version':kissat_version,'real_binary_sha256':sha(real_kissat),'gate_sha256':gate_sha},'sat_concurrency_control':{'real_solver_cap':gate_slots,'gate_dir':str(gate_dir),'real_kissat':str(real_kissat),'lock_files':['slot0.lock','slot1.lock'],'timing':'wrapper startup and slot wait are included in measured wall cost; benchmark policy differs from uncapped production portfolios'},'python':sys.version,'platform':sys.platform,'logical_cpus':os.cpu_count(),
      'affinity':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,'nice':os.getpriority(os.PRIO_PROCESS,0),'host_before':host_snapshot(),'host_descriptor':host_descriptor(),
      'timing':'warm model setup excluded and logged; wall timer covers production run_solver including process/IPC/model branch/native fallback; independent replay excluded; all failures use full budget capped cost and2x budget PAR2',
      'status':'running'}
    write(out/'metadata.json',metadata)
    started_study=time.monotonic();cases={c['id']:c for c in section['cases']};old_prepare_pair=None
    try:
        for number,trial in enumerate(section['schedule']):
            case=cases[trial['case']];pair=(case['id'],trial['repeat']);snapshot=host_snapshot()
            if snapshot['mem_available_bytes'] is not None and snapshot['mem_available_bytes']<6*1024**3:raise RuntimeError('MemAvailable below6GiB')
            if pair!=old_prepare_pair:
                phase='prepare';before=time.monotonic();count=len(events);signal.setitimer(signal.ITIMER_REAL,45)
                try:
                    if case['stones']>=44 and not server.WORKER._ensure():raise RuntimeError('model preparation failed')
                finally:signal.setitimer(signal.ITIMER_REAL,0)
                if len(events)>count:events[-1].update(case=case['id'],repeat=trial['repeat'],preparation_wall_seconds=time.monotonic()-before)
                old_prepare_pair=pair
            # A timed-out first auto trial may terminate the model; ensure the paired preparation condition.
            if case['stones']>=44 and (server.WORKER.proc is None or server.WORKER.proc.poll() is not None):
                phase='prepare';before=time.monotonic();signal.setitimer(signal.ITIMER_REAL,45)
                try:
                    if not server.WORKER._ensure():raise RuntimeError('model reload failed')
                finally:signal.setitimer(signal.ITIMER_REAL,0)
                events[-1].update(case=case['id'],repeat=trial['repeat'],preparation_wall_seconds=time.monotonic()-before)
            server.WORKER.last_diagnostic=None;deadline_component=None
            server.BEAM_MIN_MOVES=1000 if trial['method']=='sat' else 40
            runner=Runner();job=f'study-{number}';phase='trial';deadline_hit=False;start=time.monotonic()
            signal.setitimer(signal.ITIMER_REAL,BUDGET)
            try:
                server.Handler.run_solver(runner,case['board'],BUDGET,job)
                result=runner.result or {'status':'error','reason':'missing result'}
            except Deadline:deadline_hit=True;result={'status':'unknown','reason':'strict trial deadline'}
            except Exception as exc:clean_current();result={'status':'error','reason':type(exc).__name__+':'+str(exc)}
            finally:
                elapsed=time.monotonic()-start;signal.setitimer(signal.ITIMER_REAL,0)
            solver_status=result.get('status','error');verified=False;invalid=False
            if solver_status=='found':
                try:verify(result['moves'],case['board']);verified=True
                except (ValueError,KeyError):invalid=True
            if solver_status=='unreachable':invalid=True
            within=elapsed<=BUDGET and not deadline_hit
            success=verified and within and not invalid
            status='unknown' if verified and not within else solver_status
            row={**trial,'stones':case['stones'],'stratum':case.get('stratum',case['stones']),'seed':case['seed'],'trial_index':number,'status':status,'solver_status':solver_status,'actual_method':result.get('method'),
              'wall_seconds':elapsed,'server_seconds':result.get('time'),'budget_seconds':BUDGET,'deadline_hit':deadline_hit,'within_budget':within,'verified':verified,'success':int(success),'invalid_or_wrong':invalid,
              'capped_cost_seconds':elapsed if success else BUDGET,'par2_seconds':elapsed if success else 2*BUDGET,
              'moves':result.get('moves',[]),'reason':result.get('reason',''),'guided_diagnostic':server.WORKER.last_diagnostic,
              'guided_eligible':trial['method']=='auto' and case['stones']>=44,'deadline_component':deadline_component,
              'fallback_observed':trial['method']=='auto' and case['stones']>=44 and (result.get('method')=='sat' or deadline_component=='native_sat'),'host_before':snapshot,'host_after':host_snapshot()}
            rows.append(row)
            with (out/'runs.jsonl').open('a') as file:file.write(json.dumps(row,ensure_ascii=False)+'\n')
            write(out/'preparation.json',events)
            print(json.dumps({key:row[key] for key in ['trial_index','case','stones','repeat','method','status','wall_seconds','success']},ensure_ascii=False),flush=True)
        metadata['status']='complete'
    except BaseException:
        metadata['status']='interrupted';raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);clean_current();stop_process(server.WORKER)
        metadata.update(finished_at=utc(),trial_loop_wall_seconds=time.monotonic()-started_study,completed_trials=len(rows),host_after=host_snapshot())
        write(out/'metadata.json',metadata);write(out/'preparation.json',events)
    analysis_started=time.monotonic()
    summary=analysis(rows,section['cases']);summary['metadata']=metadata
    layer_costs={s:statistics.mean(r['wall_seconds'] for r in rows if r['stratum']==s) for s in STONES}
    summary['pilot_projection']={'main_planned_trials':protocol['main_independent_games']*protocol['main_repeats']*2,'layer_mean_observed_seconds':layer_costs,
       'estimated_main_trial_seconds':protocol['main_independent_games']/len(STONES)*protocol['main_repeats']*2*sum(layer_costs.values()),'note':'Runtime estimate only, from disjoint pilot seeds. Two cases per layer do not accurately estimate population success or variance. No timing-based main-case selection.'} if split=='pilot' else None
    overall=summary['estimates']['fixed_stratum_overall']
    cost=overall['capped_cost_seconds']['auto_div_sat'];success=overall['success']['auto_minus_sat']
    cost_radius=max(abs(v-cost['estimate']) for v in cost['ci95'])/abs(cost['estimate'])
    success_radius=max(abs(v-success['estimate']) for v in success['ci95'])
    complete=len(rows)==len(section['schedule']) and all(len([r for r in rows if r['case']==c['id'] and r['method']==m])==(1 if split=='pilot' else 3) for c in section['cases'] for m in ['sat','auto'])
    enough=split=='main' and len(section['cases'])>=400 and complete
    boundary_success=any(any(flags.values()) for flags in overall['boundary_checks'].values()) or success['ci95'][0]==success['ci95'][1]
    boundary_cost=cost['ci95'][0]==cost['ci95'][1]
    checks={'capped_cost_auto_div_sat':{'ci_relative_radius':cost_radius,'target':0.05,'boundary_or_degenerate':boundary_cost,'precision_met':bool(enough and not boundary_cost and cost_radius<=.05)},
      'success_auto_minus_sat':{'ci_absolute_radius':success_radius,'target':0.05,'boundary_or_degenerate':boundary_success,'precision_met':bool(enough and not boundary_success and success_radius<=.05)}}
    summary.update(precision_checks=checks,precision_met=bool(all(x['precision_met'] for x in checks.values())),precision_note='Formal precision declaration requires at least400independent cases and complete predeclared trials. A20case auxiliary study reports descriptive stratified case-cluster bootstrap3000replicates without a precision guarantee. Pilot never establishes precision. Degenerate boundary intervals do not establish precision. Wilson targets separate all-repeats-success binary estimand.')
    metadata.update(analysis_wall_seconds=time.monotonic()-analysis_started,program_wall_seconds_so_far=time.monotonic()-program_started)
    summary['guided_diagnostics']={'auto_eligible_trials':sum(r['guided_eligible'] for r in rows),'cnn_used_trials':sum(bool((r['guided_diagnostic'] or {}).get('cnn_used')) for r in rows),
      'direct_sat_guided_trials':sum((r['guided_diagnostic'] or {}).get('found_via')=='direct' for r in rows),'fallback_observed_trials':sum(r['fallback_observed'] for r in rows),
      'diagnostic_unavailable_eligible_trials':sum(r['guided_eligible'] and r['guided_diagnostic'] is None for r in rows)}
    write(out/'metadata.json',metadata)
    write(out/'summary.json',summary)
    lines=['# '+protocol['id']+' '+split,'',f"独立対局{len(section['cases'])}件、{len(rows)}試行。各{BUDGET}秒、CPU/FP32・Torch{protocol['torch_version']}、モデル準備は別計時。",'',
      f'各試行の成功は合法な棋譜の独立再生と{BUDGET}秒以内を条件とします。unknownは到達不能の意味ではありません。3反復を独立標本数として数えません。','',
      '| 層 | 方法 | 成功/試行 | 平均capped秒 | 平均PAR2秒 | 平均観測wall秒 |','|---:|---|---:|---:|---:|---:|']
    for stones in STONES:
        for method in ['sat','auto']:
            selected=[r for r in rows if r['stratum']==stones and r['method']==method]
            lines.append(f"| {stones} | {method} | {sum(r['success'] for r in selected)}/{len(selected)} | {statistics.mean(r['capped_cost_seconds'] for r in selected):.4f} | {statistics.mean(r['par2_seconds'] for r in selected):.4f} | {statistics.mean(r['wall_seconds'] for r in selected):.4f} |")
    if split=='pilot':lines+=['',f"主試行の所要時間概算は{summary['pilot_projection']['estimated_main_trial_seconds']/60:.1f}分（試行時間のみ）。pilotは各層2例しかなく、この概算の精度も限られます。mainの実施判断前の予備調査です。"]
    lines+=['','この標本の範囲はprotocolに事前固定した層だけです。途中400局面と終局20局面は独立の表で報告します。参照棋譜のパス有無は全ての復元棋譜にパスが必要かを保証しません。',
      'paired差/比と層化case-cluster bootstrap95%CIはsummary.jsonに全値を記録します。モデル・コードはライセンス確認まで非公開です。']
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    metadata['program_wall_seconds']=time.monotonic()-program_started;write(out/'metadata.json',metadata);summary['metadata']=metadata;write(out/'summary.json',summary)
    print(json.dumps({'output':str(out),'status':metadata['status'],'trial_loop_wall_seconds':metadata['trial_loop_wall_seconds'],'program_wall_seconds':metadata['program_wall_seconds'],'pilot_projection':summary['pilot_projection']}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest='command',required=True)
    r=subs.add_parser('run');r.add_argument('--bank',type=Path,default=Path(__file__).with_name('study-midgame-cpu222-v1.json'));r.add_argument('--split',choices=['pilot','main'],default='main');r.add_argument('--output',type=Path,required=True)
    subs.add_parser('model-worker');args=parser.parse_args()
    if args.command=='model-worker':model_worker()
    else:run(args.bank,args.split,args.output)

if __name__=='__main__':main()
