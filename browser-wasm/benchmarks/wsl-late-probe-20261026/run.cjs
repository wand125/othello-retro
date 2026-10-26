// SPDX-License-Identifier: MIT
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {Worker,isMainThread,parentPort,workerData}=require('node:worker_threads');
const ROOT=__dirname;
const UI=path.resolve(ROOT,'../../ui');
const ENCODER=process.env.RETRO_ENCODER_WASM||path.join(ROOT,'artifacts/encoder.wasm');
async function single(job){
 const start=performance.now(),caseData=JSON.parse(fs.readFileSync(ROOT+'/cases.json')).cases.find(c=>c.id===job.case);
 if(!caseData)throw Error('unknown case');
 const rules=require(UI+'/verify.js'),glue=require(ROOT+'/measured-engine.js');
 const {instance}=await WebAssembly.instantiate(fs.readFileSync(ENCODER),{});const e=instance.exports;
 const factory=require(UI+'/kissat.js'),sat=await factory({wasmBinary:fs.readFileSync(UI+'/kissat.wasm'),print:()=>{},printErr:()=>{}});
 const loaded=performance.now(),stats={...job,load_seconds:(loaded-start)/1000};let s=0,buf=0;
 function progress(phase){parentPort.postMessage({event:'progress',phase,stats:{...stats},elapsed_seconds:(performance.now()-start)/1000});}
 try{
  progress('encoding');const t0=performance.now();const code=e.encode_board(...glue.boardWords(caseData.board),job.mode);
  if(code!==0)return {status:code===1?'preprocess_rejection':'error',stats};
  const placements=new Int32Array(e.memory.buffer,e.placements_ptr(),e.placements_len()).slice(),truth=e.true_literal();
  Object.assign(stats,{encoding_seconds:(performance.now()-t0)/1000,variables:e.variables(),clauses:e.clauses(),steps:e.steps(),literal_count:e.literals_len(),encoder_heap_bytes:e.memory.buffer.byteLength});
  s=sat._kissat_init();sat._kissat_reserve(s,stats.variables);
  function option(name,value){const b=Buffer.from(name+'\0'),p=sat._malloc(b.length);new Uint8Array(sat.HEAP32.buffer).set(b,p);sat._kissat_set_option(s,p,value);const observed=sat._kissat_get_option(s,p);sat._free(p);if(observed!==value)throw Error('option rejected: '+name);}
  if(job.sat_preset){option('target',2);option('restartint',50);}
  if(job.options)for(const [k,v] of Object.entries(job.options))option(k,v);
  const copyStart=performance.now(),lits=new Int32Array(e.memory.buffer,e.literals_ptr(),e.literals_len());buf=sat._malloc(Math.max(4,lits.byteLength));sat.HEAP32.set(lits,buf>>>2);sat._kissat_add_buffer(s,buf,lits.length);sat._free(buf);buf=0;e.free_encoding();stats.copy_add_seconds=(performance.now()-copyStart)/1000;
  if(job.conflicts)sat._kissat_set_conflict_limit(s,job.conflicts);if(job.decisions)sat._kissat_set_decision_limit(s,job.decisions);
  progress('solving');const ts=performance.now(),result=sat._kissat_solve(s);stats.solver_seconds=(performance.now()-ts)/1000;stats.solver_result=result;stats.solver_heap_bytes=sat.HEAP32.buffer.byteLength;
  if(result!==10)return {status:result===20?(job.mode===0||job.mode===3?'unreachable':'restricted_unsat'):'unknown',stats};
  const moves=[];for(let step=0;step<stats.steps;step++){let selected=-1;for(let q=0;q<64;q++){const l=placements[step*64+q],v=l===truth?true:l===-truth?false:sat._kissat_value(s,l)>0;if(v){if(selected>=0)throw Error('duplicate placement');selected=q;}}if(selected<0)throw Error('missing placement');moves.push('abcdefgh'[selected%8]+String((selected/8|0)+1));}
  const verified=rules.verify(moves,caseData.board);return {status:'found',moves:verified.moves,terminal:verified.terminal,independent_replay:true,stats};
 }finally{if(buf)sat._free(buf);if(s)sat._kissat_release(s);e.free_encoding();stats.total_seconds=(performance.now()-start)/1000;}
}
if(!isMainThread){single(workerData).then(x=>parentPort.postMessage({event:'result',result:x})).catch(e=>parentPort.postMessage({event:'result',result:{status:'error',reason:e.stack}}));}
else (async()=>{
 const argv=process.argv.slice(2),idx=argv.indexOf('--output');
 if(idx<0||!argv[idx+1])throw Error('Usage: node run.cjs --output NEW_DIRECTORY [--allow-artifact-change]');
 const directory=path.resolve(argv[idx+1]);
 if(fs.existsSync(directory))throw Error('Output directory must not already exist');
 const expected=JSON.parse(fs.readFileSync(path.join(ROOT,'measurement-inputs.json')));
 const actualFiles={'encoder.wasm':ENCODER,'kissat.js':UI+'/kissat.js','kissat.wasm':UI+'/kissat.wasm','verify.js':UI+'/verify.js'};
 const mismatches=Object.entries(actualFiles).filter(([name,file])=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')!==expected.artifact_sha256[name]);
 if(mismatches.length&&!argv.includes('--allow-artifact-change'))throw Error('Artifact mismatch: '+mismatches.map(x=>x[0]).join(', ')+'; rebuild measured inputs or explicitly use --allow-artifact-change');
 fs.mkdirSync(directory,{recursive:true});
 const plan=JSON.parse(fs.readFileSync(path.join(ROOT,'plan.json'))),out=path.join(directory,'results');
 fs.writeFileSync(path.join(directory,'input-conditions.json'),JSON.stringify({artifact_hashes_match_measured:mismatches.length===0,artifact_change_explicitly_allowed:argv.includes('--allow-artifact-change'),limits_are_work_units:true,watchdog_is_not_unreachable:true},null,2));
 const hash=f=>crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
 fs.writeFileSync(out+'.meta.json',JSON.stringify({runtime:process.version,platform:process.platform,arch:process.arch,nice:19,scope:'exploratory selected fixtures; desktop Node, not smartphone latency guarantee',watchdog_verdict:'unknown, never unreachable',files:Object.fromEntries([ENCODER,UI+'/kissat.js',UI+'/kissat.wasm',UI+'/verify.js',__filename].map(f=>[path.basename(f),hash(f)])),plan},null,2));
 for(const job of plan){let latest=null;const result=await new Promise((resolve,reject)=>{const w=new Worker(__filename,{workerData:job});const begun=performance.now();const timer=setTimeout(async()=>{await w.terminate();resolve({status:'observation_deadline_unknown',watchdog_seconds:job.observe_ms/1000,last_progress:latest,observed_wall_seconds:(performance.now()-begun)/1000});},job.observe_ms);w.on('message',async m=>{if(m.event==='progress'){latest=m;return;}clearTimeout(timer);await w.terminate();resolve(m.result);});w.once('error',e=>{clearTimeout(timer);reject(e);});});
 const row={job,...result};fs.appendFileSync(out+'.jsonl',JSON.stringify(row)+'\n');console.log(JSON.stringify({name:job.name,case:job.case,status:row.status,seconds:row.stats?.total_seconds,solver_seconds:row.stats?.solver_seconds,last_phase:row.last_progress?.phase}));
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
