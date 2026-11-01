// Progressive Web App Service Worker for Aegis AI Camera Assistant
const CACHE_NAME = 'aegis-hud-v2';
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch(() => {});
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Only intercept GET requests for static UI shells; bypass live API and camera stream routes
  const url = event.request.url;
  if (
    event.request.method === 'GET' &&
    !url.includes('/api/') &&
    !url.includes('/stream/') &&
    !url.includes('/ws/')
  ) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
  }
});
