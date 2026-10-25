/* Encode frames and offline audio with explicit timestamps on one shared timeline. */
"use strict";
(() => {
  const button = document.getElementById("vExport"), cancel = document.getElementById("vExportCancel");
  const format = document.getElementById("vExportFormat"), status = document.getElementById("exportStatus");
  const download = document.getElementById("exportDownload");
  let recording = false, aborted = false, objectURL = null;
  const M = window.Mediabunny;
  const types = [["MP4", "avc", "aac"], ["WebM", "vp9", "opus"]];
  button.disabled = true;
  status.textContent = "動画の保存形式を確認中…";
  const ready = (async () => {
    const supported = [];
    if (M && window.VideoEncoder && window.AudioEncoder) {
      for (const [label, video, audio] of types) {
        if (await M.canEncodeVideo(video, {width:720, height:1280}) && await M.canEncodeAudio(audio)) supported.push([label, video, audio]);
      }
    }
    format.replaceChildren(...supported.map(([label]) => new Option(label, label)));
    button.disabled = !supported.length;
    status.textContent = supported.length ? "選んだ音・字幕・画面比率で保存します。保存中はこのタブを開いたままにしてください。" :
      "このブラウザでは動画を保存できません。最新版のChrome、Edge、Safariでお試しください。";
    return supported;
  })();

  function captions(ctx, text, y, width, fontSize, bottom) {
    if (!text) return;
    ctx.font = `700 ${fontSize}px -apple-system, BlinkMacSystemFont, 'Hiragino Sans', sans-serif`;
    const lines = []; let line = "";
    for (const char of text) {
      if (char === "\n" || ctx.measureText(line + char).width > width * .88) { lines.push(line); line = char === "\n" ? "" : char; }
      else line += char;
    }
    lines.push(line);
    const height = fontSize * 1.4;
    if (bottom) y -= lines.length * height;
    ctx.fillStyle = "#f4f2ea"; ctx.textAlign = "center"; ctx.textBaseline = "top";
    ctx.shadowColor = "rgba(0,0,0,.6)"; ctx.shadowBlur = fontSize * .25;
    lines.forEach((s, i) => ctx.fillText(s, width / 2, y + i * height));
    ctx.shadowBlur = 0;
  }

  function makeTimeline() {
    const durations = stepDurations(), starts = [];
    let end = cfg.introMs;
    for (const duration of durations) { starts.push(end); end += duration; }
    // 100ms is an integer number of both 30fps video frames and 20ms Opus packets.
    return { starts, outroStart: end, duration: Math.ceil((end + cfg.outroMs + 750) / 100) * 100 };
  }

  function sceneAt(t, timeline) {
    let k = 0;
    while (k < timeline.starts.length && t >= timeline.starts[k]) k++;
    return { k, elapsed: k ? t - timeline.starts[k - 1] : Infinity,
      introOpacity: cfg.introMs > 0 ? Math.max(0, Math.min(1, t / 350, (cfg.introMs + 350 - t) / 350)) : 0,
      outroOpacity: Math.max(0, Math.min(1, (t - timeline.outroStart) / 350)) };
  }

  function drawFrame(canvas, scene = null) {
    const ctx = canvas.getContext('2d'), w = canvas.width, h = canvas.height;
    ctx.fillStyle = '#101311'; ctx.fillRect(0, 0, w, h);
    if (!states) return;
    scene ||= { k: view?.k || 0, elapsed: Infinity, introOpacity: 0, outroOpacity: 0 };
    const st = states[scene.k], prev = states[Math.max(0, scene.k - 1)];
    const delays = new Map(scene.k ? flipSchedule(st).map(({s, delay}) => [s, delay]) : []);
    const root = getComputedStyle(document.documentElement);
    const size = Math.min(w, h) * .86, x = (w - size) / 2, y = (h - size) / 2;
    const gap = Math.max(1.5, size * .004), step = (size - gap) / 8, square = step - gap;
    ctx.fillStyle = root.getPropertyValue('--board-line'); ctx.fillRect(x, y, size, size);
    st.b.forEach((stone, s) => {
      const left = x + gap + (s % 8) * step, top = y + gap + Math.floor(s / 8) * step;
      ctx.fillStyle = root.getPropertyValue('--board'); ctx.fillRect(left, top, square, square);
      let color = stone, scaleX = 1, scaleY = 1, opacity = 1;
      if (prefs.anim && scene.k) {
        if (s === st.last && scene.elapsed < 200) {
          const progress = Math.max(0, scene.elapsed / 200), eased = 1 - (1 - progress) ** 2;
          scaleX = scaleY = opacity = .3 + .7 * eased;
        }
        if (delays.has(s)) {
          const elapsed = scene.elapsed - FLIP_DELAY - delays.get(s);
          if (elapsed < 0) color = prev.b[s];
          else if (elapsed < FLIP_HALF) { color = prev.b[s]; scaleX = 1 - (elapsed / FLIP_HALF) ** 2; }
          else if (elapsed < 2 * FLIP_HALF) { color = st.b[s]; scaleX = 1 - (1 - (elapsed - FLIP_HALF) / FLIP_HALF) ** 2; }
        }
      }
      if (color !== '-') {
        const radius = square * .4;
        ctx.save(); ctx.translate(left + square / 2, top + square / 2);
        ctx.scale(Math.max(.001, scaleX), Math.max(.001, scaleY)); ctx.globalAlpha = opacity;
        const gradient = ctx.createRadialGradient(-radius * .3, -radius * .4, 0, 0, 0, radius * 1.2);
        gradient.addColorStop(0, color === 'X' ? '#4a4a4a' : '#ffffff');
        gradient.addColorStop(.6, color === 'X' ? '#1b1b1b' : '#f7f7f2');
        gradient.addColorStop(1, color === 'X' ? '#111111' : '#d9d9d0');
        ctx.fillStyle = gradient; ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 2; ctx.shadowOffsetY = 1;
        ctx.beginPath(); ctx.arc(0, 0, radius, 0, Math.PI * 2); ctx.fill(); ctx.restore();
      }
      if (cfg.marks && s === st.last) {
        ctx.fillStyle = root.getPropertyValue('--hl'); ctx.beginPath();
        ctx.arc(left + square / 2, top + square / 2, square * .11, 0, Math.PI * 2); ctx.fill();
      }
    });
    ctx.save(); ctx.globalAlpha = scene.introOpacity;
    captions(ctx, cfg.introText, h * .07, w, w * .055, false); ctx.restore();
    ctx.save(); ctx.globalAlpha = scene.outroOpacity;
    captions(ctx, cfg.outroText, h * .92, w, w * .055, true); ctx.restore();
  }

  function cancelExport() {
    if (!recording) return;
    aborted = true; stop(); status.textContent = "保存を中止しています…";
  }
  cancel.onclick = cancelExport;
  document.addEventListener("visibilitychange", () => { if (document.hidden) cancelExport(); });

  async function save() {
    if (recording) return;
    const supported = await ready;
    if (!supported.length) return;
    if (!states) { status.textContent = "先に棋譜を読み込んでください。"; return; }
    stop(); recording = true; aborted = false;
    const oldSound = prefs.sound, disabled = new Map();
    const controls = [...document.querySelectorAll(".settings input, .settings textarea, .settings button, .settings select"), vPlay, vFirst, vRec, button, format];
    controls.forEach(el => { disabled.set(el, el.disabled); el.disabled = true; });
    cancel.hidden = false; download.hidden = true;
    let output, finalized = false, failed = false;
    try {
      // The save action explicitly includes sound even when preview sound was off.
      prefs.sound = true;
      audioCtx(); // Initialize the shared noise sample used by the sound presets.
      stopSoundEffects();
      status.textContent = '音声と映像を準備中…';
      const timeline = makeTimeline();
      // Pre-render every sound against the exact same timeline used for all video frames.
      const offline = new OfflineAudioContext(2, Math.ceil(timeline.duration / 1000 * 48000), 48000);
      states.slice(1).forEach((st, i) => playStepSoundPanned(st, cfg.pan / 100, offline, timeline.starts[i] / 1000));
      const soundtrack = await offline.startRendering();
      if (aborted) return;
      view.k = 0; view.show(0, false); capIntro.classList.remove('on'); capOutro.classList.remove('on');
      const canvas = document.createElement('canvas'), ratio = Number(cfg.ar);
      canvas.width = ratio < 1 ? 720 : ratio > 1 ? 1280 : 720;
      canvas.height = ratio < 1 ? 1280 : 720;
      canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;z-index:2';
      stage.append(canvas);
      const [label, videoCodec, audioCodec] = supported.find(([name]) => name === format.value);
      const target = new M.BufferTarget();
      output = new M.Output({target, format: label === 'MP4' ? new M.Mp4OutputFormat() : new M.WebMOutputFormat()});
      const videoSource = new M.CanvasSource(canvas, {codec:videoCodec, bitrate:5000000});
      const audioSource = new M.AudioBufferSource({codec:audioCodec, bitrate:128000});
      const fps = 30, frameCount = Math.ceil(timeline.duration / 1000 * fps);
      output.addVideoTrack(videoSource, {frameRate:fps}); output.addAudioTrack(audioSource);
      await output.start();
      // Feed both tracks concurrently to respect muxer backpressure. No live
      // AudioContext or recorder clock participates in the file timestamps.
      await Promise.all([
        (async () => { await audioSource.add(soundtrack); audioSource.close(); })(),
        (async () => {
          for (let frame = 0; frame < frameCount && !aborted; frame++) {
            drawFrame(canvas, sceneAt(frame / fps * 1000, timeline));
            await videoSource.add(frame / fps, 1 / fps);
            if (frame % 8 === 0) {
              status.textContent = `音付き動画を保存中… ${Math.floor(frame / frameCount * 100)}%`;
              await new Promise(resolve => setTimeout(resolve, 0));
            }
          }
          videoSource.close();
        })()
      ]);
      if (aborted) return;
      await output.finalize(); finalized = true;
      if (aborted) return;
      view.show(states.length - 1, false);
      const mime = label === 'MP4' ? 'video/mp4' : 'video/webm', blob = new Blob([target.buffer], {type:mime});
      if (!blob.size) throw new Error("動画を作成できませんでした。");
      if (objectURL) URL.revokeObjectURL(objectURL);
      objectURL = URL.createObjectURL(blob);
      const extension = mime.startsWith("video/mp4") ? "mp4" : "webm";
      const filename = `othello-${new Date().toISOString().replace(/[:.]/g, "-")}.${extension}`;
      download.href = objectURL; download.download = filename; download.hidden = false;
      download.click();
      status.textContent = `音付き動画を保存しました（${extension.toUpperCase()}・${(blob.size / 1048576).toFixed(1)} MB）。`;
    } catch (e) {
      if (!aborted) { failed = true; status.textContent = `保存できませんでした：${e.message || e}`; }
    } finally {
      stop();
      if (output && !finalized) { try { await output.cancel(); } catch (e) {} }
      stage.querySelector('canvas')?.remove();
      prefs.sound = oldSound;
      disabled.forEach((value, el) => { el.disabled = value; });
      cancel.hidden = true; recording = false;
      if (aborted && !failed) status.textContent = "保存を中止しました。タブを開いた状態で、もう一度保存できます。";
    }
  }
  button.onclick = save;
  window.OthelloVideoExport = { save, drawFrame, get recording() { return recording; } };
})();
