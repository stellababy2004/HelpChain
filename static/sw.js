/* HelpChain Service Worker - minimal */
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// Network-first: don't break the site if cache is empty
self.addEventListener("fetch", (event) => {
  // Keep third-party assets (including OSM map tiles) out of the offline
  // fallback. A failed tile request must be handled by the browser, not
  // replaced with our same-origin 503 response.
  if (new URL(event.request.url).origin !== self.location.origin) return;

  event.respondWith(
    fetch(event.request).catch(() =>
      caches.match(event.request).then((cached) =>
        cached || new Response("", { status: 503, statusText: "Offline" })
      )
    )
  );
});
