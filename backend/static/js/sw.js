/**
 * HelpChain Service Worker
 * Handles background push notifications and caching
 */

const CACHE_NAME = "helpchain-v1";
const STATIC_CACHE = "helpchain-static-v1";

// Files to cache
const STATIC_FILES = [
  "/",
  "/static/css/bootstrap.min.css",
  "/static/css/styles.css",
  "/static/js/bootstrap.bundle.min.js",
  "/static/js/notification_service.js",
  "/static/favicon.ico",
  "/static/manifest.json",
];

// Install event - cache static files
self.addEventListener("install", (event) => {
  console.log("Service Worker installing.");
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => {
        console.log("Caching static files");
        return cache.addAll(STATIC_FILES);
      })
      .catch((error) => {
        console.error("Error caching static files:", error);
      }),
  );
  // Force activation
  self.skipWaiting();
});

// Activate event - clean old caches
self.addEventListener("activate", (event) => {
  console.log("Service Worker activating.");
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== STATIC_CACHE && cacheName !== CACHE_NAME) {
              console.log("Deleting old cache:", cacheName);
              return caches.delete(cacheName);
            }
          }),
        );
      })
      .then(() => {
        // Take control of all clients
        return self.clients.claim();
      }),
  );
});

// Fetch event - serve from cache or network
self.addEventListener("fetch", (event) => {
  // Only cache GET requests
  if (event.request.method !== "GET") return;

  // Skip cross-origin requests
  if (!event.request.url.startsWith(self.location.origin)) return;

  event.respondWith(
    caches.match(event.request).then((response) => {
      // Return cached version or fetch from network
      return (
        response ||
        fetch(event.request)
          .then((fetchResponse) => {
            // Don't cache non-successful responses
            if (!fetchResponse.ok) return fetchResponse;

            // Cache successful responses
            const responseClone = fetchResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseClone);
            });

            return fetchResponse;
          })
          .catch((error) => {
            console.error("Fetch failed:", error);
            // Return offline fallback for HTML pages
            if (event.request.headers.get("accept").includes("text/html")) {
              return caches.match("/offline.html");
            }
          })
      );
    }),
  );
});

// Push event - handle incoming push notifications
self.addEventListener("push", (event) => {
  console.log("Push received:", event);

  let data = {};

  if (event.data) {
    try {
      data = event.data.json();
    } catch (error) {
      console.error("Error parsing push data:", error);
      data = { title: "HelpChain", body: event.data.text() };
    }
  }

  const options = {
    body: data.body || "Имате ново известие",
    icon: "/static/favicon.ico",
    badge: "/static/favicon.ico",
    tag: data.tag || "helpchain-notification",
    requireInteraction: data.requireInteraction || false,
    silent: data.silent || false,
    data: data.data || {},
    actions: data.actions || [],
  };

  // Add vibration for urgent notifications
  if (data.urgent) {
    options.vibrate = [200, 100, 200, 100, 200];
    options.silent = false;
  }

  event.waitUntil(
    self.registration
      .showNotification(data.title || "HelpChain", options)
      .then(() => {
        // Notify clients about the push
        return self.clients.matchAll().then((clients) => {
          clients.forEach((client) => {
            client.postMessage({
              type: "push_received",
              payload: data,
            });
          });
        });
      }),
  );
});

// Notification click event
self.addEventListener("notificationclick", (event) => {
  console.log("Notification clicked:", event);

  event.notification.close();

  const data = event.notification.data || {};
  let url = "/";

  // Determine URL based on notification type
  switch (data.type) {
    case "new_request":
    case "urgent_request":
      url = `/request/${data.requestId}`;
      break;
    case "message":
      url = `/chat/${data.chatId}`;
      break;
    case "task_update":
      url = `/task/${data.taskId}`;
      break;
    case "volunteer_assigned":
      url = `/task/${data.taskId}`;
      break;
    default:
      url = "/dashboard";
  }

  // Handle action clicks
  if (event.action) {
    switch (event.action) {
      case "view":
        url = url; // Use the determined URL
        break;
      case "dismiss":
        return; // Just close, don't navigate
      default:
        url = "/dashboard";
    }
  }

  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clients) => {
        // Check if there's already a window open with this URL
        const existingClient = clients.find((client) =>
          client.url.includes(url),
        );

        if (existingClient) {
          // Focus existing window
          return existingClient.focus();
        } else {
          // Open new window
          return self.clients.openWindow(url);
        }
      })
      .then(() => {
        // Notify clients about the click
        return self.clients.matchAll().then((clients) => {
          clients.forEach((client) => {
            client.postMessage({
              type: "notification_click",
              payload: data,
            });
          });
        });
      }),
  );
});

// Background sync for failed requests
self.addEventListener("sync", (event) => {
  console.log("Background sync triggered:", event.tag);

  if (event.tag === "background-sync") {
    event.waitUntil(doBackgroundSync());
  }
});

// Message event - handle messages from clients
self.addEventListener("message", (event) => {
  console.log("Message received:", event.data);

  if (event.data && event.data.type) {
    switch (event.data.type) {
      case "skipWaiting":
        self.skipWaiting();
        break;
      case "getVersion":
        event.ports[0].postMessage({ version: "1.0.0" });
        break;
    }
  }
});

// Background sync function
async function doBackgroundSync() {
  try {
    // Get pending requests from IndexedDB or similar
    const pendingRequests = await getPendingRequests();

    for (const request of pendingRequests) {
      try {
        const response = await fetch(request.url, request.options);
        if (response.ok) {
          // Remove from pending requests
          await removePendingRequest(request.id);
          console.log("Background sync successful for:", request.url);
        }
      } catch (error) {
        console.error("Background sync failed for:", request.url, error);
      }
    }
  } catch (error) {
    console.error("Background sync error:", error);
  }
}

// Placeholder functions for pending requests (would use IndexedDB in production)
async function getPendingRequests() {
  // In a real implementation, this would query IndexedDB
  return [];
}

async function removePendingRequest(id) {
  // In a real implementation, this would remove from IndexedDB
  console.log("Removing pending request:", id);
}

// Periodic background task (if supported)
self.addEventListener("periodicsync", (event) => {
  if (event.tag === "periodic-sync") {
    event.waitUntil(
      // Perform periodic tasks like checking for updates
      checkForUpdates(),
    );
  }
});

async function checkForUpdates() {
  try {
    // Check for app updates, new content, etc.
    console.log("Checking for updates...");

    // This could check for new help requests in the user's area
    // or update cached data
  } catch (error) {
    console.error("Update check failed:", error);
  }
}
