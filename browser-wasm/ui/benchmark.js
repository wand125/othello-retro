// SPDX-License-Identifier: MIT
'use strict';
(()=>{
 const $=id=>document.getElementById(id);let worker=null,cancel=false,report=null;
 const digest=async raw=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(b=>b.toString(16).padStart(2,'0')).join('');
 function trial(fixture,engine){return new Promise(resolve=>{
  const started=performance.now(),progress=[],active=new Worker(new URL('solver-worker.js',location.href));worker=active;
  let done=false;function finish(result){if(done)return;done=true;clearTimeout(timer);active.terminate();if(worker===active)worker=null;
   const seconds=(performance.now()-started)/1000;let verified=false;
   if(result.status==='found'){try{RetroRules.verify(result.moves,fixture.board);verified=true;}catch{result={status:'error',reason:'independent_verification_failed'};}}
   if((fixture.expected==='reachable'&&result.status==='unreachable')||(fixture.expected==='unreachable'&&result.status==='found'))
    result={status:'error',reason:'unexpected_reachability_verdict',original_result:result};
   resolve({id:fixture.id,board:fixture.board,expected:fixture.expected,engine,observed_seconds:seconds,independently_verified:verified,progress,result});}
  const timer=setTimeout(()=>finish({status:'unknown',observational_deadline:true}),60000);
  active.onmessage=e=>{if(e.data.type==='progress')progress.push({at_seconds:(performance.now()-started)/1000,...e.data});else if(e.data.type==='result')finish(e.data);};
  active.onerror=()=>finish({status:'error',reason:'worker_error'});
  active.onmessageerror=()=>finish({status:'error',reason:'worker_message_error'});
  active.cancel=()=>finish({status:'cancelled'});active.postMessage({type:'solve',board:fixture.board,engine});
 });}
 $('stop').onclick=()=>{cancel=true;worker?.cancel();};
 $('run').onclick=async()=>{
  cancel=false;$('run').disabled=true;$('stop').disabled=false;$('save').disabled=true;$('results').replaceChildren();
  try{
   const response=await fetch('benchmark-cases.json');if(!response.ok)throw Error('cases unavailable');const raw=await response.arrayBuffer(),data=JSON.parse(new TextDecoder().decode(raw));
   const engine=$('engine').value,suite=$('suite').value;let cases=data.cases;
   if(suite==='midgame')cases=cases.slice(0,20);if(suite==='endgame')cases=cases.slice(20);
   if(suite==='quick')cases=cases.slice(0,20).filter((_,i)=>i%4===0);
   let manifest=null;try{manifest=await(await fetch('asset-manifest.json',{cache:'no-store'})).json();}catch{}
   report={schema_version:1,started_utc:new Date().toISOString(),purpose:'Actual user-device fresh-Worker observation, no result cache; not a reachability verdict on expiration',engine,suite,
    user_agent:navigator.userAgent,hardware_concurrency:navigator.hardwareConcurrency,device_memory_gb:navigator.deviceMemory??null,
    cross_origin_isolated:crossOriginIsolated,case_source_sha256:await digest(raw),asset_version:manifest?.version??null,
    assets_sha256:manifest?.files_sha256??null,observational_deadline_seconds:60,results:[]};
   for(const [i,fixture]of cases.entries()){
    if(cancel)break;$('progress').textContent=`${i+1} / ${cases.length}：${fixture.stones}石を計算中`;
    const row=await trial(fixture,engine);report.results.push(row);$('save').disabled=false;
    const tr=document.createElement('tr');for(const text of [row.id,row.result.status,row.observed_seconds.toFixed(3),row.result.stats?.solved_by??'']){const td=document.createElement('td');td.textContent=text;tr.append(td);}$('results').append(tr);
   }
   report.finished_utc=new Date().toISOString();report.interrupted=cancel;
   const found=report.results.filter(r=>r.independently_verified).length;$('progress').textContent=`${report.results.length}件を観測、${found}件の棋譜を検証しました。${cancel?'中断しました。':''}`;
  }catch(error){$('progress').textContent='測定を完了できませんでした。'+error.message;}
  finally{$('run').disabled=false;$('stop').disabled=true;}
 };
 $('save').onclick=()=>{if(!report)return;const link=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)+'\n'],{type:'application/json'}));link.href=url;link.download='othello-retro-device-benchmark.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
})();
