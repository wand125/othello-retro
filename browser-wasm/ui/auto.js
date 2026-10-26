// SPDX-License-Identifier: MIT
// Guided search is a heuristic. Only independent replay accepts a witness;
// failure to find one always returns to a complete SAT formula.
(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.RetroAuto = api;
})(globalThis, function (root) {
  'use strict';
  const POLICY = Object.freeze({name:'browser-lightweight-v3', width:8, cap:2, shortlist:128,
    stop_placements:30, symmetry_count:1, refinement:0, batch:128,
    guided_budget_seconds:12, candidate_conflicts:2000, candidate_decisions:20000,
    max_candidates:16, min_stones:36, pass_zone:48});
  const stones = board => [...board].filter(c=>c!=='-').length;
  function wordsBoard(v) {
    let board='';
    for(let i=0;i<64;i++) {
      const j=i>>>5, bit=i&31;
      board += (v[j]>>>bit)&1 ? 'X' : (v[j+2]>>>bit)&1 ? 'O' : '-';
    }
    return board;
  }
  function children(parent, encoder, passes) {
    const count=encoder.undo_board(...parent.words,parent.next,passes?2:3);
    if(count<0) throw Error('invalid undo input');
    const raw=new Uint32Array(encoder.memory.buffer,encoder.undos_ptr(),count*6).slice();
    const heuristic=new Int32Array(encoder.memory.buffer,encoder.undo_scores_ptr(),count).slice();
    encoder.free_undos();
    const result=[];
    for(let i=0;i<count;i++) {
      const offset=i*6, words=Array.from(raw.subarray(offset,offset+4)), next=raw[offset+4], square=raw[offset+5];
      result.push({words,next,square,parent,heuristic:heuristic[i],tail:[square,...parent.tail], key:words.join(',')+':'+next});
    }
    return result;
  }
  function planes(items) {
    const out=new Float32Array(items.length*320);
    items.forEach((item,index)=>{
      const q=item.words,p=item.parent.words,black=item.next===0,base=index*320;
      for(let i=0;i<64;i++) {
        const j=i>>>5,bit=i&31,qb=(q[j]>>>bit)&1,qw=(q[j+2]>>>bit)&1;
        const pb=(p[j]>>>bit)&1,pw=(p[j+2]>>>bit)&1,removed=pb+pw-qb-qw;
        out[base+i]=black?qb:qw; out[base+64+i]=black?qw:qb;
        out[base+128+i]=1-qb-qw; out[base+192+i]=removed;
        out[base+256+i]=Math.max(0,Math.abs(pb-qb)-removed);
      }
    });
    return out;
  }
  async function beam(board,encoder,inference,passes,progress=()=>{},options={}) {
    const policy={...POLICY,...options},started=performance.now();
    const deadline=started+policy.guided_budget_seconds*1000;
    let level=[{words:root.RetroEngine.boardWords(board),next:3,tail:[]}],n=stones(board)-4,evaluated=0;
    const steps=[];
    const check=()=>{if(performance.now()>=deadline) throw Error('guided_budget');};
    while(n>policy.stop_placements) {
      check();const stepStart=performance.now(),seen=new Set(),items=[];
      progress({stage:'guided_generate',remaining_moves:n,evaluated,kept:level.length});
      for(const parent of level) {
        check();
        for(const child of children(parent,encoder,passes)) {
          if(child.next!==(n-1)%2 && n-1<policy.pass_zone)continue;
          if(seen.has(child.key))continue;
          seen.add(child.key);items.push(child);
        }
      }
      if(!items.length)return {candidates:[],evaluated,steps,reason:'empty_frontier'};
      const generated=items.length;
      // A cheap native evaluator screens large frontiers before CNN inference.
      // This is a heuristic restriction, never a reachability verdict.
      items.sort((a,b)=>b.heuristic-a.heuristic);
      if(items.length>policy.shortlist) {
        const per=new Map(),selected=[];
        const parentLimit=Math.max(policy.cap,Math.ceil(policy.shortlist/level.length));
        for(const item of items) {
          const used=per.get(item.parent)||0;
          if(used>=parentLimit)continue;
          per.set(item.parent,used+1);selected.push(item);
          if(selected.length===policy.shortlist)break;
        }
        items.splice(0,items.length,...selected);
      }
      progress({stage:'guided_evaluate',remaining_moves:n-1,candidates:items.length,evaluated});
      for(let i=0;i<items.length;i+=policy.batch) {
        check();const batch=items.slice(i,i+policy.batch),scores=await inference.score(planes(batch),batch.length,passes);
        if(scores.length!==batch.length)throw Error('invalid_model_output');
        scores.forEach((score,j)=>{if(!Number.isFinite(score))throw Error('invalid_model_output');batch[j].score=score;});
      }
      check(); const order=items.map((item,index)=>({item,index}));
      order.sort((a,b)=>b.item.score-a.item.score||a.index-b.index);
      const perParent=new Map(),next=[];
      for(const {item} of order) {
        const used=perParent.get(item.parent)||0;
        if(used>=policy.cap)continue;
        perParent.set(item.parent,used+1);next.push(item);
        if(next.length===policy.width)break;
      }
      // Drop parent chains: only the actual tail is needed for final replay.
      level=next.map(({words,next,tail})=>({words,next,tail}));
      n--;evaluated+=items.length;
      steps.push({remaining_moves:n,generated,candidates:items.length,kept:level.length,seconds:(performance.now()-stepStart)/1000});
      progress({stage:'guided_selected',...steps.at(-1),evaluated});
    }
    return {candidates:level.filter(c=>c.next===n%2).map(c=>({...c,board:wordsBoard(c.words)})),evaluated,steps};
  }
  async function solve(board,encoder,sat,rules,inference,progress=()=>{},options={}) {
    const started=performance.now(),policy={...POLICY,...options};
    if(stones(board)<policy.min_stones)return root.RetroEngine.solve(board,encoder,sat,rules,progress);
    const search=root.RetroEngine.createSearch(board,encoder,sat,rules,progress);
    const large=stones(board)>=root.RetroEngine.POLICY.large_board_min_stones;
    const direct=search.attempt(1,{conflicts:large?100000:2000,decisions:large?1000000:20000});
    if(direct.status==='found'||direct.preprocess_rejection)return search.finish(direct);
    const prefixAttempts=[direct.stats];
    if(large) {
      const late=search.attempt(2,{conflicts:100000,decisions:1000000});
      prefixAttempts.push(late.stats);
      if(late.status==='found'||late.preprocess_rejection)return search.finish(late);
    }
    const guidance={policy,model:direct.status==='restricted_unsat'?'passes':'standard',hit:false,candidate_attempts:[]};
    try {
      const found=await beam(board,encoder,inference,guidance.model==='passes',progress,policy);
      guidance.evaluated=found.evaluated;guidance.steps=found.steps;
      for(const candidate of found.candidates.slice(0,policy.max_candidates)) {
        progress({stage:'guided_sat',tested:guidance.candidate_attempts.length,total_candidates:found.candidates.length});
        const check=root.RetroEngine.createSearch(candidate.board,encoder,sat,rules,()=>{});
        const result=check.attempt(1,{conflicts:policy.candidate_conflicts,decisions:policy.candidate_decisions});
        guidance.candidate_attempts.push(result.stats);
        if(result.status!=='found')continue;
        const tail=candidate.tail.map(s=>'abcdefgh'[s%8]+String((s>>>3)+1));
        // Check the entire path, including all implicit/explicit forced passes.
        // A valid prefix alone does not establish validity of its joined tail.
        let verified;
        try {verified=rules.verify([...result.moves,...tail],board);}catch{continue;}
        guidance.hit=true;
        return {status:'found',moves:verified.moves,terminal:verified.terminal,
          stats:{policy:{...policy,machine_learning:true},solved_by:'lightweight_auto',
            attempts:prefixAttempts,guidance},wall_seconds:(performance.now()-started)/1000};
      }
      guidance.miss_reason=found.reason||'candidates_exhausted';
    }catch(error) {
      guidance.miss_reason=error?.message==='guided_budget'?'guided_budget':'model_or_guidance_error';
    }
    progress({stage:'guided_fallback'});
    // The direct probe has already run. Do not repeat it after a guided miss.
    const result=search.finish(search.attempt(3),{guidance});
    result.wall_seconds=(performance.now()-started)/1000;
    return result;
  }
  return {POLICY,wordsBoard,children,planes,beam,solve};
});
