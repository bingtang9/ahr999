// ahr999 PWA service worker.
// Strategy:
//   HTML + JSON: network-first (always fresh when online, cached for offline)
//   icons / manifest / other static: cache-first (stable assets)
// Bump CACHE when the strategy or shell list changes, to drop stale caches.
const CACHE = "ahr999-v2";
const SHELL = [
  "./manifest.json",
  "./icon.svg",
  "./icon-maskable.svg",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;  // never cache cross-origin (Binance, CDN)

  const isHTML = e.request.mode === "navigate" ||
                 url.pathname === "/" || url.pathname.endsWith("/") ||
                 url.pathname.endsWith(".html");
  const isData = url.pathname.includes("/data/");

  // Network-first for HTML + data (always fresh when online, cache as fallback).
  if (isHTML || isData) {
    e.respondWith(
      fetch(e.request).then(resp => {
        if (resp.ok) {
          const copy = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, copy));
        }
        return resp;
      }).catch(() => caches.match(e.request))
    );
    return;
  }

  // Cache-first for other static assets (icons, manifest, sw itself handled by browser).
  e.respondWith(
    caches.match(e.request).then(hit => hit || fetch(e.request).then(resp => {
      if (resp.ok) {
        const copy = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy));
      }
      return resp;
    }))
  );
});
