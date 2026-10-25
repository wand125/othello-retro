// 棋譜復元ページと棋譜プレイヤーで共有する部品:
// オセロの最小限の実装、盤面の描画、返す石のアニメーション、効果音、棋譜の解釈。
"use strict";
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

// ---- f5 開始への正規化 ----
// 初期配置を保つ対称変換で、初手 d3・c4・e6 の棋譜を初手 f5 の形にそろえる（どれも自分自身が逆変換）
const SYMS = {
  f5: { label: "", map: s => s },
  e6: { label: "主対角線（a1–h8）で反転", map: s => (s % 8) * 8 + Math.floor(s / 8) },
  c4: { label: "180° 回転", map: s => 63 - s },
  d3: { label: "反対角線（a8–h1）で反転", map: s => (7 - s % 8) * 8 + (7 - Math.floor(s / 8)) },
};
// 着手の列 → { moves: f5 開始にそろえた列, sym: 使った変換の名前（f5 なら "f5"） }
function normalizeF5(moves) {
  const first = moves.find(m => m !== "pass");
  const sym = SYMS[first] ? first : "f5";
  return { moves: moves.map(m => (m === "pass" ? m : sqName(SYMS[sym].map(nameSq(m))))), sym };
}
const transformBoard = (b, sym) => b.map((_, s) => b[SYMS[sym].map(s)]);

// ---- 盤面の描画 ----
function makeBoard(el, colsEl, rowsEl) {
  colsEl.innerHTML = FILES.split("").map(f => `<span>${f}</span>`).join("");
  rowsEl.innerHTML = [...Array(8)].map((_, i) => `<span>${i + 1}</span>`).join("");
  el.innerHTML = [...Array(64)].map((_, s) => `<div class="cell" data-sq="${s}" aria-label="${sqName(s)}"><div class="disc"></div></div>`).join("");
  return [...el.children];
}
// container の中に座標つきの読み取り専用盤面を作る
function boardInto(container) {
  container.classList.add("board-wrap");
  container.innerHTML = `<div class="cols"></div><div class="rows"></div><div class="board readonly"></div>`;
  return makeBoard(container.querySelector(".board"), container.querySelector(".cols"), container.querySelector(".rows"));
}
function paint(cells, b, marks = {}) {
  cells.forEach((cell, s) => {
    cell.firstChild.className = "disc" + (b[s] === "-" ? "" : " " + b[s]);
    cell.classList.toggle("last", marks.last === s);
    cell.classList.toggle("flipped", !!(marks.flipped && marks.flipped.has(s)));
  });
}
const counts = b => ({ x: b.filter(v => v === "X").length, o: b.filter(v => v === "O").length });

