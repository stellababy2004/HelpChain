// HelpChain Service Worker for PWA functionality
const CACHE_NAME = "helpchain-v1.0.2";
const STATIC_CACHE = "helpchain-static-v1.0.2";
const DYNAMIC_CACHE = "helpchain-dynamic-v1.0.2";

// Resources to cache immediately
const STATIC_ASSETS = [
  "/static/manifest.json",
  "/static/css/styles.css",
  "/static/css/custom.css",
  "/static/css/admin_volunteers.css",
  "/static/css/chatbot.css",
  "/static/css/facebook.css",
  "/static/icons/icon-192x192.png",
  "/static/icons/icon-512x512.png",
  "/static/icons/icon-144x144.png",
  "/static/icons/icon-96x96.png",
  "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
  "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css",
  "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css",
  "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
];

// Install event - cache static assets
self.addEventListener("install", (event) => {
  console.log("[SW] Installing service worker");
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => {
        console.log("[SW] Caching static assets");
        // Cache assets one by one to prevent installation failure if one fails
        return Promise.allSettled(
          STATIC_ASSETS.map(url => {
            return fetch(url, { mode: 'no-cors' })
              .then(response => {
                if (response.ok || response.type === 'opaque') {
                  return cache.put(url, response);
                } else {
                  console.warn(`[SW] Failed to cache ${url}: ${response.status}`);
                  return Promise.resolve(); // Don't fail the installation
                }
              })
              .catch(error => {
                console.warn(`[SW] Error caching ${url}:`, error);
                return Promise.resolve(); // Don't fail the installation
              });
          })
        );
      })
      .catch((error) => {
        console.error("[SW] Error opening cache:", error);
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
  if (request.method !== "GET") return;

  // Skip Chrome extension requests
  if (url.protocol === "chrome-extension:") return;

  // Handle API requests differently
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cache successful API responses for offline use
          if (response.status === 200) {
            const responseClone = response.clone();
            caches
              .open(DYNAMIC_CACHE)
              .then((cache) => cache.put(request, responseClone));
          }
          return response;
        })
        .catch(() => {
          // Return cached API response if available
          return caches.match(request).then((cachedResponse) => {
            if (cachedResponse) {
              return cachedResponse;
            }
            // Return offline message for API calls
            return new Response(
              JSON.stringify({
                error: "Офлайн режим",
                message: "Нямате интернет връзка. Моля, опитайте по-късно.",
                offline: true,
              }),
              {
                status: 503,
                statusText: "Service Unavailable",
                headers: { "Content-Type": "application/json" },
              },
            );
          });
        }),
    );
    return;
  }

  // Handle static assets and pages
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
          caches
            .open(DYNAMIC_CACHE)
            .then((cache) => cache.put(request, responseClone));

          return response;
        })
        .catch(() => {
          // Return offline fallback page for navigation requests
          if (request.mode === "navigate") {
            return caches.match("/").then((cachedResponse) => {
              if (cachedResponse) {
                return cachedResponse;
              }
              // Return basic offline page
              return new Response(
                `<!DOCTYPE html>
<html lang="bg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HelpChain - Офлайн</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background: linear-gradient(120deg, #e3f2fd 0%, #fff 100%);
            min-height: 100vh;
        }
        .offline-message {
            background: rgba(255, 255, 255, 0.9);
            border-radius: 20px;
            padding: 2rem;
            box-shadow: 0 8px 40px rgba(31, 38, 135, 0.2);
            max-width: 500px;
            margin: 0 auto;
        }
        h1 { color: #1976d2; }
        .retry-btn {
            background: #1976d2;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="offline-message">
        <h1>🚫 Офлайн режим</h1>
        <p>Нямате интернет връзка в момента.</p>
        <p>HelpChain ще работи нормално, когато се свържете отново с интернет.</p>
        <button class="retry-btn" onclick="window.location.reload()">Опитай отново</button>
    </div>
</body>
</html>`,
                {
                  headers: { "Content-Type": "text/html" },
                },
              );
            });
          }

          // For other requests, return error
          return new Response("Offline - No cached version available", {
            status: 503,
            statusText: "Service Unavailable",
          });
        });
    }),
  );
});

// Background sync for offline form submissions
self.addEventListener("sync", (event) => {
  console.log("[SW] Background sync triggered:", event.tag);

  if (event.tag === "help-request-sync") {
    event.waitUntil(syncHelpRequests());
  }

  if (event.tag === "feedback-sync") {
    event.waitUntil(syncFeedback());
  }
});

// Push notifications (for future use)
self.addEventListener("push", (event) => {
  console.log("[SW] Push notification received");

  if (event.data) {
    const data = event.data.json();
    const options = {
      body: data.body,
      icon: "/static/icons/icon-192x192.png",
      badge: "/static/icons/icon-96x96.png",
      vibrate: [100, 50, 100],
      data: {
        url: data.url || "/",
      },
    };

    event.waitUntil(
      self.registration.showNotification(data.title || "HelpChain", options),
    );
  }
});

// Handle notification clicks
self.addEventListener("notificationclick", (event) => {
  console.log("[SW] Notification clicked");
  event.notification.close();

  event.waitUntil(clients.openWindow(event.notification.data.url || "/"));
});

// Helper function to sync help requests
async function syncHelpRequests() {
  try {
    const cache = await caches.open(DYNAMIC_CACHE);
    // Implementation for syncing offline help requests
    console.log("[SW] Syncing help requests...");
    // This would typically send queued requests to server
  } catch (error) {
    console.error("[SW] Error syncing help requests:", error);
  }
}

// Helper function to sync feedback
async function syncFeedback() {
  try {
    const cache = await caches.open(DYNAMIC_CACHE);
    // Implementation for syncing offline feedback
    console.log("[SW] Syncing feedback...");
    // This would typically send queued feedback to server
  } catch (error) {
    console.error("[SW] Error syncing feedback:", error);
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
      // This is a simplified cleanup - in production you'd check response dates
      // For now, we'll keep all cached entries
    }

    console.log("[SW] Cache cleanup completed");
  } catch (error) {
    console.error("[SW] Error during cache cleanup:", error);
  }
}
