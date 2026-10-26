// SPDX-License-Identifier: MIT
// Cross-language regression fixtures come from independently replayed legal games.
'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const engine=require('../ui/engine.js'),auto=require('../ui/auto.js');
const root=path.resolve(__dirname,'..');
const fixtures=JSON.parse(fs.readFileSync(path.join(root,'model-tools/numeric-fixtures.json')));
const edges=JSON.parse(fs.readFileSync(path.join(root,'model-tools/legal-edge-items.json'))).items;
let encoder;
async function wasm(){if(!encoder)encoder=(await WebAssembly.instantiate(fs.readFileSync(path.join(root,'ui/encoder.wasm')),{})).instance.exports;return encoder;}
for(const fixture of fixtures.batches.filter(b=>b.items)){
 test('five input planes match original Python exactly: '+fixture.id,()=>{
  const items=fixture.items.map(i=>({words:i.child_words,next:i.mover,parent:{words:i.parent_words}}));
  const actual=auto.planes(items);
  assert.deepEqual(actual,new Float32Array(fixture.input));
 });
}
test('WASM predecessor enumeration retains all 179 actual legal reference edges, including forced passes',async()=>{
 const enc=await wasm();let count=0;
 for(const edge of edges){
  const parent={words:edge.parent_words,next:3,tail:[]};
  const kids=auto.children(parent,enc,true);
  assert(kids.some(k=>k.words.every((v,i)=>v===edge.child_words[i])&&k.next===edge.mover&&k.square===edge.removed_square),edge.source_case+' '+edge.normalized_move_index);
  count++;
 }
 assert.equal(count,179);
});
test('ML loading failure returns to complete SAT, never to a model reachability verdict',async()=>{
 const original=global.RetroEngine;const calls=[];
 const board='X'.repeat(36)+'-'.repeat(28);
 const enc={undo_board:()=>1,undos_ptr:()=>0,undo_scores_ptr:()=>24,free_undos:()=>{},memory:{buffer:new ArrayBuffer(28)}};
 new Uint32Array(enc.memory.buffer).set([1,0,2,0,1,3,0]);
 global.RetroEngine={boardWords:engine.boardWords,POLICY:engine.POLICY,
  createSearch:()=>({attempt:mode=>{calls.push(mode);return {status:'unknown',stats:{phase:mode===3?'full':'probe'}};},
    finish:(r,extra)=>({...r,stats:{...r.stats,...extra}})}),
  solve:()=>{throw Error('must not repeat a completed probe');}};
 try{
  const result=await auto.solve(board,enc,{}, {},{score:()=>Promise.reject(Error('model unavailable'))});
  assert.equal(result.status,'unknown');assert.deepEqual(calls,[1,3]);
  assert.equal(result.stats.guidance.hit,false);
  assert.equal(result.stats.guidance.miss_reason,'model_or_guidance_error');
 }finally{global.RetroEngine=original;}
});
test('all board/word conversions preserve exactly the 64 goal cells',()=>{
 for(const edge of edges){assert.equal(auto.wordsBoard(engine.boardWords(edge.parent_board)),edge.parent_board);}
});
