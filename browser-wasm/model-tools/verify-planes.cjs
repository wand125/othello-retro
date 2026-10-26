// SPDX-License-Identifier: MIT
// Copyright (c) 2026 wand125 and contributors.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const args=process.argv.slice(2);
function option(name,fallback){const index=args.indexOf(name);return index<0?fallback:args[index+1];}
const fixturePath=path.resolve(option('--fixtures',path.join(__dirname,'numeric-fixtures.json')));
const autoPath=path.resolve(option('--auto-js',path.join(__dirname,'../ui/auto.js')));
const auto=require(autoPath),fixtures=JSON.parse(fs.readFileSync(fixturePath));
let batches=0,candidates=0,floats=0;
for(const batch of fixtures.batches){
 if(!batch.items)continue;
 const items=batch.items.map(item=>({words:item.child_words,next:item.mover,square:item.removed_square,parent:{words:item.parent_words}}));
 const actual=auto.planes(items),expected=Float32Array.from(batch.input);
 assert.equal(actual.length,batch.shape.reduce((a,b)=>a*b,1));
 assert.deepEqual(new Uint8Array(actual.buffer,actual.byteOffset,actual.byteLength),new Uint8Array(expected.buffer),batch.id);
 batches++;candidates+=items.length;floats+=actual.length;
}
assert.equal(batches,4);assert.equal(candidates,146);
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const report={status:'passed',scope:'JS5-plane features match original PyTorch training/search feature arrays byte-for-byte on genuine legal reference reverse edges; no inference/search launched.',legal_batches:batches,candidates,floats_compared:floats,fixtures_sha256:sha(fixturePath),tested_auto_js_sha256:sha(autoPath)};
const output=option('--output');if(output){if(fs.existsSync(output))throw Error('--output already exists');fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify(report));
