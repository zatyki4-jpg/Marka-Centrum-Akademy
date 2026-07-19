const CACHE = "dakpro-v4";
const ASSETS = ["/", "/index.html", "/app.js", "/style.css", "/manifest.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);

 if (
    url.pathname.startsWith("/catalog") ||
    url.pathname.startsWith("/courses") ||
    url.pathname.startsWith("/lessons") ||
    url.pathname.startsWith("/quiz") ||
    url.pathname.startsWith("/enrollments") ||
    url.pathname.startsWith("/stripe") ||
    url.pathname.startsWith("/health")
  ) {
    e.respondWith(fetch(e.request));
    return;
  }

  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});