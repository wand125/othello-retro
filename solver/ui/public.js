/* Public UI: board input, reconstruction and silent replay. */
"use strict";
(() => {
const FILES = "abcdefgh";
const DIRS = [[0,1],[0,-1],[1,0],[-1,0],[1,1],[1,-1],[-1,1],[-1,-1]];
const INIT = (() => { const b = Array(64).fill("-"); b[27] = "O"; b[36] = "O"; b[28] = "X"; b[35] = "X"; return b; })();
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const sqName = s => FILES[s % 8] + (Math.floor(s / 8) + 1);
const nameSq = n => (parseInt(n.slice(1)) - 1) * 8 + FILES.indexOf(n[0]);
const other = c => (c === "X" ? "O" : "X");

// ---- オセロ ----
function flipsOf(b, s, c) {
  const o = other(c), r0 = Math.floor(s / 8), c0 = s % 8, out = [];
  if (b[s] !== "-") return out;
  for (const [dr, dc] of DIRS) {
    let r = r0 + dr, cc = c0 + dc; const line = [];
    while (r >= 0 && r < 8 && cc >= 0 && cc < 8 && b[r * 8 + cc] === o) { line.push(r * 8 + cc); r += dr; cc += dc; }
    if (line.length && r >= 0 && r < 8 && cc >= 0 && cc < 8 && b[r * 8 + cc] === c) out.push(...line);
  }
  return out;
}
const hasMove = (b, c) => b.some((_, s) => flipsOf(b, s, c).length > 0);

// 棋譜テキスト → 着手の列（"f5" など小文字、または "pass"）。手番号や区切り記号は無視する
function parseRecord(text) {
  return (text.match(/[a-h][1-8]|pass|ps|--/gi) || []).map(t => (/^[a-h][1-8]$/i.test(t) ? t.toLowerCase() : "pass"));
}

// 着手の列 → 各局面（1 局面 = 石を 1 個置いた後）。パスは局面にせず手番だけ切り替える（省略されていても補う）。
// 非合法な手があればそこまでの局面と error を返す
function buildStates(moves) {
  const states = [{ b: INIT.slice(), last: null, flipped: new Set(), mover: null }];
  let b = INIT.slice(), c = "X";
  for (let i = 0; i < moves.length; i++) {
    const m = moves[i];
    if (m === "pass") {
      if (hasMove(b, c)) return { states, error: `${i + 1} 番目: ${c === "X" ? "黒" : "白"}に合法手があるのにパス` };
      c = other(c);
      continue;
    }
    const s = nameSq(m);
    if (!flipsOf(b, s, c).length && !hasMove(b, c) && flipsOf(b, s, other(c)).length) c = other(c);  // 省略されたパス
    const f = flipsOf(b, s, c);
    if (!f.length) return { states, error: `${i + 1} 番目の ${m} は${c === "X" ? "黒" : "白"}の合法手ではない` };
    for (const x of f) b[x] = c;
    b[s] = c;
    states.push({ b: b.slice(), last: s, flipped: new Set(f), mover: c, move: m });
    c = other(c);
  }
  return { states, error: null };
}

const EDGES = [
  { name: "1段目", sq: [0, 1, 2, 3, 4, 5, 6, 7] }, { name: "8段目", sq: [56, 57, 58, 59, 60, 61, 62, 63] },
  { name: "a列", sq: [0, 8, 16, 24, 32, 40, 48, 56] }, { name: "h列", sq: [7, 15, 23, 31, 39, 47, 55, 63] }];
const EDGE_OK = (() => {
  const P3 = [1, 3, 9, 27, 81, 243, 729, 2187], N = 6561, seen = new Uint8Array(N), stack = [0];
  seen[0] = 1;
  while (stack.length) {
    const st = stack.pop(), a = P3.map(p => Math.floor(st / p) % 3);
    for (let i = 0; i < 8; i++) {
      if (a[i]) continue;
      for (const c of [1, 2]) {
        const r = a.slice(); r[i] = c;
        for (const d of [-1, 1]) {
          let j = i + d;
          while (j >= 0 && j < 8 && r[j] === 3 - c) j += d;
          if (j >= 0 && j < 8 && r[j] === c) for (let k = i + d; k !== j; k += d) r[k] = c;
        }
        const t = r.reduce((acc, v, k) => acc + v * P3[k], 0);
        if (!seen[t]) { seen[t] = 1; stack.push(t); }
      }
    }
  }
  return seen;
})();
const edgeIndex = (b, sqs) => sqs.reduce((acc, s, i) => acc + ({ "-": 0, X: 1, O: 2 })[b[s]] * 3 ** i, 0);
const CENTER = [27, 28, 35, 36];
function precheck(b) {
  const items = [], bad = new Set();
  const occ = b.map(v => v !== "-");
  const missing = CENTER.filter(s => !occ[s]);
  items.push({ ok: !missing.length, label: "中央 4 マス", why: missing.length ? `${missing.map(sqName).join(" ")} が空` : "" });
  missing.forEach(s => bad.add(s));
  // 置き順の閉包: 置くには、ある方向で隣とその先が既に埋まっている必要がある
  const P = new Uint8Array(64); CENTER.forEach(s => P[s] = occ[s] ? 1 : 0);
  for (let changed = true; changed;) {
    changed = false;
    for (let s = 0; s < 64; s++) {
      if (!occ[s] || P[s]) continue;
      const r = Math.floor(s / 8), c = s % 8;
      if (DIRS.some(([dr, dc]) => {
        const r1 = r + dr, c1 = c + dc, r2 = r + 2 * dr, c2 = c + 2 * dc;
        return r2 >= 0 && r2 < 8 && c2 >= 0 && c2 < 8 && P[r1 * 8 + c1] && P[r2 * 8 + c2];
      })) { P[s] = 1; changed = true; }
    }
  }
  const orphan = [...Array(64).keys()].filter(s => occ[s] && !P[s]);
  items.push({ ok: !orphan.length, label: "置き順（孤立した石なし）",
    why: orphan.length ? `${orphan.slice(0, 6).map(sqName).join(" ")}${orphan.length > 6 ? " ほか" : ""} に置く手順がない` : "" });
  orphan.forEach(s => bad.add(s));
  for (const e of EDGES) {
    const ok = !!EDGE_OK[edgeIndex(b, e.sq)];
    items.push({ ok, label: `辺 ${e.name}`, why: ok ? "" : "この並びは作れない" });
    if (!ok) e.sq.filter(s => occ[s]).forEach(s => bad.add(s));
  }
  return { ok: items.every(i => i.ok), items, bad };
}
const $ = id => document.getElementById(id);
const config = JSON.parse($('publicConfig').textContent);
const libraryMode = !!config.library;
const load = key => { try { return JSON.parse(localStorage.getItem('othello-retro-' + key) || 'null'); } catch { return null; } };
const store = (key, value) => { try { localStorage.setItem('othello-retro-' + key, JSON.stringify(value)); } catch {} };
let savedBoard; try { savedBoard = localStorage.getItem('othello-retro-board'); } catch {}
let board = /^[XO-]{64}$/.test(savedBoard || '') ? [...savedBoard] : INIT.slice();
const requestedBoard = new URLSearchParams(location.search).get('board');
if (!libraryMode && /^[XO-]{64}$/.test(requestedBoard || '') && !load('job')) board = [...requestedBoard];
let brush = 'cycle', painting = null, job = null, pollVersion = 0, timer = null, playTimer = null, leaving = false;
let states = [], ply = 0, lastStage = '', resultTarget = null;
for (const option of [...$('timeSel').options]) if (+option.value > config.maxSeconds) option.remove();
const previousTime = load('public-time');
if ([...$('timeSel').options].some(option => +option.value === previousTime)) $('timeSel').value = previousTime;
$('timeSel').onchange = () => store('public-time', +$('timeSel').value);

function makeBoard(id, cols, rows, editable) {
  $(cols).innerHTML = [...FILES].map(f => `<span>${f}</span>`).join('');
  $(rows).innerHTML = Array.from({length:8}, (_, i) => `<span>${i + 1}</span>`).join('');
  $(id).innerHTML = Array.from({length:64}, (_, s) => editable ?
    `<button type="button" class="cell" data-sq="${s}"><span class="disc"></span></button>` :
    `<div class="cell" data-sq="${s}"><span class="disc"></span></div>`).join('');
  return [...$(id).children];
}
const editCells = makeBoard('editBoard', 'editCols', 'editRows', true);
const playCells = makeBoard('playBoard', 'playCols', 'playRows', false);
function paint(cells, position, last = null) {
  cells.forEach((cell, s) => {
    cell.firstChild.className = 'disc' + (position[s] === '-' ? '' : ' ' + position[s]);
    cell.setAttribute('aria-label', `${sqName(s)}：${{'-':'空', X:'黒', O:'白'}[position[s]]}`);
    cell.classList.toggle('last', s === last);
  });
}
function renderInput() {
  if (resultTarget && resultTarget !== board.join('')) {
    stopPlayback(); $('playback').hidden = true; $('elapsed').textContent = '';
    notice('盤面が変更されました', '新しい盤面の棋譜を探してください。');
    resultTarget = null; store('result', null);
  }
  paint(editCells, board);
  const x = board.filter(v => v === 'X').length, o = board.filter(v => v === 'O').length;
  $('counts').textContent = `黒 ${x}　白 ${o}　空 ${64 - x - o}`;
  $('boardText').value = Array.from({length:8}, (_, r) => board.slice(r * 8, r * 8 + 8).join('')).join('\n');
  const check = precheck(board), failed = check.items.filter(item => !item.ok);
  $('check').textContent = failed.length ? failed.map(item => item.why || item.label).join('・') : '盤面の準備ができました。';
  $('check').classList.toggle('error', !check.ok);
  editCells.forEach((cell, s) => cell.classList.toggle('bad', check.bad.has(s)));
  try { localStorage.setItem('othello-retro-board', board.join('')); } catch {}
  document.querySelectorAll('#inputSection button, #inputSection select, #inputSection textarea').forEach(el => {
    if (el.id !== 'btnCancel') el.disabled = !!job;
  });
  $('btnSolve').disabled = !!job || !check.ok;
  $('btnCancel').hidden = !job;
}
function put(square) {
  if (job) return;
  board[square] = painting; $('importMsg').textContent = ''; renderInput();
}
$('editBoard').addEventListener('pointerdown', event => {
  const cell = event.target.closest('button[data-sq]'); if (!cell || job || event.button > 0) return;
  const square = +cell.dataset.sq;
  painting = brush === 'cycle' ? {'-':'X', X:'O', O:'-'}[board[square]] : brush;
  put(square); $('editBoard').setPointerCapture(event.pointerId);
});
$('editBoard').addEventListener('pointermove', event => {
  if (painting === null || job) return;
  const cell = document.elementFromPoint(event.clientX, event.clientY)?.closest('#editBoard button[data-sq]');
  if (cell && board[+cell.dataset.sq] !== painting) put(+cell.dataset.sq);
});
for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) $('editBoard').addEventListener(name, () => painting = null);
$('editBoard').addEventListener('click', event => {
  const cell = event.target.closest('button[data-sq]'); if (!cell || event.detail !== 0 || job) return;
  painting = brush === 'cycle' ? {'-':'X', X:'O', O:'-'}[board[+cell.dataset.sq]] : brush;
  put(+cell.dataset.sq); painting = null;
});
document.querySelectorAll('[data-brush]').forEach(button => button.onclick = () => {
  brush = button.dataset.brush;
  document.querySelectorAll('[data-brush]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
});
$('btnInit').onclick = () => { board = INIT.slice(); renderInput(); };
$('btnClear').onclick = () => { board = Array(64).fill('-'); renderInput(); };
$('btnSwap').onclick = () => { board = board.map(v => v === '-' ? '-' : other(v)); renderInput(); };
const transform = map => { const before = board.slice(); board = before.map((_, s) => before[map(Math.floor(s / 8), s % 8)]); renderInput(); };
$('btnRotate').onclick = () => transform((r, c) => (7 - c) * 8 + r);
$('btnFlipH').onclick = () => transform((r, c) => r * 8 + 7 - c);
$('btnFlipV').onclick = () => transform((r, c) => (7 - r) * 8 + c);
$('btnExample').onclick = () => {
  const example = buildStates(['d3','c3','f5','d2','c4','g6','d1','e3','c2','c6','d6','b4']);
  board = example.states.at(-1).b.slice(); renderInput();
};
$('btnImport').onclick = () => {
  const text = $('boardText').value.trim(), hex = text.match(/^(?:0x)?([0-9a-f]{1,16})\s*,\s*(?:0x)?([0-9a-f]{1,16})$/i);
  let parsed;
  if (hex) {
    const black = BigInt('0x' + hex[1]), white = BigInt('0x' + hex[2]);
    if (black & white) { $('importMsg').textContent = '同じマスに黒と白が重なっています。'; return; }
    parsed = Array.from({length:64}, (_, s) => (black >> BigInt(s)) & 1n ? 'X' : (white >> BigInt(s)) & 1n ? 'O' : '-');
  } else {
    const mapping = {X:'X',x:'X',B:'X',b:'X','●':'X',O:'O',o:'O',W:'O',w:'O','○':'O','-':'-','.':'-','_':'-'};
    const input = [...text.replace(/\s+/g, '')];
    if (input.length !== 64 || input.some(c => !(c in mapping))) { $('importMsg').textContent = '黒X・白O・空-で、64マス分を入力してください。'; return; }
    parsed = input.map(c => mapping[c]);
  }
  board = parsed; renderInput(); $('importMsg').textContent = '読み込みました。';
};

function notice(title, message = '', kind = '', spinning = false) {
  $('status').innerHTML = `<div class="notice ${kind}"><strong>${spinning ? '<span class="spinner"></span>' : ''}${esc(title)}</strong>${message ? `<span class="hint">${esc(message)}</span>` : ''}</div>`;
}
function stopPlayback() { clearInterval(playTimer); playTimer = null; $('play').textContent = '再生'; }
function showPly(next) {
  if (!states.length) return;
  ply = Math.max(0, Math.min(states.length - 1, next));
  const state = states[ply]; paint(playCells, state.b, state.last);
  $('slider').value = ply;
  $('ply').textContent = ply ? `${ply} / ${states.length - 1}手目：${state.mover === 'X' ? '黒' : '白'} ${state.move}` : '初期配置';
  $('first').disabled = $('prev').disabled = ply === 0;
  $('next').disabled = $('last').disabled = ply === states.length - 1;
  $('play').disabled = states.length <= 1;
  if (!libraryMode) { try { localStorage.setItem('othello-retro-result-k', String(ply)); } catch {} }
}
function showResult(result, target, seconds, fresh = true) {
  resultTarget = target.join('');
  stopPlayback(); $('playback').hidden = true; $('elapsed').textContent = ''; $('copyStatus').textContent = '';
  if (result.status !== 'found') {
    const messages = {
      unreachable:['この盤面には到達できません', result.reason || '合法な手順では作れない盤面です。'],
      unknown:['制限時間内に見つかりませんでした', '時間を延ばして再度お試しください。到達できないと確定したわけではありません。'],
      cancelled:['探索を中止しました', '盤面を編集したり、もう一度探索したりできます。'],
      error:['探索できませんでした', result.reason || 'しばらくしてから再度お試しください。']
    };
    const [title, message] = messages[result.status] || messages.error;
    notice(title, message, ['unreachable','error'].includes(result.status) ? 'error' : '');
  } else {
    const legal = Array.isArray(result.moves) && result.moves.every(m => typeof m === 'string' && /^(?:[a-h][1-8]|pass)$/.test(m));
    const built = legal ? buildStates(result.moves) : {error:true};
    if (built.error || !built.states.at(-1).b.every((v, i) => v === target[i])) {
      notice('結果を確認できませんでした', '棋譜と入力した盤面が一致しません。もう一度お試しください。', 'error'); return;
    }
    states = built.states;
    notice('棋譜が見つかりました', `${states.length - 1}手・${Number(result.time ?? seconds).toFixed(1)}秒・入力した盤面と一致`, 'ok');
    if (!libraryMode && /^record-[A-Za-z0-9_-]+$/.test(result.record_id || '')) $('status').insertAdjacentHTML('beforeend', `<p class="hint"><a href="/examples/${result.record_id}">作成された棋譜として開く</a></p>`);
    $('record').value = result.moves.join(''); $('slider').max = states.length - 1; $('playback').hidden = false;
    let selected = states.length - 1;
    if (!fresh && !libraryMode) { try { const value = localStorage.getItem('othello-retro-result-k'); if (value !== null) selected = Number(value); } catch {} }
    showPly(Number.isFinite(selected) ? selected : states.length - 1);
  }
  if (fresh) store('result', {res:result, target:target.join(''), secs:seconds});
}
for (const [id, position] of [['first', () => 0], ['prev', () => ply - 1], ['next', () => ply + 1], ['last', () => states.length - 1]]) {
  $(id).onclick = () => { stopPlayback(); showPly(position()); };
}
$('slider').oninput = () => { stopPlayback(); showPly(+$('slider').value); };
$('play').onclick = () => {
  if (playTimer) { stopPlayback(); return; }
  if (ply >= states.length - 1) showPly(0);
  $('play').textContent = '停止';
  playTimer = setInterval(() => { showPly(ply + 1); if (ply >= states.length - 1) stopPlayback(); }, 500);
};
$('copy').onclick = async () => {
  try { await navigator.clipboard.writeText($('record').value); $('copyStatus').textContent = '棋譜をコピーしました。'; }
  catch { $('record').focus(); $('record').select(); $('copyStatus').textContent = '棋譜を選択しました。コピーしてください。'; }
};

function searching(stage) {
  if (stage === lastStage) return;
  lastStage = stage;
  notice(stage === 'queued' ? '探索の順番を待っています' : '棋譜を探しています', '石が多い盤面は時間がかかることがあります。ページを再読み込みしても探索は続きます。', '', true);
}
function beginSearch(pending) {
  stopPlayback(); job = pending; lastStage = ''; $('playback').hidden = true; $('btnCancel').disabled = false;
  store('job', pending); renderInput(); searching('queued');
  const tick = () => $('elapsed').textContent = `経過 ${Math.max(0, Math.floor((Date.now() - pending.t0) / 1000))}秒 ／ 制限 ${pending.limit}秒`;
  clearInterval(timer); tick(); timer = setInterval(tick, 1000);
}
function finishSearch(pending, result) {
  if (leaving || job?.id !== pending.id) return;
  clearInterval(timer); job = null; store('job', null); renderInput();
  if (result.status === 'found') result.record_id = 'record-' + pending.id;
  showResult(result, [...pending.target], (Date.now() - pending.t0) / 1000);
}
async function poll(pending, version) {
  while (!leaving && job?.id === pending.id && version === pollVersion) {
    try {
      const response = await fetch('/api/result?id=' + encodeURIComponent(pending.id));
      if (response.ok) {
        const result = await response.json();
        if (result.status === 'running') searching(result.stage || 'running');
        else if (result.status !== 'lost' || Date.now() - pending.t0 > 15000) {
          finishSearch(pending, result.status === 'lost' ? {status:'error', reason:'探索の記録が見つかりません。再度お試しください。'} : result); return;
        }
      }
    } catch {} // A transient network failure must not discard a running job.
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
}
$('btnSolve').onclick = async () => {
  if (job || !precheck(board).ok) return;
  const pending = {id:crypto.randomUUID().replaceAll('-', ''), target:board.join(''), limit:+$('timeSel').value, t0:Date.now()};
  beginSearch(pending); const version = ++pollVersion;
  try {
    const response = await fetch('/api/solve', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id:pending.id, board:pending.target, time:pending.limit})});
    const result = await response.json();
    if (!response.ok) { finishSearch(pending, {status:'error', reason:result.reason || result.error}); return; }
    if (result.status !== 'queued') { finishSearch(pending, result); return; }
  } catch {} // The request may have reached the server; recover by polling its ID.
  await poll(pending, version);
};
$('btnCancel').onclick = async () => {
  if (!job) return;
  $('btnCancel').disabled = true;
  try {
    const response = await fetch('/api/cancel', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id:job.id})});
    if (!response.ok) throw new Error();
  } catch { $('btnCancel').disabled = false; notice('中止を送信できませんでした', '接続を確認し、もう一度「中止」を押してください。'); }
};
addEventListener('pagehide', () => { leaving = true; clearInterval(timer); stopPlayback(); });
document.querySelectorAll('nav a').forEach(link => {
  if (link.getAttribute('href') === (libraryMode ? '/examples' : '/')) link.setAttribute('aria-current', 'page');
});
function recordTime(example) {
  return typeof example.elapsed_seconds === 'number' && Number.isFinite(example.elapsed_seconds)
    ? `${example.elapsed_seconds.toLocaleString('ja-JP', {maximumFractionDigits:3})}秒` : '記録なし';
}
function recordDate(value) {
  if (!value || !Number.isFinite(Date.parse(value))) return '記録なし';
  return new Date(value).toLocaleString('ja-JP', {timeZone:'Asia/Tokyo', hour12:false}) + '（日本時間）';
}
function checkRecord(example) {
  if (!/^[A-Za-z0-9_-]{1,100}$/.test(example.id || '') || !/^[XO-]{64}$/.test(example.board || '') || !Array.isArray(example.moves)) throw new Error();
  const built = buildStates(example.moves);
  if (built.error || built.states.at(-1).b.join('') !== example.board) throw new Error();
  return example;
}
function recordCard(example) {
  return `<a class="example-card" href="/examples/${example.id}"><div class="board readonly preview" role="img" aria-label="${esc(example.title)}">${[...example.board].map(v => `<div class="cell"><span class="disc${v === '-' ? '' : ' ' + v}"></span></div>`).join('')}</div><strong>${esc(example.title)}</strong><span class="hint">${example.moves.filter(m => m !== 'pass').length}手・検証済み</span><span class="hint">計算時間 ${esc(recordTime(example))}</span></a>`;
}
function recordMetadata(example) {
  const methodNames = {sat:'SAT', beam:'学習モデルで候補を絞り込み'};
  return `<dl class="record-metadata"><dt>計算時間</dt><dd>${esc(recordTime(example))}</dd><dt>制限時間</dt><dd>${example.requested_seconds == null ? '記録なし' : esc(String(example.requested_seconds)) + '秒'}</dd><dt>探索方法</dt><dd>${esc(methodNames[example.method] || example.method || '記録なし')}</dd><dt>実行環境</dt><dd>${esc(example.environment || '記録なし')}</dd><dt>作成日時</dt><dd>${esc(recordDate(example.finished_at))}</dd></dl>${example.timing_note ? `<p class="hint">${esc(example.timing_note)}</p>` : ''}`;
}
async function showLibrary() {
  $('inputSection').hidden = true; $('resultSection').hidden = true;
  $('examplesSection').hidden = false;
  $('intro').textContent = '作成された盤面と合法な棋譜を、計算時間とともに確認できます。';
  document.querySelector('h1').textContent = '作成された棋譜';
  $('examplesSection').innerHTML = '<p class="hint">棋譜を読み込んでいます…</p>';
  let staticExamples;
  const fallback = async () => {
    if (!staticExamples) {
      const response = await fetch('/public-examples.json'); if (!response.ok) throw new Error();
      staticExamples = (await response.json()).examples;
    }
    return staticExamples;
  };
  try {
    if (config.example) {
      let example;
      try {
        const response = await fetch('/api/records/' + encodeURIComponent(config.example)); if (!response.ok) throw new Error();
        example = await response.json();
      } catch { example = (await fallback()).find(e => e.id === config.example); }
      if (!example) throw new Error();
      checkRecord(example);
      $('examplesSection').innerHTML = `<a href="/examples">一覧へ戻る</a><h2>${esc(example.title)}</h2><p class="hint">合法な棋譜を再生し、各手の盤面を確認できます。</p>${recordMetadata(example)}<a href="/?board=${example.board}">この盤面で探索する</a>`;
      $('examplesSection').classList.add('example-description');
      $('resultSection').hidden = false;
      $('resultTitle').textContent = '盤面と棋譜';
      showResult({status:'found', moves:example.moves, time:example.elapsed_seconds}, [...example.board], 0, false);
      notice('検証済みの棋譜', `${example.moves.filter(m => m !== 'pass').length}手・合法手と最終盤面の一致を確認済み`, 'ok');
    } else {
      let cursor = null, loaded = 0, seen = new Set();
      $('examplesSection').innerHTML = '<h2>作成された盤面と棋譜</h2><p class="hint">各盤面を開くと、初期配置からの再生、棋譜のコピー、計算時間の確認ができます。</p><p id="recordsMessage" class="hint" role="status"></p><div class="examples-grid" id="recordsGrid"></div><button type="button" id="moreRecords" hidden>続きを表示</button>';
      const loadPage = async () => {
        $('moreRecords').disabled = true;
        try {
          let rows, next = null, usingFallback = false;
          try {
            const response = await fetch('/api/records' + (cursor ? '?cursor=' + encodeURIComponent(cursor) : '')); if (!response.ok) throw new Error();
            const payload = await response.json(); rows = payload.records; next = payload.next_cursor;
            if (!Array.isArray(rows)) throw new Error();
          } catch {
            if (loaded) throw new Error();
            rows = await fallback(); usingFallback = true;
          }
          rows.forEach(checkRecord);
          for (const row of rows) if (!seen.has(row.id)) { $('recordsGrid').insertAdjacentHTML('beforeend', recordCard(row)); seen.add(row.id); loaded++; }
          cursor = next;
          $('moreRecords').hidden = !cursor;
          $('recordsMessage').textContent = usingFallback ? '保存済みの棋譜を表示しています。最新の一覧は再読み込みして確認してください。' : (loaded ? `${loaded}局を表示` : 'まだ作成された棋譜はありません。');
        } catch { $('recordsMessage').textContent = '続きを読み込めませんでした。もう一度お試しください。'; }
        finally { $('moreRecords').disabled = false; }
      };
      $('moreRecords').onclick = loadPage;
      await loadPage();
    }
  } catch { $('examplesSection').innerHTML = '<p role="status">棋譜を読み込めませんでした。ページを再読み込みしてください。</p>'; }
}
if (libraryMode) { showLibrary(); return; }
renderInput();
const previousResult = load('result');
if (previousResult?.res && /^[XO-]{64}$/.test(previousResult.target)) showResult(previousResult.res, [...previousResult.target], previousResult.secs || 0, false);
const pending = load('job');
if (pending?.id && /^[XO-]{64}$/.test(pending.target) && Number.isFinite(pending.t0) && Number.isFinite(pending.limit)) {
  beginSearch(pending); poll(pending, ++pollVersion);
}
})();
