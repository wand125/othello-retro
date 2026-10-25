// SPDX-License-Identifier: MIT
// Correctness acceptance, not a fixed-condition performance benchmark.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const {Worker,isMainThread,parentPort,workerData} = require('node:worker_threads');
const root = path.resolve(__dirname,'..');
const cases = JSON.parse(fs.readFileSync(path.join(__dirname,'cases.json'))).cases;

async function single(fixture) {
  const createKissat = require(path.join(root,'ui/kissat.js'));
  const glue = require(path.join(root,'ui/engine.js'));
  const rules = require(path.join(root,'ui/verify.js'));
  const bytes = fs.readFileSync(path.join(root,'ui/encoder.wasm'));
  assert.deepEqual(WebAssembly.Module.imports(new WebAssembly.Module(bytes)),[]);
  const {instance} = await WebAssembly.instantiate(bytes,{});
  const sat = await createKissat({wasmBinary:fs.readFileSync(path.join(root,'ui/kissat.wasm')),print:()=>{},printErr:()=>{}});
  const stages = [];
  const result = glue.solve(fixture.board,instance.exports,sat,rules,event=>stages.push(event.stage));
  if(result.status==='found') rules.verify(result.moves,fixture.board);
  return {id:fixture.id,expected:fixture.expected,...result,stages};
}
if(!isMainThread) {
  single(workerData).then(result=>parentPort.postMessage(result)).catch(error=>parentPort.postMessage({id:workerData.id,status:'error',reason:error.stack}));
} else {
  (async()=>{
    const smoke=process.argv.includes('--smoke');
    const stress=process.argv.includes('--stress');
    const onlyIndex=process.argv.indexOf('--only');
    const only=onlyIndex<0?null:new Set(process.argv[onlyIndex+1].split(','));
    const selected=cases.filter(c=>(stress||c.id!=='paper-deep-root-61')&&(!smoke||['initial','one-move','main-n12-s202610250000000','missing-center','paper-two-placement-unreachable'].includes(c.id))&&(!only||only.has(c.id)));
    assert(selected.length>0,'no selected fixtures');
    const results=[];
    const source_sha256 = Object.fromEntries(['ui/encoder.wasm','ui/kissat.wasm','ui/kissat.js','ui/engine.js','ui/verify.js','tests/cases.json','tests/test-solver.cjs'].map(name=>[name,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,name))).digest('hex')]));
    for(const fixture of selected) {
      const result=await new Promise((resolve,reject)=>{
        const worker=new Worker(__filename,{workerData:fixture});
        const deadline=Number(process.env.WASM_TEST_TIMEOUT_MS||180000);
        const timer=setTimeout(async()=>{
          await worker.terminate();
          resolve({id:fixture.id,expected:fixture.expected,status:'observational_deadline',observed_limit_ms:deadline,reason:'No reachability verdict; worker terminated by acceptance watchdog.'});
        },deadline);
        worker.once('message',async message=>{clearTimeout(timer);await worker.terminate();resolve(message);});
        worker.once('error',error=>{clearTimeout(timer);reject(error);});
      });
      results.push(result);
      console.log(JSON.stringify({id:result.id,status:result.status,seconds:result.wall_seconds,solved_by:result.stats?.solved_by}));
    }
    const failures=results.filter(r=>r.status!==(r.expected==='reachable'?'found':'unreachable'));
    const validation=path.join(root,'validation');fs.mkdirSync(validation,{recursive:true});
    const report={status:failures.length?'incomplete_or_failed':'passed',runtime:process.version,purpose:'Correctness acceptance; independent replay of every found witness',source_sha256,watchdog_is_not_unreachable:true,results};
    const name=stress?'solver-stress.json':smoke?'solver-smoke.json':only?'solver-selected.json':'solver-acceptance.json';
    fs.writeFileSync(path.join(validation,name),JSON.stringify(report,null,2)+'\n');
    if(failures.length)process.exitCode=1;
  })().catch(error=>{console.error(error);process.exitCode=1;});
}
