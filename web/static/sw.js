/* Papelito service worker: makes the page installable and keeps the static shell.
   The case list and the photos are never cached; they are household paper and they change. */

const SHELL = "papelito-shell-v2";
const SHELL_FILES = ["/", "/static/style.css", "/static/app.js", "/static/icon.svg", "/static/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return; /* always live */
  /* Network first, so a deploy shows up on the next load; the cache only covers no network at all. */
  event.respondWith(
    fetch(event.request).then((res) => {
      if (res.ok && SHELL_FILES.includes(url.pathname)) {
        const copy = res.clone();
        caches.open(SHELL).then((c) => c.put(event.request, copy));
      }
      return res;
    }).catch(() => caches.match(event.request, { ignoreSearch: url.pathname === "/" }))
  );
});
