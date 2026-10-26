// SPDX-License-Identifier: MIT
// FP32 model logits only. A caller must fall back to exact SAT if this rejects.
(function (root) {
  'use strict';
  const node = typeof process === 'object' && Boolean(process.versions?.node);
  const config = root.RetroInferenceConfig || {};
  const defaultBase = node ? new URL('./', require('node:url').pathToFileURL(__filename)) : new URL('./', root.location.href);
  const base = new URL(config.baseURL || './', defaultBase);
  if (!base.pathname.endsWith('/')) base.pathname += '/';
  function localURL(value) {
    const url = new URL(value, base);
    if (url.username || url.password) throw Error('Inference URLs must not contain credentials');
    if (node) { if (url.protocol !== 'file:') throw Error('Node inference uses local files only'); }
    else if (!['http:', 'https:'].includes(url.protocol) || url.origin !== root.location.origin) throw Error('Inference assets must be same-origin');
    return url;
  }
  localURL(base.href);
  const modelURLs = [localURL(config.modelURLs?.standard || 'model.fused.onnx'), localURL(config.modelURLs?.passes || 'model_passes.fused.onnx')];
  const runtimeURL = localURL('ort.wasm.min.js');
  const sessions = [null, null], queues = [Promise.resolve(), Promise.resolve()];
  let runtimePromise;
  const stats = {runtime: 'onnxruntime-web', version: '1.30.0', execution_provider: 'wasm', num_threads: 1,
    input_type: 'float32', input_layout: 'NCHW', quantized: false, fp16: false,
    runtime_load_seconds: null, models: [0, 1].map(() => ({session_load_seconds: null, calls: 0, failures: 0, last_batch: null, last_run_seconds: null, total_run_seconds: 0}))};
  function runtime() {
    if (!runtimePromise) runtimePromise = Promise.resolve().then(() => {
      const started = performance.now();
      let ort = root.ort;
      if (!ort) {
        if (node) ort = require(require('node:url').fileURLToPath(runtimeURL));
        else {
          if (typeof root.importScripts !== 'function') throw Error('Inference adapter must run in a classic Worker');
          root.importScripts(runtimeURL.href); ort = root.ort;
        }
      }
      if (!ort?.InferenceSession || !ort?.Tensor) throw Error('ONNX Runtime unavailable');
      if (ort.env.versions.web !== '1.30.0') throw Error('Unexpected ONNX Runtime version');
      ort.env.wasm.numThreads = 1;
      ort.env.wasm.proxy = false;
      ort.env.wasm.wasmPaths = base.href;
      ort.env.logLevel = 'warning';
      stats.runtime_load_seconds = (performance.now() - started) / 1000;
      return ort;
    }).catch(error => { runtimePromise = null; throw error; });
    return runtimePromise;
  }
  function session(index) {
    if (!sessions[index]) sessions[index] = (async () => {
      const ort = await runtime(), started = performance.now();
      const model = node ? new Uint8Array(require('node:fs').readFileSync(require('node:url').fileURLToPath(modelURLs[index]))) : modelURLs[index].href;
      const value = await ort.InferenceSession.create(model, {executionProviders: ['wasm'], graphOptimizationLevel: 'all'});
      if (value.inputNames.length !== 1 || value.inputNames[0] !== 'planes' || !value.outputNames.includes('logits')) {
        await value.release(); throw Error('Unexpected model input/output names');
      }
      stats.models[index].session_load_seconds = (performance.now() - started) / 1000;
      return value;
    })().catch(error => { sessions[index] = null; throw error; });
    return sessions[index];
  }
  async function run(input, count, index) {
    let tensor, outputs;
    try {
      const ort = await runtime(), model = await session(index);
      tensor = new ort.Tensor('float32', input, [count, 5, 8, 8]);
      const started = performance.now();
      outputs = await model.run({planes: tensor}, ['logits']);
      const elapsed = (performance.now() - started) / 1000, output = outputs.logits;
      if (output.type !== 'float32' || output.dims.length !== 1 || output.dims[0] !== count || !(output.data instanceof Float32Array)) throw Error('Invalid model output');
      const result = new Float32Array(output.data);
      for (const value of result) if (!Number.isFinite(value)) throw Error('Nonfinite model output');
      const modelStats = stats.models[index];
      modelStats.calls++; modelStats.last_batch = count; modelStats.last_run_seconds = elapsed; modelStats.total_run_seconds += elapsed;
      return result;
    } catch (error) { stats.models[index].failures++; throw error; }
    finally {
      tensor?.dispose();
      if (outputs) for (const value of Object.values(outputs)) value.dispose();
    }
  }
  function score(input, count, passes = false) {
    if (!(input instanceof Float32Array) || !Number.isSafeInteger(count) || count < 0 || input.length !== count * 5 * 8 * 8) return Promise.reject(new TypeError('Expected FP32 [N,5,8,8] input'));
    if (typeof passes !== 'boolean') return Promise.reject(new TypeError('passes must be boolean'));
    if (count === 0) return Promise.resolve(new Float32Array(0));
    for (const value of input) if (!Number.isFinite(value)) return Promise.reject(new TypeError('Nonfinite model input'));
    const index = passes ? 1 : 0;
    const result = queues[index].then(() => run(input, count, index));
    queues[index] = result.catch(() => {});
    return result;
  }
  const api = Object.freeze({score, getStats: () => JSON.parse(JSON.stringify(stats))});
  root.RetroInference = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(globalThis);
