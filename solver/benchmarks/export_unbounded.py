"""Export verified benchmark data only; never expose code, process registry or local paths."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import datetime as dt

PRIVATE_KEYS={'gate_directory','gate_dir','real_kissat','model_python','python_executable','executable','root','cwd','working_directory','command','args','env','controller_pid','pid','pgid','processes','groups'}
LOCAL_PATH=re.compile(r'/(?:Users|home|root|private|var|tmp|opt|srv|mnt|Volumes|Applications|Library|usr|etc|bin|sbin|run)/|[A-Za-z]:[\\/]|~[\\/]')
ROW_FIELDS=('trial_index','case','repeat','method','first_method','stones','stratum','seed','status','success','verified','invalid_or_wrong','moves','wall_seconds','interrupted_work_seconds','effective_wall_seconds','global_deadline','final_sat_time_limit','guided_diagnostic','guided_candidate_rejected','fallback_observed','host_before','host_after')

def sha(raw):return hashlib.sha256(raw).hexdigest()
def digest(obj):return sha(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def load(path):
    raw=path.read_bytes();return json.loads(raw),raw

def sanitize(value):
    if isinstance(value,dict):
        return {k:sanitize(v) for k,v in value.items() if k not in PRIVATE_KEYS and not k.startswith('_') and not k.startswith('/') and not (isinstance(v,str) and LOCAL_PATH.search(v))}
    if isinstance(value,list):return [sanitize(v) for v in value if not (isinstance(v,str) and LOCAL_PATH.search(v))]
    if isinstance(value,str) and LOCAL_PATH.search(value):return '[local path omitted]'
    return value

def replay(moves,target):
    if not isinstance(target,str) or not re.fullmatch('[XO-]{64}',target):raise ValueError('invalid target')
    board=list('---------------------------OX------XO---------------------------');side='X'
    def flips(square,color):
        if board[square]!='-':return []
        r0,c0=divmod(square,8);other='O' if color=='X' else 'X';result=[]
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                if dr==dc==0:continue
                line=[];r,c=r0+dr,c0+dc
                while 0<=r<8 and 0<=c<8 and board[r*8+c]==other:line.append(r*8+c);r+=dr;c+=dc
                if line and 0<=r<8 and 0<=c<8 and board[r*8+c]==color:result.extend(line)
        return result
    def can(color):return any(flips(s,color) for s in range(64))
    if not isinstance(moves,list):raise ValueError('invalid moves')
    for move in moves:
        other='O' if side=='X' else 'X'
        if move=='pass':
            if can(side) or not can(other):raise ValueError('illegal pass')
            side=other;continue
        if not isinstance(move,str) or not re.fullmatch('[a-h][1-8]',move):raise ValueError('invalid move')
        square=(int(move[1])-1)*8+'abcdefgh'.index(move[0]);changed=flips(square,side)
        if not changed:
            if can(side) or not can(other):raise ValueError('illegal turn/color switch')
            side=other;other='O' if side=='X' else 'X';changed=flips(square,side)
        if not changed:raise ValueError('illegal placement')
        for s in [square,*changed]:board[s]=side
        side=other
    if ''.join(board)!=target:raise ValueError('target mismatch')
    return not can('X') and not can('O')

def export(source,bankpath,output,split=None):
    if source.resolve()==output.resolve():raise ValueError('public output must differ from private input')
    bank,bankraw=load(bankpath);meta,metaraw=load(source/'metadata.json')
    if digest(bank['protocol'])!=bank['protocol_sha256']:raise ValueError('bank protocol hash mismatch')
    if meta['bank_sha256']!=sha(bankraw) or meta['protocol_sha256']!=bank['protocol_sha256']:raise ValueError('run/bank hash mismatch')
    if 'protocol' in meta and digest(meta['protocol'])!=bank['protocol_sha256']:raise ValueError('metadata protocol content mismatch')
    split=split or meta['split'];section=bank['splits'][split];schedule=section['schedule'];cases={c['id']:c for c in section['cases']}
    if digest(section['cases'])!=section['cases_sha256'] or digest(schedule)!=section['schedule_sha256']:raise ValueError('case/order hash mismatch')
    if meta['cases_sha256']!=section['cases_sha256'] or meta['schedule_sha256']!=section['schedule_sha256']:raise ValueError('metadata case/order mismatch')
    for case in cases.values():
        if replay(case['reference_moves'],case['board']) is not case['terminal']:raise ValueError('reference terminal mismatch')
    raw=(source/'runs.jsonl').read_bytes() if (source/'runs.jsonl').exists() else b'';rows=[];prefix_bytes=0;trailing=False
    for line in raw.splitlines(keepends=True):
        if not line.endswith(b'\n'):trailing=True;break
        row=json.loads(line)
        if len(rows)>=len(schedule):raise ValueError('extra trial')
        expected=schedule[len(rows)]
        if any(row[k]!=expected[k] for k in ('case','repeat','method')) or row['trial_index']!=len(rows):raise ValueError('trial order/identity mismatch')
        if row['status']!='found' or row['verified'] is not True or row.get('invalid_or_wrong'):raise ValueError('unverified completed trial')
        if row.get('global_deadline') is not None or row.get('final_sat_time_limit') is not None:raise ValueError('finite result mixed into unbounded data')
        for field in ('wall_seconds','effective_wall_seconds','interrupted_work_seconds'):
            value=row[field]
            if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<0:raise ValueError('invalid timing')
        if abs(row['effective_wall_seconds']-row['wall_seconds']-row['interrupted_work_seconds'])>1e-6:raise ValueError('effective timing sum mismatch')
        if replay(row['moves'],cases[row['case']]['board']) is not cases[row['case']]['terminal']:raise ValueError('computed record terminal mismatch')
        rows.append(sanitize({k:row[k] for k in ROW_FIELDS if k in row}));prefix_bytes+=len(line)
    full=len(rows)==len(schedule);summary_path=source/'summary.json';summary=None;summary_raw=None
    source_state=meta.get('status','unknown')
    if full and source_state=='complete' and not trailing:
        if summary_path.exists():
            summary,summary_raw=load(summary_path)
            if summary['metadata']['bank_sha256']!=meta['bank_sha256'] or summary['metadata'].get('completed_trials')!=len(rows):raise ValueError('summary source mismatch')
            state='complete'
        else:state='complete_pending_analysis'
    else:state='incomplete'
    public_meta=sanitize(meta)
    public_meta['publication_state']=state;public_meta['source_state']=source_state;public_meta['snapshot_completed_trials']=len(rows);public_meta['completed_trials']=len(rows);public_meta['planned_trials']=len(schedule)
    if state!='complete':public_meta['status']='incomplete'
    output.mkdir(parents=True,exist_ok=True)
    def put(name,value):
        tmp=output/(name+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(output/name)
    put('metadata.json',public_meta)
    rowtext=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows);(output/'runs.jsonl').write_text(rowtext)
    if summary is not None:
        summary=sanitize(summary);summary['metadata']=public_meta
        put('summary.json',summary)
    elif (output/'summary.json').exists():(output/'summary.json').unlink()
    auxiliary=[]
    for name in ['preparation.jsonl','resource-pauses.jsonl']:
        path=source/name
        if path.exists():
            selected=[]
            for line in path.read_bytes().splitlines(keepends=True):
                if not line.endswith(b'\n'):break
                selected.append(sanitize(json.loads(line)))
            (output/name).write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in selected))
            auxiliary.append(name)
    if 'resource-pauses.jsonl' in auxiliary:
        public_meta['program_wall_comparison_note']='Whole-program wall includes logged between-trial resource pauses. Compare per-trial solver cost separately.'
        put('metadata.json',public_meta)
        if summary is not None:summary['metadata']=public_meta;put('summary.json',summary)
    verification={'bank_sha256':sha(bankraw),'protocol_sha256':bank['protocol_sha256'],'cases_sha256':section['cases_sha256'],'schedule_sha256':section['schedule_sha256'],
      'completed_prefix_trials':len(rows),'planned_trials':len(schedule),'independent_input_cases':len(cases),'computed_records_independently_replayed':len(rows),
      'reference_records_independently_replayed':len(cases),'trial_order_and_uniqueness':'passed','strict_legal_replay_and_target':'passed','finite_cutoff_mix_check':'passed',
      'trailing_incomplete_line_omitted':trailing,'source_metadata_count_at_snapshot':meta.get('completed_trials',0),'snapshot_is_complete':state=='complete',
      'privacy':'absolute local paths, gate namespace and private process/control data omitted; implementation/models/stderr not exported',
      'private_source_sha256':{'metadata.json':sha(metaraw),'runs.jsonl_completed_prefix':sha(raw[:prefix_bytes]),**({'summary.json':sha(summary_raw)} if summary_raw is not None else {})}}
    put('verification.json',verification)
    files=['metadata.json','runs.jsonl','verification.json']+auxiliary+(['summary.json'] if summary is not None else [])
    manifest={'exported_at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':state,'split':split,'dataset_role':'coherence_pilot' if split=='pilot' else 'formal_main','completed_formal_dataset':state=='complete' and split=='main','cross_environment_comparison_ready':False,'cross_environment_readiness_note':'Not assessed by a single-environment export. Four-environment coverage/completeness and comparability are evaluated separately; do not infer a machine ranking from this flag.','completed_trials':len(rows),'planned_trials':len(schedule),
      'complete_data_only':state=='complete','comparison_note':'Incomplete snapshots are progress data and must not be ranked or pooled with completed benchmark sets.',
      'files_sha256':{name:sha((output/name).read_bytes()) for name in files}}
    put('manifest.json',manifest)
    for name in files:
        data=(output/name).read_text()
        if LOCAL_PATH.search(data):raise ValueError('local path remains in public export: '+name)
    if summary is not None and json.loads((output/'summary.json').read_text())['metadata']!=json.loads((output/'metadata.json').read_text()):raise ValueError('summary metadata sanitize inconsistency')
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--bank',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--split',choices=['pilot','main']);a=p.parse_args()
    print(json.dumps(export(a.input,a.bank,a.output,a.split)),flush=True)
if __name__=='__main__':main()
