// Service Worker — cacheia o app shell pra abrir mesmo sem sinal.
// Não intercepta chamadas ao Supabase nem ao esm.sh (essas precisam de rede
// de verdade; os dados offline vêm do IndexedDB, não do cache do SW).
const CACHE = "ecoclim-instalador-v17";
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
  "./js/lembretes.js",
  "./js/materiais.js",
  "./js/financeiro.js",
  "./js/adiantamentos.js",
  "./js/orcamentos.js",
  "./js/push.js",
  "./js/movimentacoes.js",
  "./js/atualizacao.js",
  "./js/config.js",
  "./js/supabase-client.js",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-192-maskable.png",
  "./icons/icon-512-maskable.png",
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

// ---------- Notificações push ----------
// Chega aqui mesmo com o app fechado — é o Service Worker que acorda. No
// iPhone isso só acontece se o app tiver sido instalado na tela inicial
// (regra da Apple), no Android funciona nos dois casos.
self.addEventListener("push", (event) => {
  let dados = {};
  try {
    dados = event.data ? event.data.json() : {};
  } catch (e) {
    dados = { title: "Ecoclim", body: event.data ? event.data.text() : "" };
  }

  const titulo = dados.title || "Ecoclim";
  const opcoes = {
    body: dados.body || "",
    icon: "./icons/icon-192.png",
    badge: "./icons/icon-192-maskable.png",
    // `tag` faz o aviso novo substituir o anterior do mesmo assunto, em vez de
    // empilhar cinco notificações iguais na barra.
    tag: dados.tag || "ecoclim",
    renotify: true,
    data: { url: dados.url || "./index.html" },
    vibrate: [80, 40, 80],
  };

  event.waitUntil((async () => {
    await self.registration.showNotification(titulo, opcoes);
    // Selo com número no ícone do app (Android; iOS ignora sem reclamar).
    if (self.navigator && "setAppBadge" in self.navigator) {
      try { await self.navigator.setAppBadge(dados.badge || 1); } catch (e) {}
    }
  })());
});

// Tocar na notificação: traz a janela já aberta pra frente em vez de abrir
// outra — quem está no meio de um preenchimento não pode perder a tela.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const destino = (event.notification.data && event.notification.data.url) || "./index.html";
  event.waitUntil((async () => {
    if (self.navigator && "clearAppBadge" in self.navigator) {
      try { await self.navigator.clearAppBadge(); } catch (e) {}
    }
    const janelas = await clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const j of janelas) {
      if (j.url.includes(self.location.origin)) return j.focus();
    }
    return clients.openWindow(destino);
  })());
});

// A tela pede a troca imediata quando o usuário toca em "Atualizar" — sem
// isso, a versão nova só assumiria quando todas as abas do app fossem
// fechadas, que é justamente o que queremos evitar que ele tenha que fazer.
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
});
