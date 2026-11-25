// Dispensa service worker: an offline app shell and the last-loaded data, while
// staying fresh online (network-first, falling back to cache only when offline).
const CACHE = "dispensa-v4";

// The app shell: enough to open offline and render the frame. The rest of the JS
// modules and any data are cached at runtime on first online use.
const SHELL = [
  "/",
  "/index.html",
  "/css/tokens.css",
  "/css/base.css",
  "/css/components.css",
  "/css/shell.css",
  "/js/main.js",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/dispensa-icon-512.svg",
  "/icons/dispensa-favicon.svg",
  "/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      await cache.addAll(SHELL);
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(
        names.filter((name) => name !== CACHE).map((name) => caches.delete(name)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") {
    return;
  }
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }
  // Sign-in is a chain of redirects that set cookies; it must reach the network
  // untouched, and must never be answered with the cached app shell.
  if (url.pathname.startsWith("/auth/")) {
    return;
  }
  event.respondWith(
    (async () => {
      try {
        // Revalidate every file with the server instead of letting the browser's
        // own cache decide. A navigation cannot take options, and is always
        // fetched fresh anyway.
        const response =
          request.mode === "navigate"
            ? await fetch(request)
            : await fetch(request, { cache: "no-cache" });
        if (response.ok) {
          const cache = await caches.open(CACHE);
          cache.put(request, response.clone());
        }
        return response;
      } catch (error) {
        const cached = await caches.match(request);
        if (cached) {
          return cached;
        }
        if (request.mode === "navigate") {
          const shell = await caches.match("/");
          if (shell) {
            return shell;
          }
        }
        throw error;
      }
    })(),
  );
});
