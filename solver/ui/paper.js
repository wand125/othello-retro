'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const dirs = [-1, 0, 1].flatMap(r => [-1, 0, 1].map(c => [r,c])).filter(([r,c]) => r || c);
  let data, example, frames=[], step=0, timer=null, reverseIndex=0, candidateIndex=0, revealed=false, deepChainIndex=0, verdictKey='found', loadError=null;
  let lang=new URLSearchParams(location.search).get('lang');
  if(!['ja','en'].includes(lang)){try{lang=localStorage.getItem('othello-paper-language');}catch(_){}if(!['ja','en'].includes(lang))lang='en';}
  const tr=(ja,en)=>lang==='ja'?ja:en;
  const color=c=>c==='X'?tr('黒','Black'):tr('白','White');
  const opponent=c=>c==='X'?'O':'X';
  const name=s=>'abcdefgh'[s%8]+(Math.floor(s/8)+1);
  const staticNodes=[...document.querySelectorAll('[data-ja][data-en]')];
  const attrNodes=[...document.querySelectorAll('[data-ja-aria-label][data-en-aria-label]')];
  let dark=false;try{dark=localStorage.getItem('othello-paper-theme')==='dark';}catch(_){}
  function theme(){
    document.documentElement.dataset.theme=dark?'dark':'light';
    $('theme').textContent=dark?tr('明るい配色','Light theme'):tr('暗い配色','Dark theme');
    $('theme').setAttribute('aria-label',dark?tr('明るい配色に切り替え','Switch to light theme'):tr('暗い配色に切り替え','Switch to dark theme'));
  }
  function flips(board,square,c){
    if(board[square]!=='-')return [];
    const result=[],r0=Math.floor(square/8),c0=square%8;
    for(const[dr,dc]of dirs){const line=[];let r=r0+dr,k=c0+dc;while(r>=0&&r<8&&k>=0&&k<8&&board[r*8+k]===opponent(c)){line.push(r*8+k);r+=dr;k+=dc;}if(line.length&&r>=0&&r<8&&k>=0&&k<8&&board[r*8+k]===c)result.push(...line);}
    return result;
  }
  const legal=(board,c)=>[...board].some((_,s)=>flips(board,s,c).length);
  function replay(record){
    let b=[...data.initial],side='X';const result=[{board:[...b],side,last:-1,changed:[],move:null}];
    for(const move of record){let square=-1,changed=[];
      if(move==='pass'){if(legal(b,side)||!legal(b,opponent(side)))throw Error(tr('不正なパス','Illegal pass'));}
      else{square='abcdefgh'.indexOf(move[0])+(Number(move[1])-1)*8;changed=flips(b,square,side);if(!changed.length)throw Error(tr('不正な着手 ','Illegal placement ')+move);for(const s of[square,...changed])b[s]=side;}
      side=opponent(side);result.push({board:[...b],side,last:square,changed,move});
    }return result;
  }
  function board(el,cells,last=-1,changed=[]){
    const frag=document.createDocumentFragment(),changedSet=new Set(changed);
    for(let i=0;i<64;i++){const cell=document.createElement('span');cell.className='cell'+(cells[i]==='X'?' black':cells[i]==='O'?' white':'')+(i===last?' last':'')+(changedSet.has(i)?' changed':'');cell.title=name(i)+' '+(cells[i]==='-'?tr('空き','empty'):color(cells[i]));if(cells[i]!=='-'){const stone=document.createElement('span');stone.className='stone';cell.append(stone);}frag.append(cell);}
    el.replaceChildren(frag);const b=[...cells].filter(c=>c==='X').length,w=[...cells].filter(c=>c==='O').length;
    el.setAttribute('aria-label',tr(`盤面。黒${b}石、白${w}石。${last>=0?'直前の着手 '+name(last)+'。':''}`,`Board: ${b} Black discs and ${w} White discs.${last>=0?' Last placement: '+name(last)+'.':''}`));
  }
  function playLabel(){$('play').textContent=timer?tr('停止','Stop'):tr('再生','Play');}
  function stop(){clearInterval(timer);timer=null;playLabel();}
  function exampleTitle(e){if(lang==='ja')return e.title;const n=64-[...e.board].filter(c=>c==='-').length,p=e.moves.filter(m=>m==='pass').length;return(e.terminal?'Terminal board':'Intermediate board')+` (${n} discs${p?', '+p+' pass'+(p===1?'':'es'):''})`;}
  function updateExampleLabels(){[...$('example-select').options].forEach((o,i)=>o.textContent=exampleTitle(data.examples[i])+' · '+data.examples[i].id.slice(-4));}
  function renderRecord(){
    const frag=document.createDocumentFragment();example.moves.forEach((m,i)=>{const b=document.createElement('button');b.textContent=(i+1)+'. '+m;b.title=tr(`手順${i+1}: ${color(i%2?'O':'X')} ${m}`,`Step ${i+1}: ${color(i%2?'O':'X')} ${m}`);b.setAttribute('aria-label',b.title);b.addEventListener('click',()=>{stop();step=i+1;drawReplay();});frag.append(b);});$('record').replaceChildren(frag);
    const p=example.moves.filter(m=>m==='pass').length;
    $('replay-check').textContent=tr(`再生検証: 合法 / 目標64マスに一致。${p}回のパス。末尾まで動かすと入力盤面に戻ります。`,`Replay check: legal; all 64 target squares match. ${p} pass${p===1?'':'es'}. The final step reproduces the input board.`);
  }
  function drawReplay(){
    const f=frames[step];board($('replay-board'),f.board,f.last,f.changed);$('ply').value=step;
    const b=f.board.filter(c=>c==='X').length,w=f.board.filter(c=>c==='O').length,ended=!legal(f.board,'X')&&!legal(f.board,'O');
    let state=ended?tr('終局','Game over'):tr(`次は${color(f.side)}`,`${color(f.side)} to move`);if(!ended&&!legal(f.board,f.side))state+=tr('（パス）',' (pass)');
    $('replay-info').textContent=tr(`手順 ${step} / ${frames.length-1}　黒 ${b} · 白 ${w}　${state}${f.move?'　直前: '+f.move:''}`,`Step ${step} / ${frames.length-1} · Black ${b}, White ${w} · ${state}${f.move?' · Last: '+f.move:''}`);
    $('first').disabled=$('prev').disabled=step===0;$('last').disabled=$('next').disabled=step===frames.length-1;
    [...$('record').children].forEach((b,i)=>{b.classList.toggle('current',i+1===step);b.setAttribute('aria-current',i+1===step?'step':'false');});playLabel();
  }
  function chooseExample(index){
    stop();example=data.examples[index];frames=replay(example.moves);if(frames.at(-1).board.join('')!==example.board)throw Error(tr('棋譜の終点が入力と一致しません','Record endpoint does not match the input'));
    step=frames.length-1;$('ply').max=step;$('example-link').href='https://othello-retro.logicpuzzle.app/examples/'+example.id;renderRecord();drawReplay();
  }
  function drawReverse(){
    const d=data.reverse[reverseIndex],c=d.candidates[candidateIndex];board($('reverse-before'),c.board);board($('reverse-target'),d.target,c.square,c.flipped);$('candidate-count').textContent=`${candidateIndex+1} / ${d.candidates.length}`;
    const frag=document.createDocumentFragment();d.candidates.forEach((_,i)=>{const b=document.createElement('button');b.textContent=tr('候補 ','Candidate ')+(i+1);b.setAttribute('aria-pressed',String(i===candidateIndex));b.addEventListener('click',()=>{candidateIndex=i;revealed=false;drawReverse();});frag.append(b);});$('candidate-buttons').replaceChildren(frag);
    $('candidate-info').textContent=tr(`${color(d.color)}が ${c.move} に置くと ${c.flipped.length}石を反転し、右の目標盤面に一致します。この一手の合法性は検証済みです。`,`${color(d.color)} at ${c.move} flips ${c.flipped.length} disc${c.flipped.length===1?'':'s'} and reproduces the target on the right. This single legal transition has been checked.`);
    $('candidate-proof').hidden=!revealed;$('reveal').textContent=revealed?tr('到達可能性を隠す','Hide reachability'):tr('初期配置からの到達可能性を確かめる','Check reachability from the initial position');
    const n=d.exhaustive_states.toLocaleString(lang==='ja'?'ja-JP':'en-US'),r=d.candidates.filter(x=>x.reachable).length;
    $('candidate-proof').textContent=tr((c.reachable?'到達可能。この候補は初期配置から作れます。':'到達不能。この候補へは初期配置から進めません。')+` ${d.depth-1}着手後の全${n}盤面を列挙して照合しました。逆算候補${d.candidates.length}件のうち、初期配置につながるのは${r}件です。`,(c.reachable?'Reachable: this candidate can be constructed from the initial position.':'Unreachable: the initial position cannot lead to this candidate.')+` All ${n} boards after ${d.depth-1} placements were enumerated and compared. ${r} of the ${d.candidates.length} retained reverse candidates connect to the initial position.`);
  }
  function drawDeepChain(){
    const chain=data.deep_reverse_chain,n=chain.nodes[deepChainIndex];board($('deep-chain-board'),n.board);
    const head=tr(`逆算 ${deepChainIndex} / 11 · ${n.stones}石 · 次は${color(n.next_player)}`,`Reverse ${deepChainIndex} / 11 · ${n.stones} discs · ${color(n.next_player)} to move`);
    const edge=deepChainIndex>0?chain.edges[deepChainIndex-1]:null;
    $('deep-chain-readout').textContent=head+(edge?tr(`。${color(edge.mover)}が ${edge.move} に置くと、スライダーで一つ左の局面へ進みます。`,`; ${color(edge.mover)} at ${edge.move} moves forward to the position one slider step to the left.`):tr('。一般形CNFのUNSAT記録がある起点です。','; the root with a recorded general-CNF UNSAT result.'));
    $('deep-chain-step').value=deepChainIndex;
  }
  function drawPass(){
    const s=data.passes[Number($('pass-select').value)],white=[...s.middle].flatMap((_,i)=>flips(s.middle,i,'O').length?[i]:[]);
    if(JSON.stringify(white)!==JSON.stringify(s.opponent_legal))throw Error(tr('パス図の合法手データ不一致','Legal-move mismatch in the pass figure'));
    board($('pass-middle'),s.middle,s.first_square);for(const i of white)$('pass-middle').children[i].classList.add('possible');board($('pass-end'),s.end,s.second_square);
    const t=s.prefix_placements;
    $('pass-timeline').textContent=$('compressed-time').checked?tr(`配置時刻 ${t}: 黒 ${s.first} → ${t+1}: 黒 ${s.second} （同色が連続）`,`Placement ${t}: Black ${s.first} → ${t+1}: Black ${s.second} (same color)`):tr(`黒 ${s.first} → 白 pass → 黒 ${s.second} （パスの合法性を検査）`,`Black ${s.first} → White pass → Black ${s.second} (check pass legality)`);
    const guard=$('pass-guard').checked,only=$('target-only-pass').checked,inspected=only?white.filter(i=>s.end[i]!=='-'):white,satisfied=!guard||inspected.length===0;
    let result;
    if(!satisfied)result=tr('条件は不成立。白に合法手があるため、黒が続けて置くこの履歴は不合法です。','Condition fails. White has a legal placement, so this history with consecutive Black placements is illegal.');
    else if(white.length===0)result=tr('条件は成立。白は打てず、黒には次の合法手があるため、白の強制パスを挿入できます。','Condition holds. White cannot place and Black has a next legal placement, so a forced White pass can be inserted.');
    else result=tr('制約を弱めた検査は通過しますが、この履歴は不合法です。'+(!guard?'同色連続のパス条件を外したためです。':'目標でも空である白の合法手を検査から除いたためです。'),'The weakened check passes, but this history is illegal. '+(!guard?'The pass condition for consecutive same-color placements was removed.':'White’s legal placements on target-empty squares were excluded from inspection.'));
    $('pass-check').textContent=result;
    $('pass-details').textContent=tr(`実際の白の合法手: ${white.length?white.map(name).join(', '):'0件'}。`+(guard?`検査に含めた白の合法手: ${inspected.length}件。`:'パス条件を検査していません。')+(s.valid?'図の後半2着手は、62石で終局する実棋譜の末尾です。':'この例では白の合法3マスが目標でも全て空です。'),`Actual legal placements for White: ${white.length?white.map(name).join(', '):'none'}. `+(guard?`Legal placements included in the check: ${inspected.length}. `:'The pass condition is not checked. ')+(s.valid?'These two placements end a saved game on 62 discs.':'All three legal White squares remain empty in the target.'));
  }
  function closure(target){
    const occupied=new Set([...data.initial].flatMap((c,i)=>c!=='-'?[i]:[]));let changed=true;
    while(changed){const additions=[];for(let s=0;s<64;s++){if(target[s]==='-'||occupied.has(s))continue;const r=Math.floor(s/8),c=s%8;if(dirs.some(([dr,dc])=>{const r1=r+dr,c1=c+dc,r2=r+2*dr,c2=c+2*dc;return r1>=0&&r1<8&&c1>=0&&c1<8&&r2>=0&&r2<8&&c2>=0&&c2<8&&occupied.has(r1*8+c1)&&occupied.has(r2*8+c2);}))additions.push(s);}for(const s of additions)occupied.add(s);changed=additions.length>0;}
    return occupied;
  }
  function drawNecessary(){
    const bad=[...data.initial];bad[0]='X';const good=replay(['d3']).at(-1).board;board($('necessary-fail'),bad,0);board($('necessary-pass'),good,19,[27]);const a=closure(bad).size,b=closure(good).size;
    $('necessary-result').textContent=tr(`左: 閉包 ${a}/5マス。a1 は入らず到達不能。右: 閉包 ${b}/5マス。この必要条件を通過します。`,`Left: closure contains ${a}/5 squares. Missing a1 proves unreachability. Right: closure contains ${b}/5 squares and passes this necessary condition.`);
  }
  const verdicts={
    found:['found',['合法手だけで初期配置から再生でき、最後の64マスが入力と一致しました。その棋譜が到達可能性の具体的な証拠になります。元の対局そのものとは限りません。','Forward replay is legal from the initial position and all 64 final squares match the input. The record witnesses reachability; it need not be the original game.']],
    center:['unreachable',['標準初期配置の中央4マスは最初から占有され、その後の合法手で空きマスに戻ることはありません。その1マスが欠けた入力は、探索なしでも到達不能です。','The four central squares are occupied initially and legal play never empties them. An input missing one of them is unreachable without any search.']],
    restricted:['unknown',['パスなしの手順が存在しないと分かっただけです。パスを含む手順の可能性は残ります。一般の符号化で UNSAT が得られるか、別の不能根拠が必要です。','Only the absence of a no-pass history has been established. Histories with forced passes remain possible. UNSAT of the general encoding, or another unreachability argument, is needed.']],
    timeout:['unknown',['制限時間内に棋譜も不能の根拠も得られませんでした。予算を増やす、探索順を変える、方式を変えることで解が出る可能性があります。','Neither a record nor an unreachability argument was obtained within the limit. A larger budget, another search order, or a different method may still find a solution.']]
  };
  function verdict(key){verdictKey=key;$('verdict-label').textContent=verdicts[key][0];$('verdict-text').textContent=tr(...verdicts[key][1]);document.querySelectorAll('[data-verdict]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.verdict===key)));}
  function applyLanguage(next,writeURL=false){
    lang=next;document.documentElement.lang=lang;
    document.title=tr('オセロ盤面への到達可能性 — 逆算とSATによる合法履歴の構成','Reachability of Othello Boards — Constructing Legal Histories by Reverse Search and SAT');
    document.querySelector('meta[name=description]').content=tr('オセロ盤面への到達可能性を、必要条件、逆写像の非一意性、強制パスの圧縮、合法履歴のSAT符号化から説明する。','Othello board reachability through necessary conditions, non-unique inverse moves, compressed forced passes, and a SAT encoding of legal histories.');
    for(const el of staticNodes)el.innerHTML=el.dataset[lang];
    for(const el of attrNodes)el.setAttribute('aria-label',el.getAttribute('data-'+lang+'-aria-label'));
    document.querySelectorAll('[data-language]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.language===lang)));
    theme();verdict(verdictKey);
    if(data){updateExampleLabels();renderRecord();drawReplay();drawReverse();drawPass();drawNecessary();drawDeepChain();}
    if(loadError)$('load-error').textContent=tr('図のデータを読み込めませんでした。本文と証明は閲覧できます。 ','Figure data could not be loaded. The text and proofs remain readable. ')+loadError;
    if(writeURL){try{localStorage.setItem('othello-paper-language',lang);}catch(_){}const url=new URL(location.href);url.searchParams.set('lang',lang);history.replaceState(null,'',url);}
  }
  document.querySelectorAll('[data-language]').forEach(b=>b.addEventListener('click',()=>applyLanguage(b.dataset.language,true)));
  $('deep-chain-step').addEventListener('input',()=>{deepChainIndex=Number($('deep-chain-step').value);if(data)drawDeepChain();});
  $('theme').addEventListener('click',()=>{dark=!dark;theme();try{localStorage.setItem('othello-paper-theme',dark?'dark':'light');}catch(_){}});
  for(const id of['pass-select','compressed-time','pass-guard','target-only-pass'])$(id).addEventListener('change',()=>{if(data)drawPass();});
  $('first').addEventListener('click',()=>{stop();step=0;drawReplay();});$('last').addEventListener('click',()=>{stop();step=frames.length-1;drawReplay();});$('prev').addEventListener('click',()=>{stop();step=Math.max(0,step-1);drawReplay();});$('next').addEventListener('click',()=>{stop();step=Math.min(frames.length-1,step+1);drawReplay();});$('ply').addEventListener('input',()=>{stop();step=Number($('ply').value);drawReplay();});
  $('play').addEventListener('click',()=>{if(timer){stop();return;}if(step===frames.length-1)step=0;timer=setInterval(()=>{step++;drawReplay();if(step===frames.length-1)stop();},650);drawReplay();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
  $('example-select').addEventListener('change',()=>chooseExample(Number($('example-select').value)));
  $('reverse-select').addEventListener('change',()=>{reverseIndex=Number($('reverse-select').value);candidateIndex=0;revealed=false;drawReverse();});$('reveal').addEventListener('click',()=>{revealed=!revealed;drawReverse();});
  document.querySelectorAll('[data-verdict]').forEach(b=>b.addEventListener('click',()=>verdict(b.dataset.verdict)));
  const liveControls=[...document.querySelectorAll('figure button,figure select,figure input')];liveControls.forEach(el=>el.disabled=true);applyLanguage(lang);
  fetch('/paper-data.json').then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();}).then(d=>{
    data=d;for(const e of data.examples){if(replay(e.moves).at(-1).board.join('')!==e.board)throw Error(tr('棋譜検証エラー','Record verification failed'));}
    const options=data.examples.map((_,i)=>{const o=document.createElement('option');o.value=i;return o;});$('example-select').replaceChildren(...options);$('example-select').value='2';updateExampleLabels();liveControls.forEach(el=>el.disabled=false);chooseExample(2);drawReverse();drawPass();drawNecessary();drawDeepChain();document.documentElement.dataset.paperReady='true';
  }).catch(error=>{loadError=error.message;$('load-error').hidden=false;applyLanguage(lang);console.error(error);});
})();