// ---- 設定（このブラウザにだけ保存。保存できない環境でも動く） ----
function pref(key, dflt) {
  try { const v = localStorage.getItem(key); if (v !== null) return v === "1"; } catch (e) {}
  return dflt;
}
// 文字列の保存・読み出し（保存できない環境では何もしない）
function saveStr(key, v) { try { localStorage.setItem(key, v); } catch (e) {} }
function loadStr(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
function setPref(key, on) { try { localStorage.setItem(key, on ? "1" : "0"); } catch (e) {} }
const prefs = {
  anim: pref("othello-retro-anim", !matchMedia("(prefers-reduced-motion: reduce)").matches),
  sound: pref("othello-retro-sound", true),
};
function setAnim(on) { prefs.anim = on; setPref("othello-retro-anim", on); }
function setSound(on) { prefs.sound = on; setPref("othello-retro-sound", on); if (on) audioCtx(); }
// 棋譜を f5 開始にそろえて表示するか
prefs.f5 = pref("othello-retro-f5", true);
function bindF5(box, onchange) { box.checked = prefs.f5; box.onchange = () => { prefs.f5 = box.checked; setPref("othello-retro-f5", box.checked); onchange(); }; }
// 返し方: "all" = 一斉に 1 回で裏返す、"wave" = 置いた石に近い順に 1 個ずつ裏返す
prefs.flipMode = loadStr("othello-retro-flipmode") === "wave" ? "wave" : "all";
function setFlipMode(m) { prefs.flipMode = m === "wave" ? "wave" : "all"; saveStr("othello-retro-flipmode", prefs.flipMode); }
// 返し方の選択欄（select 要素）を設定とつなぐ
function bindFlipMode(sel) { sel.value = prefs.flipMode; sel.onchange = () => setFlipMode(sel.value); }

// ---- 返す石のアニメーション ----
const FLIP_DELAY = 70;  // 置いた石が出てから返し始めるまで
const FLIP_HALF = 140;  // 縮む時間（= 広がる時間）

// 順番に返すときの間隔。prefs.flipGapMs を設定すると固定の間隔になる（動画制作モード用）
const flipGap = n => (prefs.flipMode !== "wave" ? 0 : prefs.flipGapMs != null ? prefs.flipGapMs : Math.min(35, 220 / Math.max(1, n)));
// 返る石の順番（置いた石に近いものから）と、それぞれが返り始めるまでの遅れ（ミリ秒）。
// 一斉なら全部 0。順番なら一定間隔でずらす（多いときは詰めて、自動再生の間隔を崩しにくくする）
function flipSchedule(st) {
  const r0 = Math.floor(st.last / 8), c0 = st.last % 8;
  const dist = s => Math.max(Math.abs(Math.floor(s / 8) - r0), Math.abs(s % 8 - c0));
  const order = [...st.flipped].sort((a, b) => dist(a) - dist(b) || a - b);
  const gap = flipGap(order.length);
  return order.map((s, i) => ({ s, delay: i * gap }));
}

// 置いた石は出現、返る石は前の色で縮んでから新しい色で広がる。view.anim が変わったら中断
function animateStep(view, prev, st) {
  const cells = view.cells, token = view.anim, plan = flipSchedule(st);
  if (st.last !== null) cells[st.last].firstChild.classList.add("pop");
  plan.forEach(({ s }) => { cells[s].firstChild.className = "disc " + prev.b[s]; });
  plan.forEach(({ s, delay }) => {
    setTimeout(() => { if (view.anim === token) cells[s].firstChild.className = "disc " + prev.b[s] + " flip-out"; }, FLIP_DELAY + delay);
    setTimeout(() => { if (view.anim === token) cells[s].firstChild.className = "disc " + st.b[s] + " flip-in"; }, FLIP_DELAY + FLIP_HALF + delay);
  });
  const end = FLIP_DELAY + 2 * FLIP_HALF + 60 + (plan.length ? plan[plan.length - 1].delay : 0);
  setTimeout(() => {
    if (view.anim === token) cells.forEach(c => c.firstChild.classList.remove("pop", "flip-in", "flip-out"));
  }, end);
}

// ---- 効果音（Web Audio で合成。音声ファイルなし） ----
let audio = null, noiseBuf = null;
function audioCtx() {
  if (!audio) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    audio = new AC();
    noiseBuf = audio.createBuffer(1, Math.floor(audio.sampleRate * 0.03), audio.sampleRate);
    const d = noiseBuf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / d.length, 3);
  }
  if (audio.state === "suspended") audio.resume();
  return audio;
}
// 初回の生成は数百ミリ秒かかることがあり、再生 1 手目のアニメーションが詰まる。
// ブラウザは操作をきっかけにしないと音を出せないので、最初の操作の時点で先に作っておく
document.addEventListener("pointerdown", () => { if (prefs.sound) audioCtx(); }, { once: true });
// 音の出力先。普段はスピーカー直結、定位するときは一時的に StereoPanner に差し替える
let OUT = null;
const audioBuses = new WeakMap(), soundSources = new WeakMap();
function audioOutput(ac) {
  if (!audioBuses.has(ac)) { const bus = ac.createGain(); bus.connect(ac.destination); audioBuses.set(ac, bus); }
  return audioBuses.get(ac);
}
function trackSound(ac, source) {
  if (!soundSources.has(ac)) soundSources.set(ac, new Set());
  const set = soundSources.get(ac); set.add(source);
  source.onended = () => { set.delete(source); source.disconnect(); };
}
function stopSoundEffects(ac = audio) {
  if (!ac) return;
  const sources = soundSources.get(ac);
  if (sources) { for (const source of sources) { try { source.stop(); } catch (e) {} } sources.clear(); }
}
const out = ac => OUT || audioOutput(ac);
// スピーカーと同じ効果音（定位も含む）を録画用トラックへ分岐する。
function captureSound() {
  const ac = audioCtx();
  if (!ac || !ac.createMediaStreamDestination) throw new Error("このブラウザでは音声を録画できません。");
  const destination = ac.createMediaStreamDestination(), bus = audioOutput(ac);
  bus.connect(destination);
  // An active, inaudible source preserves leading silence in recorder audio timestamps.
  const clock = ac.createConstantSource(); clock.offset.value = 1e-8; clock.connect(bus); clock.start();
  return { ac, stream: destination.stream, close() {
    clock.stop(); clock.disconnect();
    bus.disconnect(destination); destination.stream.getTracks().forEach(t => t.stop());
  } };
}
// fn の中で鳴らす音を、左右の位置 pan（-1 左 〜 1 右）に置く
function panned(ac, pan, fn) {
  const p = ac.createStereoPanner ? ac.createStereoPanner() : null;
  if (!p) return fn();
  p.pan.value = Math.max(-1, Math.min(1, pan));
  p.connect(audioOutput(ac));
  OUT = p;
  try { fn(); } finally { OUT = null; }
}
const colPan = (s, width) => ((s % 8) - 3.5) / 3.5 * width;  // 盤の列 → 左右の位置

