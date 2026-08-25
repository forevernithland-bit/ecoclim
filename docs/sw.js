// Service Worker — cacheia o app shell pra abrir mesmo sem sinal.
// Não intercepta chamadas ao Supabase nem ao esm.sh (essas precisam de rede
// de verdade; os dados offline vêm do IndexedDB, não do cache do SW).
const CACHE = "ecoclim-instalador-v6";
const ARQUIVOS_SHELL = [
  "./",
  "./index.html",
  "./manifest.json",
  "./css/app.css",
  "./js/app.js",
  "./js/auth.js",
  "./js/db.js",
  "./js/sync.js",
  "./js/midias.js",
  "./js/agenda.js",
  "./js/materiais.js",
  "./js/financeiro.js",
  "./js/adiantamentos.js",
  "./js/orcamentos.js",
  "./js/config.js",
  "./js/supabase-client.js",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ARQUIVOS_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((chaves) =>
      Promise.all(chaves.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || event.request.method !== "GET") {
    return; // deixa passar direto pra rede (Supabase, esm.sh, etc.)
  }
  event.respondWith(
    caches.match(event.request).then((cacheado) => {
      const buscaRede = fetch(event.request)
        .then((resp) => {
          const copia = resp.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copia));
          return resp;
        })
        .catch(() => cacheado);
      return cacheado || buscaRede;
    })
  );
});
