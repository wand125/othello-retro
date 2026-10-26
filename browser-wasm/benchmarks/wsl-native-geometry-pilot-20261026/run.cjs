// SPDX-License-Identifier: MIT
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),{pathToFileURL}=require('node:url');
const {Worker,isMainThread,parentPort,workerData}=require('node:worker_threads');
const ROOT=__dirname,UI=path.resolve(process.env.RETRO_BROWSER_UI||path.join(ROOT,'../../ui'));
const prototype=()=>process.env.RETRO_GEOMETRY_PROTOTYPE;
function safeError(error){let text=String(error?.message||error);for(const [value,label]of [[UI,'[UI]'],[ROOT,'[DIAG]'],[prototype()?path.dirname(prototype()):null,'[OUTPUT]']])if(value)text=text.split(value).join(label);return text;}
async function single(job){
 const begun=performance.now(),c=JSON.parse(fs.readFileSync(ROOT+'/cases.json')).cases.find(c=>c.id===job.case);
 const rules=require(UI+'/verify.js');require(UI+'/engine.js');const auto=require(job.variant==='A'?UI+'/auto.js':prototype());
 globalThis.RetroInferenceConfig={baseURL:pathToFileURL(UI+'/inference/').href,modelURLs:{standard:pathToFileURL(UI+'/models/model.fused.onnx').href,passes:pathToFileURL(UI+'/models/model_passes.fused.onnx').href}};
 const infer=require(UI+'/inference/infer.js');
 const metrics={cnn_calls_attempted:0,cnn_calls_completed:0,cnn_items_attempted:0,cnn_items_completed:0,cnn_seconds:0,cnn_failures:0};let lastStage='loading';
 const publish=event=>parentPort.postMessage({event:'progress',progress:{...event,metrics:{...metrics}},elapsed_seconds:(performance.now()-begun)/1000});
 const inference={score:async(input,count,passes)=>{metrics.cnn_calls_attempted++;metrics.cnn_items_attempted+=count;publish({stage:lastStage,phase:'cnn_started',batch:count});const start=performance.now();try{const r=await infer.score(input,count,passes);metrics.cnn_calls_completed++;metrics.cnn_items_completed+=count;return r;}catch(e){metrics.cnn_failures++;throw e;}finally{metrics.cnn_seconds+=(performance.now()-start)/1000;publish({stage:lastStage,phase:'cnn_completed',batch:count});}}};
 const {instance}=await WebAssembly.instantiate(fs.readFileSync(UI+'/encoder.wasm'),{});const factory=require(UI+'/kissat.js');const sat=await factory({wasmBinary:fs.readFileSync(UI+'/kissat.wasm'),print:()=>{},printErr:()=>{}});
 const result=await auto.solve(c.board,instance.exports,sat,rules,inference,event=>{lastStage=event.stage;publish(event)});
 if(result.status==='found')rules.verify(result.moves,c.board);
 return {...result,metrics,inference_stats:infer.getStats(),independent_replay:result.status==='found',whole_worker_seconds:(performance.now()-begun)/1000};
}
if(!isMainThread)single(workerData).then(result=>parentPort.postMessage({event:'result',result})).catch(e=>parentPort.postMessage({event:'result',result:{status:'error',reason:safeError(e)}}));
else(async()=>{
 const plan=JSON.parse(fs.readFileSync(ROOT+'/plan.json')),hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
 const args=process.argv.slice(2),position=args.indexOf('--output');
 if(position<0||!args[position+1])throw Error('Usage: RETRO_BROWSER_UI=UI_DIRECTORY node run.cjs --output NEW_DIRECTORY [--allow-artifact-change]');
 const output=path.resolve(args[position+1]);if(fs.existsSync(output))throw Error('Output directory must not already exist');
 const expected=JSON.parse(fs.readFileSync(ROOT+'/conditions.json')).source_sha256;
 const inputFile=name=>name.startsWith('ui/')?path.join(UI,name.slice(3)):path.join(ROOT,name);
 const names=Object.keys(expected).filter(name=>name!=='ui/auto-native-geometry.js'&&name!=='run.cjs');
 const manifest=Object.fromEntries(names.map(name=>[name,hash(inputFile(name))]));
 const changes=names.filter(name=>manifest[name]!==expected[name]);
 if(changes.length&&!args.includes('--allow-artifact-change'))throw Error('Measured input mismatch: '+changes.join(', ')+'; use matching inputs or explicitly record --allow-artifact-change');
 fs.mkdirSync(output,{recursive:true});
 const nativePath=path.join(output,'auto-native-geometry.js');fs.copyFileSync(UI+'/auto.js',nativePath);
 require('node:child_process').execFileSync('patch',[nativePath,ROOT+'/native-geometry.patch'],{stdio:'pipe'});
 const nativeHash=hash(nativePath);if(nativeHash!==expected['ui/auto-native-geometry.js']&&!args.includes('--allow-artifact-change'))throw Error('Patched B differs from measured prototype');
 process.env.RETRO_GEOMETRY_PROTOTYPE=nativePath;manifest['ui/auto-native-geometry.js']=nativeHash;
 fs.writeFileSync(output+'/input-check.json',JSON.stringify({artifact_hashes_match_measured:changes.length===0&&nativeHash===expected['ui/auto-native-geometry.js'],changed_inputs:changes,allow_artifact_change:args.includes('--allow-artifact-change'),published_runner_is_IO_port_only:true},null,2));
 const meta={started_at:new Date().toISOString(),node:process.version,platform:process.platform,arch:process.arch,source_sha256:{...manifest,'run.cjs':hash(__filename)},nice:require('node:os').getPriority(),affinity:fs.existsSync('/proc/self/status')?fs.readFileSync('/proc/self/status','utf8').split('\n').find(l=>l.startsWith('Cpus_allowed_list:')):null,model_backend:'ONNX Runtime WASM CPU FP32 one thread',policy_budget_note:'B guided_budget_seconds null in JSON means disabled; Infinity in code',plan,status:'running'};fs.writeFileSync(output+'/metadata.json',JSON.stringify(meta,null,2));
 for(const job of plan){const available=fs.existsSync('/proc/meminfo')?Number(fs.readFileSync('/proc/meminfo','utf8').match(/MemAvailable:\s+(\d+)/)[1]):Infinity;if(available<6*1024*1024)throw Error('MemAvailable below6GiB; own experiment stopped');const begun=performance.now();let latest=null;const progress=[];
  const row=await new Promise((resolve,reject)=>{const w=new Worker(__filename,{workerData:job}),timer=setTimeout(async()=>{await w.terminate();resolve({status:'observation_deadline_unknown',observational_deadline:true,observed_seconds:(performance.now()-begun)/1000,last_progress:latest,metrics:latest?.progress?.metrics??null,progress});},job.observation_ms);w.on('message',async m=>{if(m.event==='progress'){latest=m;progress.push(m);return;}clearTimeout(timer);await w.terminate();resolve({...m.result,observed_seconds:(performance.now()-begun)/1000,progress});});w.once('error',e=>{clearTimeout(timer);reject(e)});});
  fs.appendFileSync(output+'/results.jsonl',JSON.stringify({job,...row})+'\n');console.log(JSON.stringify({case:job.case,variant:job.variant,status:row.status,seconds:row.observed_seconds,solved_by:row.stats?.solved_by,last_stage:row.last_progress?.progress?.stage,metrics:row.metrics}));
 }
 meta.status='complete';meta.finished_at=new Date().toISOString();meta.source_hashes_unchanged=Object.entries(meta.source_sha256).every(([f,h])=>hash(f==='run.cjs'?__filename:f==='ui/auto-native-geometry.js'?nativePath:inputFile(f))===h);fs.writeFileSync(output+'/metadata.json',JSON.stringify(meta,null,2));
})().catch(e=>{console.error(safeError(e));process.exitCode=1});
