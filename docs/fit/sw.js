// Service Worker — cacheia o app pra abrir sem sinal. Não intercepta Supabase,
// esm.sh nem a API (essas precisam de rede; os dados offline vêm do IndexedDB).
// ⚠️ Suba a versão do CACHE (e js/versao.js) a cada publicação.
const CACHE = "evolua-v4";
const ARQUIVOS = [
  "./", "./index.html", "./manifest.json", "./css/app.css",
  "./js/app.js", "./js/versao.js", "./js/config.js", "./js/db.js", "./js/estado.js", "./js/nuvem.js", "./js/ia.js",
  "./js/ui.js", "./js/midia.js", "./js/camera.js", "./js/ciencia.js", "./js/treino.js", "./js/alimentos.js", "./js/suplementos.js", "./js/gostos.js", "./js/fisico-arte.js",
  "./js/telas/onboarding.js", "./js/telas/hoje.js", "./js/telas/comida.js", "./js/telas/treino.js",
  "./js/telas/evolucao.js", "./js/telas/coach.js", "./js/telas/perfil.js",
  "./icons/icon-192.png", "./icons/icon-512.png", "./icons/icon-192-maskable.png", "./icons/icon-512-maskable.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ARQUIVOS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

// Rede primeiro para o app (pega versão nova assim que publicada), cache se offline.
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin || e.request.method !== "GET") return;
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        const copia = resp.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copia));
        return resp;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match("./index.html")))
  );
});
