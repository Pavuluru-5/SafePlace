/**
 * SafePlace Service Worker — v4
 * 100% Autonomous Offline PWA Engine with Cache-First Static Shell,
 * Offline SVG Tile Fallback, and Resilient API Interception.
 */

const CACHE_NAME = 'safeplace-v4';
const TILE_CACHE = 'safeplace-tiles-v1';

// Static Shell Assets for 100% Offline Capability
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/css/style.css',
  '/js/app.js',
  '/manifest.json',
  '/vendor/leaflet/leaflet.css',
  '/vendor/leaflet/leaflet.js',
  '/vendor/leaflet/images/marker-icon.png',
  '/vendor/leaflet/images/marker-icon-2x.png',
  '/vendor/leaflet/images/marker-shadow.png',
  '/vendor/leaflet/images/layers.png',
  '/vendor/leaflet/images/layers-2x.png',
  '/vendor/fontawesome/css/all.min.css',
  '/vendor/fontawesome/webfonts/fa-solid-900.woff2',
  '/vendor/fontawesome/webfonts/fa-regular-400.woff2',
  '/vendor/fontawesome/webfonts/fa-brands-400.woff2',
  '/vendor/fontawesome/webfonts/fa-v4compatibility.woff2'
];

// Dark HUD Radar Grid SVG for offline map tile fallback
const OFFLINE_TILE_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" fill="#0b0f19"/>
  <path d="M 0 64 L 256 64 M 0 128 L 256 128 M 0 192 L 256 192 M 64 0 L 64 256 M 128 0 L 128 256 M 192 0 L 192 256" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>
  <circle cx="128" cy="128" r="2" fill="rgba(59,130,246,0.2)"/>
</svg>`;

// Install Event: Pre-cache core shell assets
self.addEventListener('install', (event) => {
  console.log('[SafePlace ServiceWorker] Installing v4 offline cache...');
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cachePromises = STATIC_ASSETS.map(async (assetUrl) => {
        try {
          const response = await fetch(assetUrl, { cache: 'no-cache' });
          if (response && (response.ok || response.type === 'opaque')) {
            await cache.put(assetUrl, response.clone());
            if (assetUrl === '/') {
              await cache.put('/index.html', response.clone());
            }
          }
        } catch (err) {
          console.warn('[SafePlace ServiceWorker] Pre-cache skip for:', assetUrl, err);
        }
      });
      await Promise.allSettled(cachePromises);
      console.log('[SafePlace ServiceWorker] Shell pre-caching complete.');
    })
  );
  self.skipWaiting();
});

// Activate Event: Clean up legacy caches & take immediate control
self.addEventListener('activate', (event) => {
  console.log('[SafePlace ServiceWorker] Activating v4...');
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME && key !== TILE_CACHE) {
            console.log('[SafePlace ServiceWorker] Removing deprecated cache:', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event Handler: 100% Robust Offline Routing Strategy
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Ignore non-GET requests (e.g. POST to /api/...) so client offline fallback handles them
  if (request.method !== 'GET') {
    return;
  }

  // 1. Navigation Requests (Opening App / Home Screen Shortcut / Reloads / Offline Cold Start)
  if (request.mode === 'navigate' || request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      (async () => {
        // Cache first for instant zero-network offline launching
        const cached = await caches.match('/index.html') ||
                       await caches.match('/') ||
                       await caches.match(request, { ignoreSearch: true });
        if (cached) {
          // Revalidate in background if online
          fetch(request).then(async (networkResp) => {
            if (networkResp && networkResp.ok) {
              const cache = await caches.open(CACHE_NAME);
              cache.put('/index.html', networkResp.clone());
              cache.put('/', networkResp.clone());
            }
          }).catch(() => {});
          return cached;
        }

        try {
          const networkResp = await fetch(request);
          if (networkResp && networkResp.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put('/index.html', networkResp.clone());
            cache.put('/', networkResp.clone());
          }
          return networkResp;
        } catch (err) {
          const fallback = await caches.match('/index.html') || await caches.match('/');
          if (fallback) return fallback;
          return new Response('<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="background:#0b0f19;color:#fff;font-family:sans-serif;padding:20px;text-align:center;"><h2>SafePlace Offline</h2><p>Please launch from Home Screen or reload.</p></body></html>', {
            headers: { 'Content-Type': 'text/html' }
          });
        }
      })()
    );
    return;
  }

  // 2. Map Tile Requests (OpenStreetMap / CartoDB)
  if (url.hostname.includes('tile.openstreetmap.org') || url.hostname.includes('cartocdn.com')) {
    event.respondWith(
      (async () => {
        const tileCache = await caches.open(TILE_CACHE);
        const cachedTile = await tileCache.match(request);
        if (cachedTile) return cachedTile;

        try {
          const networkTile = await fetch(request);
          if (networkTile && networkTile.ok) {
            tileCache.put(request, networkTile.clone());
          }
          return networkTile;
        } catch (e) {
          // Offline Fallback: Return Dark HUD Tactical Tile
          return new Response(OFFLINE_TILE_SVG, {
            headers: { 'Content-Type': 'image/svg+xml' }
          });
        }
      })()
    );
    return;
  }

  // 3. API GET Requests (/api/pois, /api/safe-bubble, /api/status, etc.)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      (async () => {
        try {
          const networkResp = await fetch(request);
          if (networkResp && networkResp.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, networkResp.clone());
            return networkResp;
          }
        } catch (e) {
          // Network failed, check cache
          const cached = await caches.match(request);
          if (cached) return cached;
          
          // Return valid 503 JSON so client fetch .catch() / !res.ok cleanly executes client offline engine
          return new Response(JSON.stringify({ offline: true, message: "Offline Mode Active" }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
          });
        }
      })()
    );
    return;
  }

  // 4. Static Assets (CSS, JS, Fonts, Images, Manifest)
  event.respondWith(
    (async () => {
      // Cache-first for speed and offline stability
      const cached = await caches.match(request, { ignoreSearch: true });
      if (cached) return cached;

      try {
        const networkResp = await fetch(request);
        if (networkResp && (networkResp.ok || networkResp.type === 'opaque')) {
          const cache = await caches.open(CACHE_NAME);
          cache.put(request, networkResp.clone());
        }
        return networkResp;
      } catch (err) {
        // Fallback for image requests when offline
        if (request.destination === 'image' || url.pathname.match(/\.(png|jpg|jpeg|svg|gif|webp)$/i)) {
          return new Response(OFFLINE_TILE_SVG, { headers: { 'Content-Type': 'image/svg+xml' } });
        }
        // Generic offline fallback
        return new Response('', { status: 408, statusText: 'Offline Asset Unavailable' });
      }
    })()
  );
});
