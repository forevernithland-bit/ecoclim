// Service Worker — cacheia o app pra abrir sem sinal. Não intercepta Supabase,
// esm.sh nem a API (essas precisam de rede; os dados offline vêm do IndexedDB).
// ⚠️ Suba a versão do CACHE (e js/versao.js) a cada publicação.
const CACHE = "evolua-v22";
const ARQUIVOS = [
  "./", "./index.html", "./manifest.json", "./css/app.css",
  "./js/app.js", "./js/versao.js", "./js/config.js", "./js/db.js", "./js/estado.js", "./js/nuvem.js", "./js/ia.js",
  "./js/ui.js", "./js/midia.js", "./js/camera.js", "./js/ciencia.js", "./js/treino.js", "./js/alimentos.js", "./js/suplementos.js", "./js/gostos.js", "./js/fisico-arte.js", "./js/instalar.js", "./js/sessao.js", "./js/interpretar-treino.js", "./js/nutri-insights.js", "./js/calibracao.js", "./js/emoji-comida.js", "./js/esportes.js", "./js/medicamentos.js",
  "./js/telas/onboarding.js", "./js/telas/hoje.js", "./js/telas/comida.js", "./js/telas/treino.js",
  "./js/telas/evolucao.js", "./js/telas/coach.js", "./js/telas/perfil.js", "./js/telas/relatorio.js", "./js/telas/adicionar-exercicio.js", "./js/telas/esporte.js",
  "./data/alimentos.json", "./icons/icon-192.png", "./icons/icon-512.png", "./icons/icon-192-maskable.png", "./icons/icon-512-maskable.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ARQUIVOS.map((u) => new Request(u, { cache: "reload" })))).catch(() => {}));
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
    // "no-cache" = sempre confere com o servidor se o arquivo mudou (o GitHub
    // Pages manda o navegador guardar por 10 min — sem isso a atualização atrasava)
    fetch(e.request, { cache: "no-cache" })
      .then((resp) => {
        const copia = resp.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copia));
        return resp;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match("./index.html")))
  );
});

// Toque na notificação ("deu o tempo do treino") → abre/foca o app
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil((async () => {
    const janelas = await clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const j of janelas) if (j.url.includes(self.registration.scope)) return j.focus();
    return clients.openWindow("./index.html");
  })());
});
