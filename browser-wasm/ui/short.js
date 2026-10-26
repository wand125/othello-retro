"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const FILES = "abcdefgh", DIRS = [-1, 0, 1].flatMap(r => [-1, 0, 1].map(c => [r, c])).filter(([r,c]) => r || c);
  const INITIAL = [..."---------------------------OX------XO---------------------------"];
  const EMPTY=Array(64).fill("-");
  const opposite = c => c === "X" ? "O" : "X";
  const coordinate = s => FILES[s % 8] + (Math.floor(s / 8) + 1);
  const squareOf = move => (Number(move[1]) - 1) * 8 + FILES.indexOf(move[0]);
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const prefix = "othello-retro-browser-";
  const save = (key, value) => { try { localStorage.setItem(prefix + key, JSON.stringify(value)); } catch {} };
  const load = key => { try { return JSON.parse(localStorage.getItem(prefix + key)); } catch { return null; } };
  const storedUnreachable = load("unreachable");
  const rejectedBoards = new Set((Array.isArray(storedUnreachable) ? storedUnreachable : []).filter(b => typeof b === "string" && /^[XO-]{64}$/.test(b)).slice(-32));
  const saveRejections = () => save("unreachable", [...rejectedBoards].slice(-32));
  const saved = load("board");
  let target = typeof saved === "string" && /^[XO-]{64}$/.test(saved) ? [...saved] : EMPTY.slice();
  const sharedParams = new URLSearchParams(location.search);
  const requested = sharedParams.get("board"), sharedMoves = sharedParams.get("moves"), sharedCode = sharedParams.get("r");
  if (/^[XO-]{64}$/.test(requested || "")) target = [...requested];
  let inputInvalid = false;
  let painting = null, phase = "editing", frames = [], index = 0, speed = 1;
  const nextColor = color => ({"-":"X", "X":"O", "O":"-"})[color];
  let animationToken = 0, pollToken = 0, job = null, leaving = false, elapsedTimer = null, lastStage = "";
  let soundEnabled = load("sound") !== false, audio = null, soundBus = null, noiseBuffer = null;
  let audioOutput = load("output") === "recording" ? "recording" : "standard";
  let renderEngine = null, mediaPlayer = null, mediaToken = 0, mediaTimeline = false, mediaFailed = false;
  const mediaClips = new Map();
  const voices = new Set();
  const PENTA=[659.25,783.99,880,1046.5,1174.66,1318.51,1567.98,1760,2093,2349.32];
  const soundPresets={
    snap:{label:"パチッ",place:t=>dryStoneSound(t,"place"),note:(t,f,v)=>dryStoneSound(t,"flip",Math.min(1.65,Math.sqrt(f/PENTA[0])),v/.22),remove:(t,p)=>dryStoneSound(t,"remove",.9+.3*p,.85)},
    marimba:{label:"マリンバ",place:t=>{tone(t,{freq:196,dur:.32,vol:.45});tone(t,{freq:784,dur:.05,vol:.12});},note:(t,f,v)=>{tone(t,{freq:f/2,dur:.38,vol:v*1.3});tone(t,{freq:f*2,dur:.04,vol:v*.35});},remove:(t,p)=>{const f=PENTA[Math.round(p*(PENTA.length-1))];tone(t,{freq:f/2,dur:.085,vol:.17});tone(t,{freq:f*2,dur:.012,vol:.045});}},
    chip:{label:"8bit",place:t=>{tone(t,{type:"square",freq:131,dur:.07,vol:.14});tone(t+.035,{type:"square",freq:98,dur:.06,vol:.12});},note:(t,f,v)=>{tone(t,{type:"square",freq:f,dur:.05,vol:v*.45});tone(t+.03,{type:"square",freq:f*1.5,dur:.05,vol:v*.35});},remove:(t,p)=>{const f=PENTA[Math.round(p*(PENTA.length-1))];tone(t,{type:"square",freq:f/2,dur:.025,vol:.065});tone(t+.012,{type:"square",freq:f*.75,dur:.018,vol:.045});}}
  };
  // Keep explicit preferences from either UI; a fresh browser starts with wood.
  soundPresets.wood={label:"木の石",place:t=>{tone(t,{freq:190,to:105,dur:.16,vol:.5});noise(t,{freq:760,vol:.25});},note:(t,f,v)=>{tone(t,{freq:f,to:f*.55,dur:.11,vol:v});noise(t,{freq:f*4,vol:v*.5});},remove:(t,p)=>{tone(t,{freq:240+180*p,to:150,dur:.035,vol:.12});noise(t,{freq:1300,vol:.12,rate:2});}};
  soundPresets.pop={label:"ポップ",place:t=>tone(t,{freq:140,to:320,dur:.09,vol:.5}),note:(t,f,v)=>tone(t,{freq:f*.5,to:f*1.25,dur:.08,vol:v*1.2}),remove:(t,p)=>tone(t,{freq:220+300*p,to:110,dur:.03,vol:.09})};
  soundPresets.bell={label:"ベル",place:t=>{tone(t,{type:"triangle",freq:330,dur:.5,vol:.3});tone(t,{freq:910.8,dur:.22,vol:.07});},note:(t,f,v)=>{tone(t,{freq:f,dur:.7,vol:v*.8,attack:.002});tone(t,{freq:f*2.76,dur:.3,vol:v*.22});},remove:(t,p)=>tone(t,{freq:440+440*p,dur:.04,vol:.08})};
  soundPresets.clack={...soundPresets.snap,label:"カチッ"};
  function oldPreference(key){try{const short=localStorage.getItem("othello-retro-short-"+key);if(short!==null)return JSON.parse(short);const common=localStorage.getItem("othello-retro-"+key);if(common!==null){try{return JSON.parse(common);}catch{return common;}}}catch{}return null;}
  const savedSound=load("sound") ?? oldPreference("sound");
  if(savedSound===false)soundEnabled=false;
  const soundPattern="wave",preferredVoice=load("voice") ?? oldPreference("voice");
  let soundVoice=Object.hasOwn(soundPresets,preferredVoice)?preferredVoice:"wood";
  function unlockSound() {
    if (!soundEnabled) return;
    if(audioOutput==="recording" && !mediaFailed){
      // Keep this route entirely outside the live Web Audio output session.
      // Offline rendering does not create an output device or an active session.
      if(audio){const old=audio;audio=null;soundBus=null;noiseBuffer=null;old.close().catch(()=>{});}
      try{if(navigator.audioSession)navigator.audioSession.type="auto";}catch{}
      primeMediaPlayer();return Promise.resolve();
    }
    try {
      try { if (navigator.audioSession) navigator.audioSession.type = "playback"; } catch {}
      if (!audio || audio.state === "closed") {
        const Audio = window.AudioContext || window.webkitAudioContext;
        if (!Audio) return;
        audio = new Audio({latencyHint:"interactive"});
        soundBus=audio.createGain();soundBus.gain.value=1;soundBus.connect(audio.destination);
        const length = Math.ceil(audio.sampleRate * .03);
        noiseBuffer = audio.createBuffer(1, length, audio.sampleRate);
        const samples = noiseBuffer.getChannelData(0);
        for (let i = 0; i < length; i++) samples[i] = (Math.random() * 2 - 1) * (1 - i / length) ** 3;
        const silent = audio.createBufferSource(); silent.buffer = audio.createBuffer(1,1,audio.sampleRate);
        silent.connect(audio.destination); silent.start();
      }
      const silent = audio.createBufferSource(); silent.buffer=audio.createBuffer(1,1,audio.sampleRate); silent.connect(audio.destination); silent.start();
      if (audio.state !== "running") return audio.resume().catch(() => {});
      return Promise.resolve();
    } catch { /* Animation remains usable when the browser has no audio output. */ }
  }
  for (const name of ["pointerdown","touchend","click"]) document.addEventListener(name,event=>{
    if(event.isTrusted && soundEnabled && event.target.closest?.("#film,.panel,#settings-dialog")) unlockSound();
  },{capture:true,passive:true});
  document.addEventListener("dblclick",event=>{if(event.cancelable)event.preventDefault();},{passive:false});
  function stopSound() {
    mediaToken++; mediaTimeline = false;
    if (mediaPlayer) mediaPlayer.pause();
    for (const source of voices) { try { source.stop(); } catch {} }
    voices.clear();
  }
  function trackVoice(source, cleanup) {
    voices.add(source);
    source.onended = () => { voices.delete(source); source.disconnect(); cleanup(); };
  }
  function tone(t, {type="sine", freq, to=freq, dur, vol, attack=.004}) {
    const context=renderEngine?.context || audio, bus=renderEngine?.bus || soundBus;
    const gain=context.createGain(), source=context.createOscillator();
    gain.gain.setValueAtTime(.0001,t); gain.gain.exponentialRampToValueAtTime(vol,t+attack); gain.gain.exponentialRampToValueAtTime(.0001,t+dur);
    gain.connect(bus); source.type=type; source.frequency.setValueAtTime(freq,t);
    if (to!==freq) source.frequency.exponentialRampToValueAtTime(to,t+dur);
    source.connect(gain); if(!renderEngine)trackVoice(source,()=>gain.disconnect()); source.start(t); source.stop(t+dur+.02);
  }
  function noise(t, {freq,q=1.2,vol,rate=1}) {
    const context=renderEngine?.context || audio, bus=renderEngine?.bus || soundBus;
    const source=context.createBufferSource(), filter=context.createBiquadFilter(), gain=context.createGain();
    source.buffer=renderEngine?.noise || noiseBuffer; source.playbackRate.value=rate; filter.type="bandpass"; filter.frequency.value=freq; filter.Q.value=q; gain.gain.value=vol;
    source.connect(filter); filter.connect(gain); gain.connect(bus);
    if(!renderEngine)trackVoice(source,()=>{filter.disconnect();gain.disconnect();}); source.start(t);
  }
  function planStep(t,count,voice=soundVoice) {
    const preset=soundPresets[voice];preset.place(t);
    for(let i=0;i<count;i++)preset.note(t+.21+i*Math.min(35,220/Math.max(1,count))/1000,PENTA[Math.min(i,PENTA.length-1)],.22);
  }
  function classicStepSound(count) {
    if(mediaTimeline)return;
    if(soundEnabled && audioOutput==="recording" && !mediaFailed){
      playMediaClip(renderMediaClip("step|"+soundVoice+"|"+count,.95,()=>planStep(.01,count)));return;
    }
    if(!soundEnabled || !audio || audio.state!=="running")return;
    planStep(audio.currentTime+.01,count);
  }
  function dryStoneSound(t,kind="remove",pitch=1,level=1) {
    const c={place:{pitch:1,duration:.008,rate:2.6,level:1},flip:{pitch:1.08,duration:.006,rate:3.1,level:.4},remove:{pitch:1.18,duration:.005,rate:3.5,level:.7}}[kind];
    noise(t,{freq:3300*c.pitch*pitch,q:2,vol:.95*c.level*level,rate:c.rate});noise(t,{freq:1550*c.pitch*pitch,q:1,vol:.3*c.level*level,rate:c.rate*1.15});tone(t,{type:"triangle",freq:1450*c.pitch*pitch,to:1000*c.pitch*pitch,dur:c.duration,vol:.035*c.level*level,attack:.0004});
  }
  function removalSound(progress=null,at=audio?.currentTime) {
    if(mediaTimeline)return;
    if(!soundEnabled || !audio || audio.state!=="running" || !noiseBuffer)return;
    const ratio=progress ?? ((frames.at(-1)?.placements||0)?frames[index].placements/frames.at(-1).placements:0);
    soundPresets[soundVoice].remove(at,Math.max(0,Math.min(1,ratio)));
  }
  function previewPattern(){
    if(soundEnabled && audioOutput==="recording" && !mediaFailed){
      playMediaClip(renderMediaClip("preview|"+soundVoice,1.25,()=>{planStep(.01,4);for(let i=0;i<5;i++)soundPresets[soundVoice].remove(.85+i*.045,1-i/4);}));return;
    }
    if(!soundEnabled || !audio || audio.state!=="running")return;
    classicStepSound(4);const t=audio.currentTime+.85;for(let i=0;i<5;i++)removalSound(1-i/4,t+i*.045);
  }
  // Render the existing instruments unchanged, then use the ordinary media-file
  // output path. No microphone, recording permission, stream relay or upload.
  function wavBlob(samples,rate=48000) {
    const bytes=new ArrayBuffer(44+samples.length*2),view=new DataView(bytes);
    const text=(offset,value)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i));};
    text(0,"RIFF");view.setUint32(4,36+samples.length*2,true);text(8,"WAVE");text(12,"fmt ");view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,rate,true);view.setUint32(28,rate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,"data");view.setUint32(40,samples.length*2,true);
    for(let i=0;i<samples.length;i++){const v=Math.max(-1,Math.min(1,samples[i]));view.setInt16(44+i*2,Math.round(v*(v<0?32768:32767)),true);}
    return new Blob([bytes],{type:"audio/wav"});
  }
  function primeMediaPlayer() {
    if(!mediaPlayer){
      mediaPlayer=document.createElement("audio");mediaPlayer.preload="auto";mediaPlayer.setAttribute("playsinline","");mediaPlayer.setAttribute("webkit-playsinline","");mediaPlayer.setAttribute("aria-hidden","true");mediaPlayer.hidden=true;mediaPlayer.dataset.shortAudio="recording";
      mediaPlayer.src=URL.createObjectURL(wavBlob(new Float32Array(2400)));document.body.append(mediaPlayer);
      mediaPlayer.dataset.primer="true";
    }
    if(mediaPlayer.dataset.primer==="true")mediaPlayer.play().catch(()=>{});
  }
  function renderMediaClip(key,duration,schedule) {
    if(mediaClips.has(key))return mediaClips.get(key);
    const promise=(async()=>{
      const Offline=window.OfflineAudioContext || window.webkitOfflineAudioContext;
      if(!Offline)throw Error("offline audio unavailable");
      const context=new Offline(1,Math.ceil(duration*48000),48000),bus=context.createGain(),noise=context.createBuffer(1,1440,48000);
      bus.connect(context.destination);
      const samples=noise.getChannelData(0);for(let i=0;i<samples.length;i++)samples[i]=(Math.random()*2-1)*(1-i/samples.length)**3;
      renderEngine={context,bus,noise};try{schedule();}finally{renderEngine=null;}
      const buffer=await context.startRendering();
      return {url:URL.createObjectURL(wavBlob(buffer.getChannelData(0))),duration:buffer.duration};
    })();
    mediaClips.set(key,promise);
    promise.catch(()=>{if(mediaClips.get(key)===promise)mediaClips.delete(key);});
    while(mediaClips.size>8){const first=mediaClips.keys().next().value,old=mediaClips.get(first);mediaClips.delete(first);old.then(clip=>{if(clip.url!==mediaPlayer?.src)URL.revokeObjectURL(clip.url);}).catch(()=>{});}
    return promise;
  }
  async function playMediaClip(promise,offset=0,valid=()=>true,timeline=false) {
    const ticket=++mediaToken;
    try{
      const clip=await promise;
      if(ticket!==mediaToken || !valid() || !soundEnabled || audioOutput!=="recording")return null;
      primeMediaPlayer();mediaPlayer.pause();delete mediaPlayer.dataset.primer;
      mediaPlayer.src=clip.url;
      // Safari may reject seeking a newly assigned URL before metadata arrives.
      if(offset>0 && mediaPlayer.readyState<1)await new Promise((resolve,reject)=>{
        const finish=error=>{clearTimeout(timer);mediaPlayer.removeEventListener("loadedmetadata",ready);mediaPlayer.removeEventListener("error",failed);error?reject(error):resolve();};
        const ready=()=>finish(),failed=()=>finish(Error("media load failed")),timer=setTimeout(()=>finish(Error("media metadata timeout")),4000);
        mediaPlayer.addEventListener("loadedmetadata",ready,{once:true});mediaPlayer.addEventListener("error",failed,{once:true});mediaPlayer.load();
      });
      if(ticket!==mediaToken || !valid() || !soundEnabled)return null;
      mediaPlayer.currentTime=offset;mediaTimeline=timeline;
      await mediaPlayer.play();
      if(ticket!==mediaToken || !valid())return null;
      mediaFailed=false;$("output-status").hidden=true;
      return {player:mediaPlayer,ticket};
    }catch(error){
      if(ticket!==mediaToken || !valid())return null;
      mediaTimeline=false;mediaFailed=true;
      unlockSound();
      $("output-status").textContent="画面収録向けの音声を開始できませんでした。標準出力に戻します。音が出ない場合は盤面をタップしてください。";$("output-status").hidden=false;
      return null;
    }
  }
  async function mediaFrames(promise,offset,end,token,drawAt) {
    const valid=()=>token===animationToken && !leaving;
    const active=await playMediaClip(promise,offset,valid,true);
    if(!active)return false;
    let lastTime=active.player.currentTime,lastProgress=performance.now();
    while(valid() && active.ticket===mediaToken){
      drawAt(active.player.currentTime);
      if(active.player.currentTime>=end || active.player.ended){mediaTimeline=false;return true;}
      if(active.player.paused){stopAnimation();return true;}
      if(active.player.currentTime!==lastTime){lastTime=active.player.currentTime;lastProgress=performance.now();}
      else if(document.visibilityState==="visible" && performance.now()-lastProgress>4000){stopAnimation();return true;}
      await new Promise(requestAnimationFrame);
    }
    return !valid();
  }
  const frameFlips=(before,after)=>after.filter((c,s)=>c!=="-" && before[s]!=="-" && before[s]!==c).length;
  function forwardMediaClip() {
    const snapshot=frames,voice=soundVoice,total=snapshot.length-1;
    return renderMediaClip("forward|"+voice+"|"+snapshot.at(-1).board.join("")+"|"+snapshot.map(f=>f.move).join(","),total*.45+.6,()=>{
      for(let i=1;i<snapshot.length;i++)if(snapshot[i].square!==null)planStep((i-1)*.45+.01,frameFlips(snapshot[i-1].board,snapshot[i].board),voice);
    });
  }
  const cells = Array.from({length:64}, (_, s) => {
    const button = document.createElement("button");
    button.type = "button"; button.className = "cell"; button.dataset.square = s; button.dataset.color = "-";
    button.tabIndex = s === 0 ? 0 : -1;
    const disc = document.createElement("span"); disc.className = "disc"; button.append(disc);
    $("board").append(button); return button;
  });
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
    document.querySelector(".panel").dataset.playback=String(!editing && !searching);
    $("edit-board").hidden=editing || searching;
    $("share-board").hidden=editing || searching;
    $("reset-board").hidden=!editing;
    $("voice-settings").hidden=editing || searching; $("ply").hidden=editing || searching;
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
    $("eyebrow").textContent = {editing:"END → BEGINNING",searching:"FINDING THE STORY",found:"THE STORY IS FOUND",rewinding:"BACK TO THE BEGINNING",playing:"ONE MOVE AT A TIME",paused:"ONE MOVE AT A TIME",complete:"THE BOARD, RESTORED"}[next];
    $("headline").innerHTML = {editing:"オセロを、<br>巻き戻す。",searching:"はじまりを、<br>探す。",found:"手順が、<br>見つかりました。",rewinding:"時間を、<br>巻き戻す。",playing:"一手ずつ、<br>この盤面へ。",paused:"一手ずつ、<br>この盤面へ。",complete:"この一局が、<br>この盤面に。"}[next];
    $("subtitle").textContent = {editing:"この盤面に至る、一つの物語。",searching:"合法な棋譜を計算しています。",found:"完成した盤面から、初期配置へ。",rewinding:"石の記憶を、たどっていく。",playing:"初期配置から、合法な手順を再生。",paused:"好きなところから、続きを。",complete:"入力した盤面と、64マスすべて一致。"}[next];
    $("footer-label").textContent = next === "editing" ? "この端末で計算・保存します" : next === "complete" ? "別の盤面にも、別の物語。" : "終わりから、はじまりへ。";
  }
  function draw(board, last = null, animated = true, sonify = false) {
    const placed=board.some((color,s)=>color!=="-" && cells[s].dataset.color==="-");
    const orderedFlips=board.flatMap((color,s)=>color!=="-" && cells[s].dataset.color!=="-" && cells[s].dataset.color!==color?[s]:[]);
    const flipDistance=s=>last===null?0:Math.max(Math.abs(s%8-last%8),Math.abs(Math.floor(s/8)-Math.floor(last/8)));
    orderedFlips.sort((a,b)=>flipDistance(a)-flipDistance(b)||a-b);
    const flipOrder=new Map(orderedFlips.map((square,i)=>[square,i])),normalPattern=soundPattern==="classic" || soundPattern==="wave";
    if(sonify && placed && normalPattern)classicStepSound(orderedFlips.length);
    for (let s = 0; s < 64; s++) {
      const previous = cells[s].dataset.color;
      cells[s].firstChild.classList.toggle("placed",phase !== "editing" && previous === "-" && board[s] !== "-");
      const distance = last === null ? 0 : Math.max(Math.abs(s % 8 - last % 8), Math.abs(Math.floor(s / 8) - Math.floor(last / 8)));
      const flipDelay=sonify && normalPattern && flipOrder.has(s)?70+(soundPattern==="wave"?flipOrder.get(s)*Math.min(35,220/Math.max(1,orderedFlips.length)):0):(animated && phase==="playing" && s!==last?Math.min(distance*23,145):0);
      cells[s].style.setProperty("--disc-delay",flipDelay/speed+"ms");
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
    const empty=target.every(c=>c==="-");
    inputInvalid = !check.ok && !empty;
    $("solve").disabled = !check.ok || target.every((c,s)=>c===INITIAL[s]);
    $("solve").classList.remove("reset-action");
    $("solve").setAttribute("aria-label","計算開始");$("solve").title="計算開始";$("solve-label").textContent="計算開始";
    $("input-error").textContent = inputInvalid ? "巻き戻し不可能な盤面です" : "この盤面を巻き戻す";
    $("input-error").classList.toggle("error",inputInvalid);
    $("input-error").hidden = false;
    status("");
  }
  function place(square, value = nextColor(target[square])) {
    if (phase !== "editing") return;
    if (target[square] === value) return;
    invalidate(); target[square] = value; updateInput();
  }
  let boardTouch=null, suppressBoardClickUntil=0;
  const endBoardGesture=()=>{document.documentElement.classList.remove("board-gesture");boardTouch=null;};
  $("board").addEventListener("touchstart",event=>{
    if(event.cancelable)event.preventDefault();
    const touch=event.touches[0];
    boardTouch=touch?{x:touch.clientX,y:touch.clientY,moved:event.touches.length!==1,phase}:null;
    document.documentElement.classList.add("board-gesture");
  },{passive:false});
  $("board").addEventListener("touchmove",event=>{
    if(event.cancelable)event.preventDefault();
    const touch=event.touches[0];
    if(boardTouch && touch && (Math.abs(touch.clientX-boardTouch.x)>10 || Math.abs(touch.clientY-boardTouch.y)>10))boardTouch.moved=true;
  },{passive:false});
  $("board").addEventListener("touchend",event=>{
    if(event.cancelable)event.preventDefault();
    const gesture=boardTouch;endBoardGesture();suppressBoardClickUntil=Date.now()+600;
    if(gesture && !gesture.moved && gesture.phase===phase && !["editing","searching"].includes(phase))togglePlayback();
  },{passive:false});
  $("board").addEventListener("touchcancel",endBoardGesture,{passive:true});
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
    $("prev").disabled = index === 0; $("next").disabled = index === frames.length - 1;
  }
  function stopAnimation() { animationToken++; stopSound(); if (frames.length) { setPhase("paused"); status("一時停止中です。手送りやシークでも確認できます。"); } }
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  async function forward(token) {
    setPhase("playing");
    status("合法な棋譜を、一手ずつ再生しています。");
    if(soundEnabled && audioOutput==="recording" && !mediaFailed){
      const total=frames.length-1;
      const played=await mediaFrames(forwardMediaClip(),index*.45,total*.45,token,time=>{
        const next=Math.min(total,Math.floor(time/.45)+1);if(next!==index)showFrame(next,true);
      });
      if(played){if(token===animationToken && !leaving && index===total)setPhase("complete");return;}
    }
    while (token === animationToken && index < frames.length - 1 && !leaving) {
      if(soundEnabled && audioOutput==="recording" && !mediaFailed){await forward(token);return;}
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
    status("初期配置へ巻き戻しています。");
    let mediaRewound=false;
    if(!reducedMotion && soundEnabled && audioOutput==="recording" && !mediaFailed){
      const start=index,snapshot=frames,voice=soundVoice,gap=Math.max(24,Math.min(65,1900/frames.length))/1000;
      const clip=renderMediaClip("rewind|"+voice+"|"+start+"|"+snapshot.at(-1).board.join("")+"|"+snapshot.map(f=>f.move).join(","),start*gap+.2,()=>{
        for(let i=start;i>0;i--)if(snapshot[i].square!==null)soundPresets[voice].remove((start-i)*gap+.005,snapshot[i-1].placements/Math.max(1,snapshot.at(-1).placements));
      });
      mediaRewound=await mediaFrames(clip,0,start*gap,token,time=>{const next=Math.max(0,start-Math.floor(time/gap)-1);if(next!==index)showFrame(next);});
    }
    if (reducedMotion) showFrame(0);
    else if(!mediaRewound)while (index > 0 && token === animationToken && !leaving) { const removed = frames[index].square !== null; showFrame(index - 1); if (removed) removalSound(); await wait(Math.max(24, Math.min(65, 1900 / frames.length))); }
    if (token !== animationToken || leaving) return;
    stopSound(); setPhase("paused"); await wait(600);
    if (token !== animationToken || leaving) return;
    if (reducedMotion) { status("初期配置に戻しました。盤面をタップすると一手ずつ進みます。"); return; }
    await forward(token);
  }
  function accept(result, pending, animate = true) {
    try {
      result={...result,moves:RetroRules.verify(result.moves,pending.target).moves};
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
  $("film").addEventListener("click", event => {
    if (phase === "editing" || phase === "searching" || event.target.closest("button, input, a") || (event.target.closest("#board") && Date.now()<suppressBoardClickUntil)) return;
    togglePlayback();
  });
  $("prev").onclick = () => { stopAnimation(); showFrame(index - 1); };
  $("next").onclick = () => { stopAnimation(); unlockSound(); showFrame(index + 1, true); };
  $("seek").oninput = () => { stopAnimation(); showFrame(+$("seek").value); };

  function showShareDialog(url) {
    $("share-url").value=url;
    $("share-x").href="https://x.com/intent/tweet?"+new URLSearchParams({text:"逆算オセロ",url});
    $("share-line").href="https://social-plugins.line.me/lineit/share?"+new URLSearchParams({url});
    $("share-status").textContent="";$("share-dialog").showModal();
  }
  $("share-board").onclick = async () => {
    if(!frames.length)return;
    const complete=frames.slice(1).map(frame=>frame.move), finalBoard=frames.at(-1).board.join("");
    const code=OthelloRecordCodec.encode(RetroRules.verify(complete,finalBoard).moves);
    if(["playing","rewinding","found"].includes(phase))stopAnimation();
    const link=new URL("./",location.href);
    link.searchParams.set("r",code);
    const payload={title:"逆算オセロ",text:"逆算オセロの棋譜",url:link.href};
    $("share-board").disabled=true;
    try{
      if(typeof navigator.share!=="function"){showShareDialog(link.href);return;}
      try{await navigator.share(payload);}catch(error){if(error.name!=="AbortError")showShareDialog(link.href);}
    }finally{$("share-board").disabled=false;}
  };
  $("share-url").onfocus=event=>event.target.select();
  $("copy-share-url").onclick = async () => {
    const input=$("share-url");let copied=false;
    try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(input.value);copied=true;}}catch{}
    if(!copied){input.focus();input.select();try{copied=document.execCommand("copy");}catch{}}
    $("share-status").textContent=copied?"URLをコピーしました":"URLを長押ししてコピーしてください";
  };

  let sessionResume = null, libraryVersion = 0, recordCursor = null, librarySeen = new Set();
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
  $("new-session").onclick=()=>{closeSession();replaceBoard(EMPTY.slice());};
  $("edit-board").onclick=()=>{
    const snapshot=frames.at(-1),stored=load("result");
    const reusable=snapshot?{target:snapshot.board.join(""),moves:frames.slice(1).map(frame=>frame.move),seconds:stored?.seconds}:null;
    replaceBoard(snapshot?.board.slice() || target.slice());save("edit-record",reusable);
  };
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
    if ([...board].filter(c=>c!=="-").length<=4 || librarySeen.has(board)) return null;
    librarySeen.add(board);
    const button=document.createElement("button");button.type="button";button.className="record-choice";
    const preview=document.createElement("span");preview.className="record-preview";preview.setAttribute("aria-hidden","true");
    for(const color of board){const cell=document.createElement("i");cell.dataset.color=color;preview.append(cell);}
    const seconds=local?row.seconds:row.elapsed_seconds;
    button.setAttribute("aria-label","この盤面を読み込む");button.append(preview);
    button.onclick=()=>{
      try {
        RetroRules.verify(moves,board);const built=buildFrames(moves);if(built.at(-1).board.join("")!==board)throw Error();
        closeSession();invalidate();target=[...board];save("board",board);accept({moves,time:seconds},{target:board});
      } catch {$("library-status").textContent="この棋譜を読み込めませんでした。";}
    };
    return button;
  }
  let staticRecordsPromise;
  function staticRows(payload){
    const collection=Array.isArray(payload)?payload:(payload?.examples ?? payload?.records ?? payload);
    const rows=Array.isArray(collection)?collection:Object.entries(collection || {}).filter(([,value])=>value && typeof value==="object").map(([id,row])=>({id,...row}));
    return rows.filter(row=>row && typeof row==="object").map(row=>({...row,id:row.id || row.record_id,board:row.board || row.target || row.request?.board,moves:row.moves || row.result?.moves,elapsed_seconds:row.elapsed_seconds ?? row.wall_seconds ?? row.seconds}));
  }
  function readStaticRecords(){
    if(!staticRecordsPromise)staticRecordsPromise=fetch(new URL("public-examples.json",location.href)).then(response=>{if(!response.ok)throw Error();return response.json();}).then(staticRows).catch(error=>{staticRecordsPromise=null;throw error;});
    return staticRecordsPromise;
  }
  async function loadRecords(version,append=false) {
    $("more-records").disabled=true;$("library-status").textContent="読み込み中…";
    try {
      const rows=await readStaticRecords(),next=null;
      if(version!==libraryVersion || !$("session-dialog").open)return;
      if(!append)$("public-records").replaceChildren();
      for(const row of rows){const button=recordChoice(row);if(button)$("public-records").append(button);}
      recordCursor=next;$("more-records").hidden=!next;$("library-status").textContent=($("public-records").children.length+$("local-records").children.length)?"":"まだ作成された棋譜はありません。";
    }catch{if(version===libraryVersion)$("library-status").textContent="棋譜を読み込めませんでした。";}
    finally{if(version===libraryVersion)$("more-records").disabled=false;}
  }
  $("load-session").onclick=()=>{
    $("session-choices").hidden=true;$("session-library").hidden=false;librarySeen=new Set();$("local-records").replaceChildren();
    for(const row of getHistory()){const button=recordChoice(row,true);if(button)$("local-records").append(button);}
    recordCursor=null;$("more-records").hidden=true;loadRecords(++libraryVersion);
  };
  $("more-records").onclick=()=>loadRecords(libraryVersion,true);
  function updateSoundButton() {
    $("sound").setAttribute("aria-pressed", String(soundEnabled));
    $("sound").setAttribute("aria-label", soundEnabled ? "音を消す" : "音を鳴らす");
    $("sound").title = soundEnabled ? "音を消す" : "音を鳴らす";
    $("sound-icon").innerHTML = soundEnabled ? '<path d="M11 5 6 9H3v6h3l5 4ZM15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>' : '<path d="M11 5 6 9H3v6h3l5 4ZM16 9l5 6m0-6-5 6"/>';
  }
  function toggleSound() {
    soundEnabled = !soundEnabled; save("sound", soundEnabled);
    if (soundEnabled) Promise.resolve(unlockSound()).then(previewPattern); else stopSound(); updateSoundButton();
  }
  $("sound").onclick = toggleSound;
  for (const [voice,preset] of Object.entries(soundPresets)) {
    const button = document.createElement("button"); button.type="button"; button.className="toggle-button"; button.dataset.voice=voice; button.textContent=preset.label; button.setAttribute("aria-pressed",String(voice===soundVoice));
    button.onclick = () => {
      soundVoice=voice; save("voice",voice); stopSound(); $("voice-settings").title = "音色：" + preset.label;
      for (const option of $("voice-options").children) option.setAttribute("aria-pressed",String(option.dataset.voice===voice));
      Promise.resolve(unlockSound()).then(previewPattern);
    };
    $("voice-options").append(button);
  }
  $("film").dataset.audioPattern="wave";
  for(const [value,label] of [["standard","標準"],["recording","画面収録向け"]]){
    const button=document.createElement("button");button.type="button";button.className="toggle-button";button.dataset.output=value;button.textContent=label;button.setAttribute("aria-pressed",String(audioOutput===value));
    button.onclick=()=>{
      stopSound();audioOutput=value;mediaFailed=false;save("output",value);$("film").dataset.audioOutput=value;$("output-status").hidden=true;
      for(const option of $("output-options").children)option.setAttribute("aria-pressed",String(option.dataset.output===value));
      Promise.resolve(unlockSound()).then(previewPattern);
    };
    $("output-options").append(button);
  }
  $("film").dataset.audioOutput=audioOutput;
  let settingsResume=null;
  $("settings").onclick = $("voice-settings").onclick = () => {settingsResume=phase;if(["playing","rewinding","found"].includes(phase))stopAnimation();$("settings-dialog").showModal();};
  $("settings-dialog").addEventListener("close",()=>{const resume=settingsResume;settingsResume=null;stopSound();if(resume==="playing")forward(++animationToken);else if(resume==="rewinding")rewindAndPlay(++animationToken);else if(resume==="found")sequence();});
  function replaceBoard(next) { if (job) return; save("edit-record",null); invalidate(); target = next; setPhase("editing"); updateInput(); }
  function stage(message) {
    lastStage=message;
    const text={loading:"計算の準備をしています",encoding:"手順の条件を組み立てています",solving:"合法な手順を探しています",verifying:"棋譜を確認しています",model_loading:"モデルを読み込んでいます",model:"逆向きの候補を絞っています",beam_fast:"逆向きの候補を絞っています",candidate_sat:"候補の手順を確認しています"}[message] || "合法な手順を探しています";
    $("search-text").textContent=text;
  }
  const engineQuery=sharedParams.get("engine");
  let searchEngine=engineQuery==="sat"?"sat":engineQuery==="auto"?"auto":load("engine")==="sat"?"sat":"auto";
  for(const [value,label] of [["auto","Auto"],["sat","SAT"]]){
    const button=document.createElement("button");button.type="button";button.className="toggle-button";button.dataset.engine=value;button.textContent=label;button.setAttribute("aria-pressed",String(searchEngine===value));
    button.onclick=()=>{searchEngine=value;save("engine",value);for(const option of $("engine-options").children)option.setAttribute("aria-pressed",String(option.dataset.engine===value));};
    $("engine-options").append(button);
  }
  let worker=null;
  function stopWorker(){if(worker){worker.terminate();worker=null;}}
  function cancelCurrent(){
    if(!job)return;
    stopWorker();job=null;pollToken++;clearInterval(elapsedTimer);invalidate();setPhase("editing");updateInput();status("計算を中断しました。");
  }
  function begin(pending){
    animationToken++;job=pending;setPhase("searching");draw([...pending.target]);
    $("cancel").disabled=false;stage("loading");status("このブラウザで計算しています。");
    const tick=()=>$("elapsed").textContent=`${Math.max(0,Math.floor((Date.now()-pending.started)/1000))}秒`;
    clearInterval(elapsedTimer);tick();elapsedTimer=setInterval(tick,1000);
  }
  function finish(pending,result){
    if(job!==pending || leaving)return;
    clearInterval(elapsedTimer);job=null;stopWorker();
    if(result.status==="found"){accept({...result,time:result.wall_seconds},pending);return;}
    if(result.status==="unreachable"){rejectedBoards.add(pending.target);saveRejections();}
    setPhase("editing");updateInput();
    if(result.status!=="unreachable")status(result.reason || "計算を完了できませんでした。盤面を変えるか、もう一度お試しください。",true);
  }
  $("solve").onclick=()=>{
    if(job || $("solve").disabled)return;
    unlockSound();
    const boardKey=target.join(""),editingRecord=load("edit-record");
    const cached=editingRecord?.target===boardKey?editingRecord:getHistory().find(row=>row.target===boardKey);
    if(cached){try{RetroRules.verify(cached.moves,boardKey);const built=buildFrames(cached.moves);if(built.at(-1).board.join("")===boardKey){invalidate();accept({moves:cached.moves,time:cached.seconds},{target:boardKey});return;}}catch{}}
    invalidate();const pending={target:boardKey,started:Date.now()};begin(pending);
    try{
      worker=new Worker(new URL("solver-worker.js",location.href));
      worker.onmessage=event=>{if(job!==pending)return;const result=event.data;if(result?.type==="progress")stage(result.stage);else if(result?.type==="result")finish(pending,result);};
      worker.onerror=()=>finish(pending,{status:"error",reason:"計算を開始できませんでした。ページを読み込み直してください。"});
      worker.onmessageerror=()=>finish(pending,{status:"error",reason:"計算結果を読み取れませんでした。"});
      worker.postMessage({type:"solve",board:boardKey,engine:searchEngine});
    }catch(error){finish(pending,{status:"error",reason:"このブラウザで計算を開始できませんでした。"});}
  };
  $("cancel").onclick=cancelCurrent;
  $("cancel").addEventListener("pointerdown",event=>{if(event.button>0)return;event.preventDefault();cancelCurrent();});
  $("initial-board").onclick=()=>{settingsResume=null;replaceBoard(INITIAL.slice());$("settings-dialog").close();};
  for(const button of document.querySelectorAll("[data-transform]"))button.onclick=()=>{
    const mode=button.dataset.transform;
    const next=mode==="swap"?target.map(c=>c==="-"?c:opposite(c)):target.map((_,s)=>mode==="rotate"?target[(7-s%8)*8+Math.floor(s/8)]:target[Math.floor(s/8)*8+7-s%8]);
    settingsResume=null;replaceBoard(next);$("settings-dialog").close();
  };
  $("download-record").onclick=()=>{
    const result=load("result"),record={format:"othello-retro-board-v1",board:target.join(""),...(result?.target===target.join("")?{moves:result.moves,wall_seconds:result.seconds}: {})};
    const blob=new Blob([JSON.stringify(record,null,2)+"\n"],{type:"application/json"}),url=URL.createObjectURL(blob),link=document.createElement("a");
    link.href=url;link.download="othello-retro.json";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$("file-status").textContent="JSONを保存しました。";
  };
  $("import-record").onclick=()=>$("record-file").click();
  $("record-file").onchange=async event=>{
    const file=event.target.files[0];if(!file || job)return;
    try{
      if(file.size>1024*1024)throw Error("ファイルが大きすぎます。");
      const row=JSON.parse(await file.text()),board=row.board || row.target;
      if(!/^[XO-]{64}$/.test(board||""))throw Error("盤面の形式が正しくありません。");
      if(row.moves)RetroRules.verify(row.moves,board);
      settingsResume=null;$("settings-dialog").close();replaceBoard([...board]);
      if(row.moves)accept({moves:row.moves,time:row.wall_seconds ?? row.seconds},{target:board},false);
      $("file-status").textContent="";
    }catch(error){$("file-status").textContent="読み込めませんでした。"+error.message;}
    event.target.value="";
  };
  addEventListener("pagehide",()=>{leaving=true;stopWorker();job=null;endBoardGesture();animationToken++;stopSound();clearInterval(elapsedTimer);if(audio?.state==="running")audio.suspend().catch(()=>{});});
  addEventListener("pageshow",event=>{if(event.persisted){leaving=false;clearInterval(elapsedTimer);if(phase==="searching"){setPhase("editing");updateInput();status("計算を中断しました。");}else if(frames.length)stopAnimation();}});
  const recoverAudio=()=>{
    if(document.visibilityState!=="visible" || !soundEnabled || !["playing","rewinding"].includes(phase))return;
    unlockSound();
    if(mediaTimeline && mediaPlayer?.paused)mediaPlayer.play().catch(()=>stopAnimation());
  };
  addEventListener("focus",recoverAudio);
  document.addEventListener("visibilitychange",recoverAudio);
  if (reducedMotion) $("film").classList.add("no-motion");
  $("voice-settings").title="音色："+soundPresets[soundVoice].label;
  updateSoundButton();
  setPhase("editing"); updateInput();
  const result=load("result"),recordId=sharedParams.get("record");
  if(sharedCode!==null){
    try{const moves=OthelloRecordCodec.decode(sharedCode),built=buildFrames(moves);target=built.at(-1).board.slice();RetroRules.verify(moves,target.join(""));save("board",target.join(""));accept({moves},{target:target.join("")},false);}catch{status("共有された棋譜を読み込めませんでした。",true);}
  }else if(sharedMoves!==null){
    try{if(sharedParams.get("v")!=="1" || !/^[XO-]{64}$/.test(requested||"") || sharedMoves.length>480 || !/^(?:[a-h][1-8]|pass){0,120}$/.test(sharedMoves))throw Error();const moves=sharedMoves.match(/pass|[a-h][1-8]/g)||[];RetroRules.verify(moves,requested);target=[...requested];save("board",requested);accept({moves},{target:requested},false);}catch{status("共有された棋譜を読み込めませんでした。",true);}
  }else if(recordId){
    readStaticRecords().then(rows=>{const row=rows.find(item=>item.id===recordId);if(!row)throw Error();RetroRules.verify(row.moves,row.board);invalidate();target=[...row.board];save("board",row.board);accept({moves:row.moves,time:row.elapsed_seconds},{target:row.board},false);}).catch(()=>status("この棋譜を読み込めませんでした。",true));
  }else if(sharedParams.get("library")==="1"){$("reset-board").click();$("load-session").click();}
  else if(result?.target===target.join(""))accept({moves:result.moves,time:result.seconds},result,false);
  document.documentElement.dataset.shortReady="true";
})();
