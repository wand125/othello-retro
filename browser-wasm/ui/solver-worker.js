// SPDX-License-Identifier: MIT
'use strict';
importScripts('verify.js', 'engine.js', 'kissat.js');
let modules;
async function initialize() {
  const response = await fetch(new URL('encoder.wasm', self.location.href));
  if (!response.ok) throw Error('計算に必要なファイルを読み込めませんでした。');
  const [rust, sat] = await Promise.all([
    WebAssembly.instantiate(await response.arrayBuffer(), {}),
    createKissat({locateFile: name => new URL(name, self.location.href).href, print: () => {}, printErr: () => {}})
  ]);
  return {encoder: rust.instance.exports, sat};
}
let busy = false;
self.onmessage = async event => {
  if (event.data?.type !== 'solve' || busy) return;
  busy = true;
  const started = performance.now();
  try {
    postMessage({type: 'progress', stage: 'loading'});
    modules ||= initialize();
    const {encoder, sat} = await modules;
    const result = RetroEngine.solve(event.data.board, encoder, sat, RetroRules,
      update => postMessage({type: 'progress', ...update}));
    postMessage({type: 'result', ...result, wall_seconds: (performance.now() - started) / 1000});
  } catch (error) {
    postMessage({type: 'result', status: 'error',
      reason: /memory|allocation|out of bounds/i.test(String(error))
        ? 'この端末で使えるメモリが不足しました。ほかのタブを閉じるか、別の端末でお試しください。'
        : '計算を完了できませんでした。ページを読み込み直してお試しください。',
      wall_seconds: (performance.now() - started) / 1000});
  } finally {
    busy = false;
  }
};
