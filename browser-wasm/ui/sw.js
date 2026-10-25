// SPDX-License-Identifier: MIT
'use strict';
// The static builder replaces this token so an asset change updates this script.
const BUILD_VERSION = '__ASSET_VERSION__';
const SCOPE = new URL(self.registration.scope);
const PREFIX = 'othello-retro-browser:' + SCOPE.pathname + ':';
const ASSET_PREFIX = PREFIX + 'assets:';
const STATE_CACHE = PREFIX + 'state';
const STATE_URL = new URL('.offline-cache-state', SCOPE).href;
const MANIFEST_URL = new URL('asset-manifest.json', SCOPE).href;
const INDEX_URL = new URL('index.html', SCOPE).href;
let installedCacheName;

async function activeCacheName() {
  if (BUILD_VERSION !== '__ASSET_' + 'VERSION__') return ASSET_PREFIX + BUILD_VERSION;
  if (installedCacheName) return installedCacheName;
  const state = await (await caches.open(STATE_CACHE)).match(STATE_URL);
  if (!state) throw Error('No active offline cache');
  const name = await state.text();
  if (!name.startsWith(ASSET_PREFIX)) throw Error('Invalid offline cache');
  return name;
}

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const response = await fetch(MANIFEST_URL, {cache: 'no-store', credentials: 'same-origin'});
    if (!response.ok) throw Error('Offline manifest unavailable');
    const manifest = await response.clone().json();
    if (typeof manifest.version !== 'string' || !manifest.version || !Array.isArray(manifest.files)) throw Error('Invalid offline manifest');
    if (BUILD_VERSION !== '__ASSET_' + 'VERSION__' && BUILD_VERSION !== manifest.version) throw Error('Offline version mismatch');
    const urls = manifest.files.map(file => {
      if (typeof file !== 'string' || !file || file.startsWith('/') || file.includes('\\')) throw Error('Invalid asset path');
      const url = new URL(file, SCOPE);
      if (url.origin !== SCOPE.origin || !url.pathname.startsWith(SCOPE.pathname) || url.search || url.hash) throw Error('Asset outside application scope');
      if (/(?:^|\/)api(?:\/|$)/.test(url.pathname)) throw Error('API is not an offline asset');
      return url.href;
    });
    if (!urls.includes(INDEX_URL)) throw Error('Offline entry missing');
    installedCacheName = ASSET_PREFIX + manifest.version;
    const cache = await caches.open(installedCacheName);
    await cache.addAll([...new Set(urls)]);
    await cache.put(MANIFEST_URL, response);
    // Keep an existing page and its asset version together. The browser activates
    // this update once pages using the older service worker have closed.
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const name = await activeCacheName();
    await (await caches.open(STATE_CACHE)).put(STATE_URL, new Response(name));
    await Promise.all((await caches.keys()).filter(key => key.startsWith(ASSET_PREFIX) && key !== name).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== SCOPE.origin || !url.pathname.startsWith(SCOPE.pathname) || /(?:^|\/)api(?:\/|$)/.test(url.pathname)) return;
  event.respondWith((async () => {
    let cache;
    try { cache = await caches.open(await activeCacheName()); }
    catch { return fetch(request); }
    const cached = await cache.match(request, {ignoreSearch: true});
    if (cached) return cached;
    if (request.mode === 'navigate') {
      const directory = new URL(url.href);
      if (!directory.pathname.endsWith('/')) directory.pathname += '/';
      const directoryEntry = await cache.match(new URL('index.html', directory), {ignoreSearch: true});
      if (directoryEntry) {
        if (!url.pathname.endsWith('/')) return Response.redirect(directory.href, 302);
        return directoryEntry;
      }
    }
    try { return await fetch(request); }
    catch (error) {
      if (request.mode === 'navigate') {
        const entry = await cache.match(INDEX_URL);
        // Canonicalize the entry URL so its relative scripts and Worker keep
        // working even when an offline navigation used an unknown nested path.
        if (entry) return Response.redirect(INDEX_URL + url.search, 302);
      }
      throw error;
    }
  })());
});
