/**
 * ClinNote AI Service Worker
 * Provides offline capability and caching strategy
 * HIPAA Note: PHI data is NOT cached — only static assets and non-sensitive API responses
 */

const CACHE_VERSION = 'v1';
const STATIC_CACHE = `clinnote-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `clinnote-dynamic-${CACHE_VERSION}`;

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icons/medical-cross.svg',
  '/icons/mic.svg',
  '/icons/clipboard.svg',
];

// API routes that should NOT be cached (PHI data)
const NO_CACHE_PATTERNS = [
  /\/api\/v1\/recordings/,
  /\/api\/v1\/transcripts/,
  /\/api\/v1\/notes/,
  /\/api\/v1\/patients/,
  /\/api\/v1\/audit/,
  /\/ws\//,
];

// Install event — cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate event — clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE && name !== DYNAMIC_CACHE)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Fetch event — cache strategy
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') return;

  // Skip WebSocket connections
  if (url.protocol === 'ws:' || url.protocol === 'wss:') return;

  // Skip PHI-containing API routes — always network first, no cache
  const isNoCacheRoute = NO_CACHE_PATTERNS.some((pattern) => pattern.test(url.pathname));
  if (isNoCacheRoute) {
    event.respondWith(fetch(request));
    return;
  }

  // For static assets: Cache First strategy
  if (request.destination === 'script' ||
      request.destination === 'style' ||
      request.destination === 'image' ||
      request.destination === 'font') {
    event.respondWith(
      caches.match(request).then((cached) => {
        return cached || fetch(request).then((response) => {
          const clone = response.clone();
          caches.open(STATIC_CACHE).then((cache) => cache.put(request, clone));
          return response;
        });
      })
    );
    return;
  }

  // For navigation requests: Network First with cache fallback
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const clone = response.clone();
          caches.open(DYNAMIC_CACHE).then((cache) => cache.put(request, clone));
          return response;
        })
        .catch(() => {
          return caches.match(request) || caches.match('/index.html');
        })
    );
    return;
  }

  // For safe API routes (ICD search, auth): Network First
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request)
        .then((response) => response)
        .catch(() => caches.match(request))
    );
    return;
  }

  // Default: Network First
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});

// Background sync for offline note saves
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-note-draft') {
    event.waitUntil(syncNoteDraft());
  }
});

async function syncNoteDraft() {
  const db = await openDB();
  const drafts = await db.getAll('drafts');
  for (const draft of drafts) {
    try {
      await fetch('/api/v1/notes/' + draft.id, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft.data)
      });
      await db.delete('drafts', draft.id);
    } catch (e) {
      console.warn('Failed to sync draft:', e);
    }
  }
}

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('clinnote-offline', 1);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('drafts')) {
        db.createObjectStore('drafts', { keyPath: 'id' });
      }
    };
  });
}
