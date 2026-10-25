"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const FILES = "abcdefgh", DIRS = [-1, 0, 1].flatMap(r => [-1, 0, 1].map(c => [r, c])).filter(([r,c]) => r || c);
  const INITIAL = [..."---------------------------OX------XO---------------------------"];
  const opposite = c => c === "X" ? "O" : "X";
  const coordinate = s => FILES[s % 8] + (Math.floor(s / 8) + 1);
  const squareOf = move => (Number(move[1]) - 1) * 8 + FILES.indexOf(move[0]);
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const prefix = "othello-retro-short-";
  const save = (key, value) => { try { localStorage.setItem(prefix + key, JSON.stringify(value)); } catch {} };
  const load = key => { try { return JSON.parse(localStorage.getItem(prefix + key)); } catch { return null; } };
  const storedUnreachable = load("unreachable");
  const rejectedBoards = new Set((Array.isArray(storedUnreachable) ? storedUnreachable : []).filter(b => typeof b === "string" && /^[XO-]{64}$/.test(b)).slice(-32));
  const saveRejections = () => save("unreachable", [...rejectedBoards].slice(-32));
  let config = {maxSeconds:300};
  try { config = {...config, ...JSON.parse($("short-config").textContent)}; } catch {}
  const computationLimit = Math.max(1, Math.min(300, Number(config.maxSeconds) || 300));
  const saved = load("board");
  let target = typeof saved === "string" && /^[XO-]{64}$/.test(saved) ? [...saved] : INITIAL.slice();
  const requested = new URLSearchParams(location.search).get("board");
  if (/^[XO-]{64}$/.test(requested || "")) target = [...requested];
  let inputInvalid = false;
  let painting = null, phase = "editing", frames = [], index = 0, speed = 1;
  const nextColor = color => ({"-":"X", "X":"O", "O":"-"})[color];
  let animationToken = 0, pollToken = 0, job = null, leaving = false, elapsedTimer = null, lastStage = "";
  let soundEnabled = load("sound") !== false, audio = null, soundBus = null, noiseBuffer = null, audioFrame = 0;
  const voices = new Set(), pendingFlips = new Map();
  const soundPresets = {
    wood: {label:"木の石", play:(t) => { tone(t,{freq:190,to:105,dur:.16,vol:.5}); noise(t,{freq:760,vol:.25}); }},
    snap: {label:"パチッ", play:(t) => { noise(t,{freq:3200,q:2.5,vol:1.4,rate:2.2}); noise(t,{freq:1300,q:1,vol:.7,rate:1.6}); tone(t,{freq:170,to:90,dur:.05,vol:.35,attack:.001}); }},
    clack: {label:"カチッ", play:(t) => { noise(t,{freq:4500,q:4,vol:1.6,rate:3}); noise(t+.006,{freq:2600,q:3,vol:.9,rate:3}); tone(t,{freq:240,to:160,dur:.03,vol:.2,attack:.001}); }},
    marimba: {label:"マリンバ", play:(t) => { tone(t,{freq:196,dur:.32,vol:.45}); tone(t,{freq:784,dur:.05,vol:.12}); }},
    bell: {label:"ベル", play:(t) => { tone(t,{type:"triangle",freq:330,dur:.5,vol:.3}); tone(t,{freq:330*2.76,dur:.22,vol:.07}); }},
    pop: {label:"ポップ", play:(t) => tone(t,{freq:140,to:320,dur:.09,vol:.5})},
    chip: {label:"8bit", play:(t) => { tone(t,{type:"square",freq:131,dur:.07,vol:.14}); tone(t+.035,{type:"square",freq:98,dur:.06,vol:.12}); }}
  };
  let soundVoice = Object.hasOwn(soundPresets,load("voice")) ? load("voice") : "wood";
  function unlockSound() {
    if (!soundEnabled) return;
    try {
      if (!audio) {
        const Audio = window.AudioContext || window.webkitAudioContext;
        if (!Audio) return;
        audio = new Audio();
        soundBus = audio.createGain(); soundBus.gain.value = .28;
        const compressor = audio.createDynamicsCompressor();
        compressor.threshold.value = -18; compressor.knee.value = 12; compressor.ratio.value = 5;
        compressor.attack.value = .002; compressor.release.value = .08;
        soundBus.connect(compressor); compressor.connect(audio.destination);
        const length = Math.ceil(audio.sampleRate * .03);
        noiseBuffer = audio.createBuffer(1, length, audio.sampleRate);
        const samples = noiseBuffer.getChannelData(0);
        for (let i = 0; i < length; i++) samples[i] = (Math.random() * 2 - 1) * (1 - i / length) ** 3;
        const silent = audio.createBufferSource(); silent.buffer = audio.createBuffer(1,1,audio.sampleRate);
        silent.connect(audio.destination); silent.start();
      }
      if (audio.state === "suspended") audio.resume().catch(() => {});
    } catch { /* Animation remains usable when the browser has no audio output. */ }
  }
  function stopSound() {
    pendingFlips.clear();
    for (const source of voices) { try { source.stop(); } catch {} }
    voices.clear();
  }
  function trackVoice(source, cleanup) {
    voices.add(source);
    source.onended = () => { voices.delete(source); source.disconnect(); cleanup(); };
  }
  function tone(t, {type="sine", freq, to=freq, dur, vol, attack=.004}) {
    const gain=audio.createGain(), source=audio.createOscillator();
    gain.gain.setValueAtTime(.0001,t); gain.gain.exponentialRampToValueAtTime(vol,t+attack); gain.gain.exponentialRampToValueAtTime(.0001,t+dur);
    gain.connect(soundBus); source.type=type; source.frequency.setValueAtTime(freq,t);
    if (to!==freq) source.frequency.exponentialRampToValueAtTime(to,t+dur);
    source.connect(gain); trackVoice(source,()=>gain.disconnect()); source.start(t); source.stop(t+dur+.02);
  }
  function noise(t, {freq,q=1.2,vol,rate=1}) {
    const source=audio.createBufferSource(), filter=audio.createBiquadFilter(), gain=audio.createGain();
    source.buffer=noiseBuffer; source.playbackRate.value=rate; filter.type="bandpass"; filter.frequency.value=freq; filter.Q.value=q; gain.gain.value=vol;
    source.connect(filter); filter.connect(gain); gain.connect(soundBus);
    trackVoice(source,()=>{filter.disconnect();gain.disconnect();}); source.start(t);
  }
  function stoneSound() {
    if (!soundEnabled || !audio || audio.state !== "running" || !noiseBuffer) return;
    soundPresets[soundVoice].play(audio.currentTime);
  }
  function rewindSound(milliseconds) {
    if (!soundEnabled || !audio || audio.state !== "running") return;
    const duration = Math.min(.72,milliseconds/1000), length = Math.ceil(audio.sampleRate * duration);
    const buffer = audio.createBuffer(1,length,audio.sampleRate), samples=buffer.getChannelData(0);
    for (let i=0;i<length;i++) samples[i]=Math.random()*2-1;
    const source=audio.createBufferSource(), filter=audio.createBiquadFilter(), gain=audio.createGain(), t=audio.currentTime;
    source.buffer=buffer; filter.type="bandpass"; filter.Q.value=.65;
    filter.frequency.setValueAtTime(420,t); filter.frequency.exponentialRampToValueAtTime(2200,t+duration*.35); filter.frequency.exponentialRampToValueAtTime(300,t+duration);
    gain.gain.setValueAtTime(.0001,t); gain.gain.exponentialRampToValueAtTime(.5,t+duration*.12); gain.gain.exponentialRampToValueAtTime(.3,t+duration*.42); gain.gain.exponentialRampToValueAtTime(.0001,t+duration);
    source.connect(filter);filter.connect(gain);gain.connect(soundBus);
    trackVoice(source,()=>{filter.disconnect();gain.disconnect();}); source.start(t);
  }
  const cells = Array.from({length:64}, (_, s) => {
    const button = document.createElement("button");
    button.type = "button"; button.className = "cell"; button.dataset.square = s; button.dataset.color = "-";
    button.tabIndex = s === 0 ? 0 : -1;
    const disc = document.createElement("span"); disc.className = "disc"; button.append(disc);
    $("board").append(button); return button;
  });
  cells.forEach((cell, square) => cell.firstChild.addEventListener("transitionend", event => {
    if (event.propertyName !== "transform") return;
    const pending = pendingFlips.get(square);
    if (!pending || pending.frame !== audioFrame || pending.color !== cell.dataset.color) return;
    pendingFlips.delete(square); stoneSound();
  }));
  document.querySelector(".columns").replaceChildren(...[...FILES].map(c => Object.assign(document.createElement("span"), {textContent:c})));
  document.querySelector(".rows").replaceChildren(...Array.from({length:8}, (_,i) => Object.assign(document.createElement("span"), {textContent:i + 1})));

  function flips(board, square, color) {
    if (board[square] !== "-") return [];
    const r0 = Math.floor(square / 8), c0 = square % 8, out = [];
    for (const [dr,dc] of DIRS) {
      let r = r0 + dr, c = c0 + dc; const line = [];
      while (r >= 0 && r < 8 && c >= 0 && c < 8 && board[r*8+c] === opposite(color)) { line.push(r*8+c); r += dr; c += dc; }
      if (line.length && r >= 0 && r < 8 && c >= 0 && c < 8 && board[r*8+c] === color) out.push(...line);
    }
    return out;
  }
  const canPlay = (board, color) => board.some((_, s) => flips(board, s, color).length);
  const CENTER = [27,28,35,36];
  const EDGES = [Array.from({length:8},(_,i)=>i), Array.from({length:8},(_,i)=>56+i), Array.from({length:8},(_,i)=>i*8), Array.from({length:8},(_,i)=>i*8+7)];
  const POW3 = Array.from({length:8},(_,i)=>3**i);
  const edgeStates = (() => {
    const seen = new Uint8Array(6561), stack = [0]; seen[0] = 1;
    while (stack.length) {
      const values = POW3.map(p => Math.floor(stack.at(-1) / p) % 3); stack.pop();
      for (let square = 0; square < 8; square++) for (const color of [1,2]) {
        if (values[square]) continue;
        const next = values.slice(); next[square] = color;
        for (const direction of [-1,1]) {
          let end = square + direction;
          while (end >= 0 && end < 8 && next[end] === 3-color) end += direction;
          if (end >= 0 && end < 8 && next[end] === color) for (let p = square+direction; p !== end; p += direction) next[p] = color;
        }
        const key = next.reduce((s,v,i) => s + v * POW3[i],0);
        if (!seen[key]) { seen[key] = 1; stack.push(key); }
      }
    }
    return seen;
  })();
  function smallReachable(goal) {
    const destination = goal.join(""), stones = goal.filter(c => c !== "-").length;
    if (stones > 10) return true; // Larger boards are checked by the existing exact solver.
    const failed = new Set();
    function visit(board, color, remaining) {
      if (remaining === 0) return board.join("") === destination;
      const key = board.join("") + color; if (failed.has(key)) return false;
      let legal = board.flatMap((_,square) => { const changed = flips(board,square,color); return changed.length ? [{square,changed}] : []; });
      if (!legal.length) {
        color = opposite(color);
        legal = board.flatMap((_,square) => { const changed = flips(board,square,color); return changed.length ? [{square,changed}] : []; });
      }
      for (const {square,changed} of legal) {
        if (goal[square] === "-") continue;
        const next = board.slice(); next[square] = color; for (const s of changed) next[s] = color;
        if (visit(next,opposite(color),remaining-1)) return true;
      }
      failed.add(key); return false;
    }
    return visit(INITIAL.slice(),"X",stones-4);
  }
  function checkInput(board) {
    const required = new Set(CENTER.filter(s => board[s] === "-")), bad = new Set();
    if (required.size) return {ok:false, required, bad};
    const covered = new Uint8Array(64); CENTER.forEach(s => covered[s] = 1);
    for (let changed = true; changed;) {
      changed = false;
      for (let s = 0; s < 64; s++) {
        if (board[s] === "-" || covered[s]) continue;
        const r = Math.floor(s/8), c = s%8;
        if (DIRS.some(([dr,dc]) => { const r2 = r+2*dr,c2=c+2*dc; return r2>=0 && r2<8 && c2>=0 && c2<8 && covered[(r+dr)*8+c+dc] && covered[r2*8+c2]; })) { covered[s] = 1; changed = true; }
      }
    }
    board.forEach((color,s) => { if (color !== "-" && !covered[s]) bad.add(s); });
    for (const edge of EDGES) {
      const key = edge.reduce((n,s,i)=>n+({"-":0,X:1,O:2})[board[s]]*POW3[i],0);
      if (!edgeStates[key]) edge.filter(s=>board[s]!=="-").forEach(s=>bad.add(s));
    }
    for (const s of CENTER) {
      if (board[s] === INITIAL[s]) continue;
      const r=Math.floor(s/8),c=s%8;
      if (![[0,1],[1,0],[1,1],[1,-1]].some(([dr,dc])=>board[(r+dr)*8+c+dc]!=="-" && board[(r-dr)*8+c-dc]!=="-")) bad.add(s);
    }
    return {ok:!bad.size && !rejectedBoards.has(board.join("")) && smallReachable(board), required, bad};
  }
  function buildFrames(moves) {
    if (!Array.isArray(moves) || moves.some(m => typeof m !== "string" || !/^(?:[a-h][1-8]|pass)$/.test(m))) throw Error("棋譜の形式が正しくありません。");
    let board = INITIAL.slice(), color = "X", placements = 0;
    const result = [{board:board.slice(), move:null, mover:null, square:null, placements:0, pass:false}];
    for (const move of moves) {
      if (!canPlay(board, color)) {
        if (!canPlay(board, opposite(color))) throw Error("終局後に手順が続いています。");
        if (move !== "pass") {
          result.push({board:board.slice(), move:"pass", mover:color, square:null, placements, pass:true}); color = opposite(color);
        }
      }
      if (move === "pass") {
        if (canPlay(board, color) || !canPlay(board, opposite(color))) throw Error("合法手がある側のパスはできません。");
        result.push({board:board.slice(), move, mover:color, square:null, placements, pass:true}); color = opposite(color); continue;
      }
      const square = squareOf(move), changed = flips(board, square, color);
      if (!changed.length) throw Error(`${move} は合法な着手ではありません。`);
      board[square] = color; for (const s of changed) board[s] = color;
      result.push({board:board.slice(), move, mover:color, square, placements:++placements, pass:false}); color = opposite(color);
    }
    return result;
  }
  function status(message, error = false) { $("status").textContent = message; $("status").classList.toggle("error", error); }
  function setPhase(next) {
    phase = next; $("film").dataset.phase = next;
    if (["editing", "searching", "found", "rewinding"].includes(next)) stopSound();
    $("film").style.setProperty("--disc-time", (next === "rewinding" ? 65 : next === "editing" ? 130 : 280 / speed) + "ms");
    const editing = next === "editing", searching = next === "searching";
    $("solve-slot").hidden = !editing && !searching;
    $("solve").hidden = !editing;
    $("cancel").hidden = !searching;
    $("settings").hidden = !editing && !searching;
    if (!editing) $("input-error").hidden = true;
    $("edit-controls").hidden = !editing; $("search-controls").hidden = !searching; $("play-controls").hidden = editing || searching;
    const step = editing || searching ? "edit" : next === "rewinding" ? "rewind" : "replay";
    for (const key of ["edit", "rewind", "replay"]) $("step-" + key).classList.toggle("active", key === step);
    for (const cell of cells) cell.disabled = !editing;
    if (!editing) {
      cells.forEach(cell => cell.classList.remove("required", "invalid"));
      $("board").classList.remove("unreachable");
    }
    const running = ["playing", "rewinding", "found"].includes(next);
    $("play").setAttribute("aria-label",running ? "一時停止" : "再生"); $("play").title=running ? "一時停止" : "再生";
    $("play-icon").innerHTML=running ? '<path d="M9 6v12m6-12v12"/>' : '<path d="m9 5 10 7-10 7Z"/>';
    $("eyebrow").textContent = {editing:"END → BEGINNING",searching:"FINDING THE STORY",found:"THE STORY IS FOUND",rewinding:"BACK TO THE BEGINNING",playing:"ONE MOVE AT A TIME",paused:"ONE MOVE AT A TIME",complete:"THE BOARD, RESTORED"}[next];
    $("headline").innerHTML = {editing:"オセロを、<br>巻き戻す。",searching:"はじまりを、<br>探す。",found:"手順が、<br>見つかりました。",rewinding:"時間を、<br>巻き戻す。",playing:"一手ずつ、<br>この盤面へ。",paused:"一手ずつ、<br>この盤面へ。",complete:"この一局が、<br>この盤面に。"}[next];
    $("subtitle").textContent = {editing:"この盤面に至る、一つの物語。",searching:"合法な棋譜を計算しています。",found:"完成した盤面から、初期配置へ。",rewinding:"石の記憶を、たどっていく。",playing:"初期配置から、合法な手順を再生。",paused:"好きなところから、続きを。",complete:"入力した盤面と、64マスすべて一致。"}[next];
    $("footer-label").textContent = next === "editing" ? "試験公開・作成情報は保存／公開されます" : next === "complete" ? "別の盤面にも、別の物語。" : "終わりから、はじまりへ。";
  }
  function draw(board, last = null, animated = true, sonify = false) {
    const generation = ++audioFrame; pendingFlips.clear();
    for (let s = 0; s < 64; s++) {
      const previous = cells[s].dataset.color;
      cells[s].firstChild.classList.toggle("placed",phase !== "editing" && previous === "-" && board[s] !== "-");
      if (sonify && previous !== board[s] && previous !== "-" && board[s] !== "-") {
        if (reducedMotion) queueMicrotask(() => { if (audioFrame === generation) stoneSound(); });
        else pendingFlips.set(s, {frame:generation, color:board[s]});
      }
      const distance = last === null ? 0 : Math.max(Math.abs(s % 8 - last % 8), Math.abs(Math.floor(s / 8) - Math.floor(last / 8)));
      cells[s].style.setProperty("--disc-delay", animated && phase === "playing" && s !== last ? Math.min(distance * 23, 145) / speed + "ms" : "0ms");
      cells[s].dataset.color = board[s]; cells[s].classList.toggle("last", s === last);
      cells[s].setAttribute("aria-label", `${coordinate(s)}：${{"X":"黒","O":"白","-":"空"}[board[s]]}`);
    }
    $("black-count").textContent = board.filter(c => c === "X").length;
    $("white-count").textContent = board.filter(c => c === "O").length;
  }
  function invalidate() { animationToken++; stopSound(); frames = []; index = 0; save("result", null); }
  function updateInput() {
    draw(target); save("board", target.join(""));
    $("position-label").textContent = "目標の盤面"; $("move-badge").textContent = "TARGET";
    const check = checkInput(target);
    cells.forEach((cell,s) => { cell.classList.toggle("required",check.required.has(s)); cell.classList.remove("invalid"); });
    $("board").classList.remove("unreachable");
    $("board").setAttribute("aria-invalid", String(!check.ok));
    inputInvalid = !check.ok;
    $("solve").disabled = false;
    $("solve").classList.toggle("reset-action", inputInvalid);
    const label = inputInvalid ? "初期配置にリセット" : "計算開始";
    $("solve").setAttribute("aria-label", label); $("solve").title = label; $("solve-label").textContent = label;
    $("solve").querySelector(".rewind-icon").toggleAttribute("hidden", inputInvalid);
    $("solve").querySelector(".reset-icon").toggleAttribute("hidden", !inputInvalid);
    $("input-error").hidden = !inputInvalid;
    status("");
  }
  function place(square, value = nextColor(target[square])) {
    if (phase !== "editing") return;
    if (target[square] === value) return;
    invalidate(); target[square] = value; updateInput();
  }
  $("board").addEventListener("pointerdown", event => {
    const cell = event.target.closest("[data-square]");
    if (!cell || phase !== "editing" || event.button > 0) return;
    painting = nextColor(target[+cell.dataset.square]); place(+cell.dataset.square, painting); $("board").setPointerCapture(event.pointerId);
  });
  $("board").addEventListener("pointermove", event => {
    if (painting === null) return;
    const cell = document.elementFromPoint(event.clientX,event.clientY)?.closest("#board [data-square]");
    if (cell) place(+cell.dataset.square, painting);
  });
  for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) $("board").addEventListener(name, () => painting = null);
  $("board").addEventListener("click", event => {
    const cell = event.target.closest("[data-square]"); if (cell && event.detail === 0) place(+cell.dataset.square);
  });
  $("board").addEventListener("keydown", event => {
    if (phase !== "editing") return;
    const cell = event.target.closest("[data-square]"); if (!cell) return;
    const change = {ArrowLeft:-1, ArrowRight:1, ArrowUp:-8, ArrowDown:8}[event.key];
    if (!change) return; event.preventDefault();
    const next = Math.max(0, Math.min(63, +cell.dataset.square + change));
    cells.forEach(c => c.tabIndex = -1); cells[next].tabIndex = 0; cells[next].focus();
  });
  function showFrame(next, sonify = false) {
    if (!frames.length) return;
    index = Math.max(0, Math.min(frames.length - 1, next)); const frame = frames[index];
    draw(frame.board, frame.square, true, sonify);
    $("position-label").textContent = frame.pass ? `${frame.mover === "X" ? "黒" : "白"}はパス` : index ? `${frame.mover === "X" ? "黒" : "白"} ${frame.move}` : "初期配置";
    $("move-badge").textContent = frame.pass ? "PASS" : index ? `${frame.placements}手目` : "START";
    $("seek").value = index; $("ply").textContent = `${frame.placements} / ${frames.at(-1).placements}`;
    $("prev").disabled = $("restart").disabled = index === 0; $("next").disabled = $("last").disabled = index === frames.length - 1;
  }
  function stopAnimation() { animationToken++; stopSound(); if (frames.length) { setPhase("paused"); status("一時停止中です。手送りやシークでも確認できます。"); } }
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  async function forward(token) {
    setPhase("playing");
    status("合法な棋譜を、一手ずつ再生しています。");
    while (token === animationToken && index < frames.length - 1 && !leaving) {
      showFrame(index + 1, true);
      await wait(450 / speed);
    }
    if (token === animationToken && !leaving) { setPhase("complete"); status("合法な棋譜を再生しました。入力した盤面と一致しています。"); }
  }
  async function sequence() {
    const token = ++animationToken;
    showFrame(frames.length - 1); setPhase("found"); status("棋譜が見つかりました。初期配置へ巻き戻して再生します。");
    await wait(reducedMotion ? 250 : 800);
    if (token !== animationToken || leaving) return;
    await rewindAndPlay(token);
  }
  async function rewindAndPlay(token) {
    setPhase("rewinding");
    if (!reducedMotion && index > 0) rewindSound(index * Math.max(24, Math.min(65, 1900 / frames.length)));
    status("初期配置へ巻き戻しています。");
    if (reducedMotion) showFrame(0);
    else while (index > 0 && token === animationToken && !leaving) { showFrame(index - 1); await wait(Math.max(24, Math.min(65, 1900 / frames.length))); }
    if (token !== animationToken || leaving) return;
    stopSound(); setPhase("paused"); await wait(600);
    if (token !== animationToken || leaving) return;
    if (reducedMotion) { status("初期配置に戻しました。盤面をタップすると一手ずつ進みます。"); return; }
    await forward(token);
  }
  function accept(result, pending, animate = true) {
    try {
      const built = buildFrames(result.moves);
      if (built.at(-1).board.join("") !== pending.target) throw Error("棋譜が入力した盤面と一致しません。");
      if (rejectedBoards.delete(pending.target)) saveRejections();
      remember(result,pending);
      frames = built; index = built.length - 1; $("seek").max = index;
      save("result", {moves:result.moves, target:pending.target, seconds:result.time});
      if (animate) sequence(); else { setPhase("paused"); showFrame(index); status("保存された棋譜を再生できます。"); }
    } catch (error) { invalidate(); setPhase("editing"); updateInput(); status(`結果を確認できませんでした。${error.message}`, true); }
  }
  function togglePlayback() {
    if (!frames.length) return;
    if (["playing", "rewinding", "found"].includes(phase)) { stopAnimation(); return; }
    unlockSound();
    if (index === frames.length - 1) { sequence(); return; }
    forward(++animationToken);
  }
  $("play").onclick = togglePlayback;
  $("film").addEventListener("click", event => {
    if (phase === "editing" || phase === "searching" || event.target.closest("button, input, a")) return;
    togglePlayback();
  });
  $("prev").onclick = () => { stopAnimation(); showFrame(index - 1); };
  $("next").onclick = () => { stopAnimation(); unlockSound(); showFrame(index + 1, true); };
  $("restart").onclick = () => { stopAnimation(); showFrame(0); };
  $("last").onclick = () => { stopAnimation(); showFrame(frames.length - 1); };
  $("seek").oninput = () => { stopAnimation(); showFrame(+$("seek").value); };
  $("speed").onclick = () => { speed = speed === 1 ? 2 : speed === 2 ? .5 : 1; $("speed").textContent = `${speed}×`; if (phase === "playing") $("film").style.setProperty("--disc-time", 280 / speed + "ms"); };
  let sessionResume = null, libraryVersion = 0, recordCursor = null;
  function closeSession() { sessionResume = null; $("session-dialog").close(); }
  $("reset-board").onclick = () => {
    sessionResume = phase; animationToken++; stopSound();
    if (["playing","found","rewinding"].includes(phase)) setPhase("paused");
    $("session-choices").hidden=false; $("session-library").hidden=true; $("session-dialog").showModal();
  };
  $("session-dialog").addEventListener("close",() => {
    libraryVersion++;
    const resume=sessionResume; sessionResume=null;
    if (resume==="playing") forward(++animationToken);
    else if (resume==="rewinding") rewindAndPlay(++animationToken);
    else if (resume==="found") sequence();
  });
  $("new-session").onclick=()=>{closeSession();replaceBoard(INITIAL.slice());};
  $("edit-board").onclick=()=>replaceBoard(frames[index]?.board.slice() || target.slice());
  const historyKey = record => record.target + "|" + record.moves.join(",");
  function getHistory() {
    const rows=load("history");
    return (Array.isArray(rows)?rows:[]).filter(r=>r && /^[XO-]{64}$/.test(r.target||"") && Array.isArray(r.moves) && r.moves.length<=120).slice(0,32);
  }
  function remember(result,pending) {
    const row={target:pending.target,moves:result.moves,seconds:result.time,created:Date.now()}, key=historyKey(row), previous=getHistory();
    if (previous.some(r=>historyKey(r)===key)) return;
    save("history",[row,...previous].slice(0,32));
  }
  function recordChoice(row,local=false) {
    const board=local?row.target:row.board, moves=row.moves;
    if (!/^[XO-]{64}$/.test(board||"") || !Array.isArray(moves) || moves.length>120) return null;
    const button=document.createElement("button");button.type="button";button.className="record-choice";
    const preview=document.createElement("span");preview.className="record-preview";preview.setAttribute("aria-hidden","true");
    for(const color of board){const cell=document.createElement("i");cell.dataset.color=color;preview.append(cell);}
    const caption=document.createElement("span");caption.className="record-caption";
    const title=document.createElement("span");title.textContent=local?`${[...board].filter(c=>c!=="-").length}石の盤面`:String(row.title||"作成された棋譜");
    const info=document.createElement("small");const seconds=local?row.seconds:row.elapsed_seconds;
    info.textContent=`${moves.filter(m=>m!=="pass").length}手`+(Number.isFinite(seconds)?` · ${seconds.toLocaleString("ja-JP",{maximumFractionDigits:3})}秒`:"");
    caption.append(title,info);button.append(preview,caption);
    button.onclick=()=>{
      try {
        const built=buildFrames(moves);if(built.at(-1).board.join("")!==board)throw Error();
        closeSession();invalidate();target=[...board];save("board",board);accept({moves,time:seconds},{target:board});
      } catch {$("library-status").textContent="この棋譜を読み込めませんでした。";}
    };
    return button;
  }
  async function loadRecords(version,append=false) {
    $("more-records").disabled=true;$("library-status").textContent="読み込み中…";
    try {
      let rows,next=null;
      try {const response=await fetch("/api/records"+(recordCursor?"?cursor="+encodeURIComponent(recordCursor):""));if(!response.ok)throw Error();const payload=await response.json();if(!Array.isArray(payload.records))throw Error();rows=payload.records;next=typeof payload.next_cursor==="string"?payload.next_cursor:null;}
      catch {if(append)throw Error();const response=await fetch("/public-examples.json");if(!response.ok)throw Error();rows=(await response.json()).examples;if(!Array.isArray(rows))throw Error();}
      if(version!==libraryVersion || !$("session-dialog").open)return;
      if(!append)$("public-records").replaceChildren();
      for(const row of rows){const button=recordChoice(row);if(button)$("public-records").append(button);}
      recordCursor=next;$("more-records").hidden=!next;$("library-status").textContent=$("public-records").children.length?"":"まだ作成された棋譜はありません。";
    }catch{if(version===libraryVersion)$("library-status").textContent="棋譜を読み込めませんでした。";}
    finally{if(version===libraryVersion)$("more-records").disabled=false;}
  }
  $("load-session").onclick=()=>{
    $("session-choices").hidden=true;$("session-library").hidden=false;$("local-records").replaceChildren();
    for(const row of getHistory()){const button=recordChoice(row,true);if(button)$("local-records").append(button);}
    if(!$("local-records").children.length)$("local-records").textContent="まだありません。";
    recordCursor=null;$("more-records").hidden=true;loadRecords(++libraryVersion);
  };
  $("more-records").onclick=()=>loadRecords(libraryVersion,true);
  function updateSoundButton() {
    $("sound").setAttribute("aria-pressed", String(soundEnabled));
    $("sound").setAttribute("aria-label", soundEnabled ? "音を消す" : "音を鳴らす");
    $("sound").title = soundEnabled ? "音を消す" : "音を鳴らす";
    $("sound-toggle").setAttribute("aria-pressed",String(soundEnabled)); $("sound-toggle").textContent = soundEnabled ? "ON" : "OFF";
    $("sound-icon").innerHTML = soundEnabled ? '<path d="M11 5 6 9H3v6h3l5 4ZM15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>' : '<path d="M11 5 6 9H3v6h3l5 4ZM16 9l5 6m0-6-5 6"/>';
  }
  function toggleSound() {
    soundEnabled = !soundEnabled; save("sound", soundEnabled);
    if (soundEnabled) unlockSound(); else stopSound(); updateSoundButton();
  }
  $("sound").onclick = $("sound-toggle").onclick = toggleSound;
  for (const [voice,preset] of Object.entries(soundPresets)) {
    const button = document.createElement("button"); button.type="button"; button.className="toggle-button"; button.dataset.voice=voice; button.textContent=preset.label; button.setAttribute("aria-pressed",String(voice===soundVoice));
    button.onclick = () => {
      soundVoice=voice; save("voice",voice); stopSound(); $("voice-settings").title = "音色：" + preset.label;
      for (const option of $("voice-options").children) option.setAttribute("aria-pressed",String(option.dataset.voice===voice));
      unlockSound(); stoneSound();
    };
    $("voice-options").append(button);
  }
  $("settings").onclick = $("voice-settings").onclick = () => $("settings-dialog").showModal();
  function replaceBoard(next) { if (job) return; invalidate(); target = next; setPhase("editing"); updateInput(); }
  function stage(message, progress) {
    lastStage = message;
    let text = message === "queued" ? "計算の順番を待っています" : "合法な手順を探しています";
    const tag = String(progress?.stage || message || "");
    if (/beam|model|guid/.test(tag)) text = "逆向きの候補を絞っています";
    else if (/sat|solv/.test(tag)) text = "手順の条件を確認しています";
    $("search-text").textContent = text;
  }
  function begin(pending) {
    animationToken++; job = pending; save("job", pending); setPhase("searching"); draw([...pending.target]);
    $("position-label").textContent = "この配置を計算中"; $("move-badge").textContent = "SEARCH";
    $("cancel").disabled = false; stage("queued"); status("計算が完了したら、巻き戻しと一手ずつの再生が始まります。");
    const tick = () => $("elapsed").textContent = `${Math.max(0, Math.floor((Date.now() - pending.started) / 1000))}秒`;
    clearInterval(elapsedTimer); tick(); elapsedTimer = setInterval(tick,1000);
  }
  function finish(pending, result) {
    if (job?.id !== pending.id || leaving) return;
    clearInterval(elapsedTimer); job = null; save("job", null);
    if (result.status === "found") { accept(result,pending); return; }
    if (result.status === "unreachable") { rejectedBoards.add(pending.target); saveRejections(); }
    setPhase("editing"); updateInput();
    if (result.status === "unreachable") return;
    const messages = {unknown:"5分以内に棋譜が見つかりませんでした。",cancelled:"計算を中止しました。盤面を編集できます。",error:result.reason || result.error || "計算に接続できませんでした。もう一度お試しください。"};
    status(messages[result.status] || messages.error, result.status !== "cancelled");
  }
  async function poll(pending, version) {
    while (!leaving && job?.id === pending.id && version === pollToken) {
      try {
        const response = await fetch("/api/result?id=" + encodeURIComponent(pending.id));
        if (response.ok) {
          const result = await response.json();
          if (result.status === "running") {
            stage(result.stage);
            try { const p = await fetch("/api/progress?id=" + encodeURIComponent(pending.id)); if (p.ok) stage(result.stage,await p.json()); } catch {}
          } else if (result.status !== "lost" || Date.now() - pending.started > 15000) {
            finish(pending, result.status === "lost" ? {status:"error",reason:"計算の記録が見つかりません。もう一度お試しください。"} : result); return;
          }
        } else if ([400,403,404].includes(response.status)) { finish(pending,{status:"error",reason:"計算の記録を確認できません。もう一度お試しください。"}); return; }
      } catch { $("search-text").textContent = "接続を確認しています"; }
      await wait(1000);
    }
  }
  $("solve").onclick = async () => {
    if (job || $("solve").disabled) return;
    if (inputInvalid) { replaceBoard(INITIAL.slice()); return; }
    unlockSound();
    invalidate();
    const pending = {id:crypto.randomUUID().replaceAll("-",""),target:target.join(""),limit:computationLimit,started:Date.now()};
    begin(pending); const version = ++pollToken;
    try {
      const response = await fetch("/api/solve",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:pending.id,board:pending.target,time:pending.limit})});
      const result = await response.json();
      if (!response.ok) { finish(pending,{status:"error",reason:result.reason || result.error}); return; }
      if (result.status !== "queued" && result.status !== "running") { finish(pending,result); return; }
    } catch { $("search-text").textContent = "計算の受付を確認しています"; }
    await poll(pending,version);
  };
  $("cancel").onclick = async () => {
    if (!job) return; $("cancel").disabled = true;
    try {
      const response = await fetch("/api/cancel",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:job.id})});
      if (!response.ok) throw Error(); $("search-text").textContent = "中止しています";
    } catch { $("cancel").disabled = false; status("中止を送信できませんでした。もう一度お試しください。",true); }
  };
  addEventListener("pagehide",() => { leaving = true; animationToken++; pollToken++; stopSound(); clearInterval(elapsedTimer); if (audio?.state === "running") audio.suspend().catch(() => {}); });
  addEventListener("pageshow",event => {
    if (event.persisted) { leaving = false; if (job) { begin(job); poll(job,++pollToken); } }
  });
  if (reducedMotion) $("film").classList.add("no-motion");
  $("voice-settings").title = "音色：" + soundPresets[soundVoice].label;
  updateSoundButton();
  setPhase("editing"); updateInput();
  const pending = load("job"), result = load("result");
  if (pending && /^[a-zA-Z0-9_-]{1,100}$/.test(pending.id || "") && /^[XO-]{64}$/.test(pending.target || "") && Number.isFinite(pending.started)) {
    target = [...pending.target]; begin(pending); poll(pending,++pollToken);
  } else if (result?.target === target.join("")) accept({moves:result.moves},result,false);
  document.documentElement.dataset.shortReady = "true";
})();
