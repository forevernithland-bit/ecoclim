// Armazenamento local (IndexedDB) — cache dos serviços do instalador logado
// (pra abrir a lista mesmo sem sinal) e uma fila de escrita ("outbox") para
// comentário/conclusão feitos offline, sincronizada depois.
const DB_NAME = "ecoclim_instalador";
const DB_VERSION = 1;

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("sessao")) {
        db.createObjectStore("sessao", { keyPath: "chave" });
      }
      if (!db.objectStoreNames.contains("servicos")) {
        db.createObjectStore("servicos", { keyPath: "id" });
      }
      if (!db.objectStoreNames.contains("outbox")) {
        db.createObjectStore("outbox", { keyPath: "localId", autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx(storeName, mode, fn) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const t = db.transaction(storeName, mode);
    const store = t.objectStore(storeName);
    const result = fn(store);
    t.oncomplete = () => resolve(result);
    t.onerror = () => reject(t.error);
  });
}

// ---------- Sessão (usuário logado, guardada localmente p/ abrir offline) ----------
export async function salvarSessao(sessao) {
  await tx("sessao", "readwrite", (s) => s.put({ chave: "atual", ...sessao }));
}

export async function lerSessao() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const req = db.transaction("sessao", "readonly").objectStore("sessao").get("atual");
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

export async function limparSessao() {
  await tx("sessao", "readwrite", (s) => s.clear());
}

// ---------- Cache dos serviços (lista + detalhe) ----------
// Cada chamada representa a lista COMPLETA e autoritativa do instalador
// logado (é isso que puxarServicos() sempre busca) — por isso o cache é
// substituído por inteiro (clear + put), não só acrescentado. Assim, se um
// serviço deixar de pertencer a este instalador (reatribuído, etc.) ele
// some do aparelho, em vez de ficar preso pra sempre no cache local.
export async function salvarServicos(lista) {
  await tx("servicos", "readwrite", (s) => {
    s.clear();
    for (const item of lista) s.put(item);
  });
}

// Limpa o cache local de serviços. Chamado no logout — essencial em
// aparelhos compartilhados entre instaladores: sem isso, os dados do
// instalador anterior (nome, telefone, endereço, valor) continuariam
// visíveis pro próximo que logar no mesmo aparelho, mesmo antes da
// primeira sincronização dele terminar.
export async function limparServicos() {
  await tx("servicos", "readwrite", (s) => s.clear());
}

export async function lerServicos() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const req = db.transaction("servicos", "readonly").objectStore("servicos").getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

export async function lerServico(id) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const req = db.transaction("servicos", "readonly").objectStore("servicos").get(id);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

// Aplica uma alteração já no cache local, pra tela refletir na hora
// (mesmo antes de sincronizar com o servidor).
export async function aplicarPatchLocal(servicoId, patch) {
  await tx("servicos", "readwrite", (s) => {
    const req = s.get(servicoId);
    req.onsuccess = () => {
      const atual = req.result;
      if (atual) s.put({ ...atual, ...patch });
    };
  });
}

// ---------- Outbox (fila de escrita pendente) ----------
export async function enfileirar(servicoId, patch) {
  const item = { servico_id: servicoId, patch, criado_em: new Date().toISOString() };
  await tx("outbox", "readwrite", (s) => s.add(item));
  await aplicarPatchLocal(servicoId, patch);
}

export async function lerOutbox() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const req = db.transaction("outbox", "readonly").objectStore("outbox").getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

export async function removerDaOutbox(localId) {
  await tx("outbox", "readwrite", (s) => s.delete(localId));
}
