"""Privacy, completed/incomplete separation and illegal-turn export regression."""
import json
from pathlib import Path
import tempfile
import export_unbounded as e
with tempfile.TemporaryDirectory(prefix='retro-export-test-') as td:
    d=Path(td);source=d/'private';source.mkdir();public=d/'public'
    b=list('---------------------------OX------XO---------------------------')
    for square in [19,27]:b[square]='X'
    for square in [18,27]:b[square]='O'
    case={'id':'fixture','board':''.join(b),'reference_moves':['d3','c3'],'terminal':False}
    order=[{'case':'fixture','repeat':1,'method':'sat'}]
    bank={'protocol':{'id':'control-fixture'},'splits':{'pilot':{'cases':[case],'schedule':order,'cases_sha256':e.digest([case]),'schedule_sha256':e.digest(order)}}};bank['protocol_sha256']=e.digest(bank['protocol']);bankpath=d/'bank.json';bankpath.write_text(json.dumps(bank))
    meta={'bank_sha256':e.sha(bankpath.read_bytes()),'protocol_sha256':bank['protocol_sha256'],'cases_sha256':bank['splits']['pilot']['cases_sha256'],'schedule_sha256':e.digest(order),'split':'pilot','status':'complete','completed_trials':1,
      'gate_directory':'/Users/owner/private-lock','nested':{'private_file':'/root/private/foo','keep':'CPU FP32'},'host_descriptor':{'cpu_model':'fixture CPU'}}
    row={'trial_index':0,**order[0],'status':'found','success':1,'verified':True,'invalid_or_wrong':False,'moves':['d3','c3'],'wall_seconds':.1,'interrupted_work_seconds':0,'effective_wall_seconds':.1,'global_deadline':None,'final_sat_time_limit':None,'guided_diagnostic':{'stage':'direct','debug_file':'/Users/private/foo'},'host_before':{'load_average':[1,2,3]},'host_after':{'load_average':[1,2,3]}}
    (source/'metadata.json').write_text(json.dumps(meta));(source/'runs.jsonl').write_text(json.dumps(row)+'\n');(source/'summary.json').write_text(json.dumps({'metadata':meta,'sample':'retained'}));(source/'resource-pauses.jsonl').write_text(json.dumps({'seconds':1,'reason':'resource_diagnostic','private_path':'/root/private'})+'\n')
    result=e.export(source,bankpath,public);assert result['status']=='complete'
    m=json.loads((public/'metadata.json').read_text());s=json.loads((public/'summary.json').read_text());assert m==s['metadata'] and 'gate_directory' not in m
    for file in public.iterdir():
        text=file.read_text();assert '/Users/' not in text and '/root/' not in text
    assert json.loads((public/'runs.jsonl').read_text())['host_before']==row['host_before']
    bad={**row,'moves':['d3','f5']};(source/'runs.jsonl').write_text(json.dumps(bad)+'\n')
    try:e.export(source,bankpath,d/'bad-public');raise AssertionError('illegal turn exported')
    except ValueError:pass
    meta['status']='running';meta['completed_trials']=0;(source/'metadata.json').write_text(json.dumps(meta));(source/'runs.jsonl').write_text('')
    result=e.export(source,bankpath,public);assert result['status']=='incomplete' and not (public/'summary.json').exists()
    assert json.loads((public/'metadata.json').read_text())['status']=='incomplete'
    print(json.dumps({'private_paths_removed':'passed','summary_metadata_identical':'passed','raw_timing_diagnostics_load_retained':'passed','illegal_color_switch_rejected':'passed','incomplete_not_mixed_with_complete':'passed','resource_pause_note_retained':'passed'}))
