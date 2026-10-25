// SPDX-License-Identifier: MIT
'use strict';
(() => {
  if (!('serviceWorker' in navigator) || !window.isSecureContext) return;
  const script = new URL('sw.js', document.currentScript.src);
  const register = () => navigator.serviceWorker.register(script.href, {
    scope: new URL('.', script).href,
    updateViaCache: 'none'
  }).catch(() => {
    // Development previews may not have a generated manifest. Online operation
    // remains available; offline installation must not become a UI error.
  });
  if (document.readyState === 'complete') register();
  else addEventListener('load', register, {once: true});
})();
