// Service Worker for HelpChain PWA
// Handles caching, offline functionality, and background tasks

// Bump versions to invalidate old cached HTML (root page changed)
const CACHE_NAME = "helpchain-v1.0.2";
const STATIC_CACHE = "helpchain-static-v1.0.2";
const DYNAMIC_CACHE = "helpchain-dynamic-v1.0.2";

// Resources to cache immediately on install
const STATIC_ASSETS = [
  "/static/manifest.json",
  "/static/styles.css",
  "/static/hands-heart.png",
  "/static/volunteers.jpg",
  // Add other critical static assets here
];

// Install event - cache static assets
self.addEventListener("install", (event) => {
  console.log("[SW] Installing service worker");
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then(async (cache) => {
        console.log("[SW] Caching static assets");
        const results = await Promise.allSettled(
          STATIC_ASSETS.map(async (asset) => {
            const request = new Request(asset, { cache: "reload" });
            const response = await fetch(request);
            if (!response.ok) {
              throw new Error(
                `Failed to fetch ${asset} with status ${response.status}`,
              );
            }
            await cache.put(request, response);
          }),
        );

        const failures = results.filter(
          (result) => result.status === "rejected",
        );
        if (failures.length > 0) {
          console.warn(
            `[SW] Failed to cache ${failures.length} static asset(s) during install`,
          );
        }
      })
      .catch((error) => {
        console.error("[SW] Error caching static assets:", error);
      }),
  );
  // Force activation of new service worker
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener("activate", (event) => {
  console.log("[SW] Activating service worker");
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
            console.log("[SW] Deleting old cache:", cacheName);
            return caches.delete(cacheName);
          }
        }),
      );
    }),
  );
  // Take control of all clients immediately
  self.clients.claim();
});

// Fetch event - serve cached content when offline
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== "GET") {
    return;
  }

  // Skip external requests
  if (url.origin !== self.location.origin) {
    return;
  }

  // Allow Socket.IO and other streaming endpoints to bypass the service worker
  if (url.pathname.startsWith("/socket.io/")) {
    return;
  }

  // Always fetch the real-time client script directly to avoid stale caching
  if (url.pathname.includes("/static/js/helpchain-websocket.js")) {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match(request).then(
          (fallback) =>
            fallback ||
            new Response("", {
              status: 503,
              statusText: "Offline",
              headers: { "Retry-After": "30" },
            }),
        ),
      ),
    );
    return;
  }

  // Handle API requests differently
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/analytics/api/")
  ) {
    // For API requests, try network first, then cache
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cache successful API responses
          if (response.status === 200) {
            const responseClone = response.clone();
            caches.open(DYNAMIC_CACHE).then((cache) => {
              cache.put(request, responseClone);
            });
          }
          return response;
        })
        .catch(() =>
          caches.match(request).then(
            (cachedResponse) =>
              cachedResponse ||
              new Response(
                JSON.stringify({
                  error: "Offline",
                  message:
                    "Неуспешно зареждане на данни. Опитайте отново по-късно.",
                }),
                {
                  status: 503,
                  statusText: "Offline",
                  headers: {
                    "Content-Type": "application/json",
                    "Retry-After": "30",
                  },
                },
              ),
          ),
        ),
    );
    return;
  }

  // Special network-first strategy for root document to avoid stale landing page
  if (url.pathname === "/") {
    event.respondWith(
      fetch(request)
        .then((resp) => {
          // Do not cache root HTML to ensure freshest template
          return resp;
        })
        .catch(() => caches.match(request)),
    );
    return;
  }

  // For static assets and other pages, try cache first, then network
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(request)
        .then((response) => {
          // Don't cache non-successful responses
          if (
            !response ||
            response.status !== 200 ||
            response.type !== "basic"
          ) {
            return response;
          }

          // Cache the response
          const responseClone = response.clone();
          caches.open(DYNAMIC_CACHE).then((cache) => {
            cache.put(request, responseClone);
          });

          return response;
        })
        .catch((error) => {
          console.error("[SW] Fetch failed:", error);

          // Return offline fallback for navigation requests
          if (request.destination === "document") {
            return (
              caches.match("/") ||
              new Response("", {
                status: 503,
                statusText: "Offline",
                headers: { "Retry-After": "30" },
              })
            );
          }

          // Attempt to serve a cached asset for other requests
          return caches.match(request).then((fallback) => {
            if (fallback) {
              return fallback;
            }

            // Graceful fallback response to avoid undefined
            return new Response("", {
              status: 503,
              statusText: "Offline",
              headers: { "Retry-After": "30" },
            });
          });
        });
    }),
  );
});

// Background sync for offline requests
self.addEventListener("sync", (event) => {
  console.log("[SW] Background sync triggered:", event.tag);

  if (event.tag === "background-sync") {
    event.waitUntil(doBackgroundSync());
  }
});

// Push notifications (if implemented later)
self.addEventListener("push", (event) => {
  console.log("[SW] Push notification received");

  if (event.data) {
    const data = event.data.json();
    const options = {
      body: data.body,
      icon: "/static/hands-heart.png",
      badge: "/static/hands-heart.png",
      vibrate: [100, 50, 100],
      data: {
        url: data.url || "/",
      },
    };

    event.waitUntil(self.registration.showNotification(data.title, options));
  }
});

// Handle notification clicks
self.addEventListener("notificationclick", (event) => {
  console.log("[SW] Notification clicked");
  event.notification.close();

  event.waitUntil(clients.openWindow(event.notification.data.url || "/"));
});

// Background sync function
async function doBackgroundSync() {
  try {
    // Get all cached requests that failed due to offline
    const cache = await caches.open(DYNAMIC_CACHE);
    const keys = await cache.keys();

    const failedRequests = keys.filter(
      (request) =>
        request.url.includes("/api/") &&
        !request.url.includes("/analytics/api/live"), // Skip live endpoints
    );

    console.log(`[SW] Processing ${failedRequests.length} failed requests`);

    // Retry failed requests
    for (const request of failedRequests) {
      try {
        const response = await fetch(request);
        if (response.ok) {
          console.log("[SW] Successfully retried request:", request.url);
          await cache.delete(request);
        }
      } catch (error) {
        console.log("[SW] Request still failing:", request.url);
      }
    }
  } catch (error) {
    console.error("[SW] Background sync error:", error);
  }
}

// Periodic cleanup of old cache entries
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "CLEAN_CACHE") {
    cleanOldCache();
  }
});

async function cleanOldCache() {
  try {
    const cache = await caches.open(DYNAMIC_CACHE);
    const keys = await cache.keys();

    // Remove entries older than 1 hour
    const oneHourAgo = Date.now() - 60 * 60 * 1000;

    for (const request of keys) {
      // This is a simplified check - in production you'd store timestamps
      // For now, just remove every 10th item to prevent unlimited growth
      if (Math.random() < 0.1) {
        await cache.delete(request);
      }
    }

    console.log("[SW] Cache cleanup completed");
  } catch (error) {
    console.error("[SW] Cache cleanup error:", error);
  }
}