// 音の部品: 減衰する 1 音（波形・音程の変化つき）と、帯域を絞った短いノイズ
function tone(ac, t, { type = "sine", freq, to = freq, dur, vol, attack = 0.004 }) {
  const g = ac.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(vol, t + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  g.connect(out(ac));
  const o = ac.createOscillator();
  o.type = type;
  o.frequency.setValueAtTime(freq, t);
  if (to !== freq) o.frequency.exponentialRampToValueAtTime(to, t + dur);
  o.connect(g); trackSound(ac, o); o.start(t); o.stop(t + dur + 0.02);
}
function noise(ac, t, { freq, q = 1.2, vol, rate = 1 }) {
  // rate を上げるとノイズが速く減衰し、短く鋭いアタックになる
  const n = ac.createBufferSource(), bp = ac.createBiquadFilter(), g = ac.createGain();
  n.buffer = noiseBuf; n.playbackRate.value = rate;
  bp.type = "bandpass"; bp.frequency.value = freq; bp.Q.value = q; g.gain.value = vol;
  n.connect(bp); bp.connect(g); g.connect(out(ac)); trackSound(ac, n); n.start(t);
}

// 音の種類。place = 石を置く音、note = 石を 1 個返す音（f は音程、v は音量）
const SOUNDS = {
  wood: { label: "木の石",
    place: (ac, t) => { tone(ac, t, { freq: 190, to: 105, dur: 0.16, vol: 0.5 }); noise(ac, t, { freq: 760, vol: 0.25 }); },
    note: (ac, t, f, v) => { tone(ac, t, { freq: f, to: f * 0.55, dur: 0.11, vol: v }); noise(ac, t, { freq: f * 4, vol: v * 0.5 }); } },
  // 石を盤に打ちつける「パチッ」: 高い帯域の鋭いアタックを数ミリ秒で切り、ごく短い低音で芯を出す
  snap: { label: "パチッ",
    place: (ac, t) => {
      noise(ac, t, { freq: 3200, q: 2.5, vol: 1.4, rate: 2.2 });
      noise(ac, t, { freq: 1300, q: 1, vol: 0.7, rate: 1.6 });
      tone(ac, t, { freq: 170, to: 90, dur: 0.05, vol: 0.35, attack: 0.001 });
    },
    note: (ac, t, f, v) => {
      noise(ac, t, { freq: f * 3, q: 3, vol: v * 3.2, rate: 2.6 });
      tone(ac, t, { freq: f * 2, dur: 0.025, vol: v * 0.35, attack: 0.001 });
    } },
  // さらに硬く乾いた「カチッ」: ごく短いクリックを 2 つ、わずかにずらして重ねる
  clack: { label: "カチッ",
    place: (ac, t) => {
      noise(ac, t, { freq: 4500, q: 4, vol: 1.6, rate: 3 });
      noise(ac, t + 0.006, { freq: 2600, q: 3, vol: 0.9, rate: 3 });
      tone(ac, t, { freq: 240, to: 160, dur: 0.03, vol: 0.2, attack: 0.001 });
    },
    note: (ac, t, f, v) => {
      noise(ac, t, { freq: f * 4, q: 5, vol: v * 3.5, rate: 3.2 });
      noise(ac, t + 0.004, { freq: f * 2.5, q: 4, vol: v * 1.5, rate: 3.2 });
    } },
  marimba: { label: "マリンバ",
    place: (ac, t) => { tone(ac, t, { freq: 196, dur: 0.32, vol: 0.45 }); tone(ac, t, { freq: 784, dur: 0.05, vol: 0.12 }); },
    note: (ac, t, f, v) => { tone(ac, t, { freq: f / 2, dur: 0.38, vol: v * 1.3 }); tone(ac, t, { freq: f * 2, dur: 0.04, vol: v * 0.35 }); } },
  bell: { label: "ベル",
    place: (ac, t) => { tone(ac, t, { type: "triangle", freq: 330, dur: 0.5, vol: 0.3 }); tone(ac, t, { freq: 330 * 2.76, dur: 0.22, vol: 0.07 }); },
    note: (ac, t, f, v) => {
      tone(ac, t, { freq: f, dur: 0.7, vol: v * 0.8, attack: 0.002 });
      tone(ac, t, { freq: f * 2.76, dur: 0.3, vol: v * 0.22 });
      tone(ac, t, { freq: f * 5.4, dur: 0.12, vol: v * 0.1 });
    } },
  pop: { label: "ポップ",
    place: (ac, t) => tone(ac, t, { freq: 140, to: 320, dur: 0.09, vol: 0.5 }),
    note: (ac, t, f, v) => tone(ac, t, { freq: f * 0.5, to: f * 1.25, dur: 0.08, vol: v * 1.2 }) },
  chip: { label: "8bit",
    place: (ac, t) => { tone(ac, t, { type: "square", freq: 131, dur: 0.07, vol: 0.14 }); tone(ac, t + 0.035, { type: "square", freq: 98, dur: 0.06, vol: 0.12 }); },
    note: (ac, t, f, v) => { tone(ac, t, { type: "square", freq: f, dur: 0.05, vol: v * 0.45 }); tone(ac, t + 0.03, { type: "square", freq: f * 1.5, dur: 0.05, vol: v * 0.35 }); } },
};
prefs.voice = SOUNDS[loadStr("othello-retro-voice")] ? loadStr("othello-retro-voice") : "wood";
// 音の種類の選択欄と試聴ボタンを設定とつなぐ
function bindVoice(sel, btn) {
  sel.innerHTML = Object.entries(SOUNDS).map(([k, v]) => `<option value="${k}">${v.label}</option>`).join("");
  sel.value = prefs.voice;
  sel.onchange = () => { prefs.voice = sel.value; saveStr("othello-retro-voice", sel.value); playPattern(4, true); };
  if (btn) btn.onclick = () => playPattern(4, true);
}

// 一斉: 返す音は 1 回だけ。返した数が多いほど長調の和音（ソ・シ・レ・高いソ）を重ねて厚くする
const CHORD = [783.99, 987.77, 1174.66, 1567.98];
// 順番: 1 個返すごとに長調ペンタトニックで少しずつ上がる（たくさん返すほど駆け上がる）
const PENTA = [659.25, 783.99, 880.0, 1046.5, 1174.66, 1318.51, 1567.98, 1760.0, 2093.0, 2349.32];
// 置く音のあと、n 個返す音を今の返し方・音の種類で鳴らす。force は効果音 OFF でも鳴らす（試聴用）
function playPattern(n, force = false) {
  if (!prefs.sound && !force) return;
  const ac = audioCtx(); if (!ac) return;
  const v = SOUNDS[prefs.voice] || SOUNDS.wood, t0 = ac.currentTime + 0.01, gap = flipGap(n) / 1000;
  v.place(ac, t0);
  if (!n) return;
  const tf = t0 + (FLIP_DELAY + FLIP_HALF) / 1000;  // 色が変わる瞬間
  if (prefs.flipMode === "wave") {
    for (let i = 0; i < n; i++) v.note(ac, tf + i * gap, PENTA[Math.min(i, PENTA.length - 1)], 0.22);
  } else {
    const voices = Math.min(CHORD.length, 1 + Math.floor(Math.log2(n)));
    for (let i = 0; i < voices; i++) v.note(ac, tf + i * 0.008, CHORD[i], 0.24 / Math.sqrt(voices));
  }
}
const playStepSound = st => playPattern(st.flipped.size);

// 定位つきで 1 手分を鳴らす: 置く音は置いた列、返す音は返る石の列に置く（width は左右の広がり 0〜1）
function playStepSoundPanned(st, width, context = null, at = null) {
  if (!prefs.sound) return;
  const ac = context || audioCtx(); if (!ac) return;
  const v = SOUNDS[prefs.voice] || SOUNDS.wood, t0 = at ?? ac.currentTime + 0.01, plan = flipSchedule(st);
  if (st.last !== null) panned(ac, colPan(st.last, width), () => v.place(ac, t0));
  if (!plan.length) return;
  const tf = t0 + (FLIP_DELAY + FLIP_HALF) / 1000;
  if (prefs.flipMode === "wave") {
    plan.forEach(({ s, delay }, i) => panned(ac, colPan(s, width), () => v.note(ac, tf + delay / 1000, PENTA[Math.min(i, PENTA.length - 1)], 0.22)));
  } else {
    const mean = plan.reduce((a, { s }) => a + (s % 8), 0) / plan.length;
    const voices = Math.min(CHORD.length, 1 + Math.floor(Math.log2(plan.length)));
    panned(ac, (mean - 3.5) / 3.5 * width, () => {
      for (let i = 0; i < voices; i++) v.note(ac, tf + i * 0.008, CHORD[i], 0.24 / Math.sqrt(voices));
    });
  }
}

// ---- 1 枚の再生盤面 ----
class BoardView {
  constructor(container, states) {
    this.cells = boardInto(container);
    this.states = states;
    this.k = 0;
    this.anim = 0;
  }
  get last() { return this.states.length - 1; }
  // k 手目を表示。1 手進めたときだけアニメーションと（sound が真なら）効果音
  show(k, sound = true) {
    const prevK = this.k;
    this.k = Math.max(0, Math.min(this.last, k));
    const st = this.states[this.k];
    this.anim++;
    paint(this.cells, st.b, { last: st.last, flipped: st.flipped });
    if (this.k === prevK + 1) {
      if (prefs.anim) animateStep(this, this.states[prevK], st);
      if (sound) playStepSound(st);
    }
  }
}
