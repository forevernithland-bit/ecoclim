// Armazenamento local (IndexedDB) — cache dos serviços do instalador logado
// (pra abrir a lista mesmo sem sinal) e uma fila de escrita ("outbox") para
// comentário/conclusão feitos offline, sincronizada depois.
const DB_NAME = "ecoclim_instalador";
const DB_VERSION = 3;

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
      // Fila de fotos/vídeos ainda não enviados (guarda o Blob local até ter
      // sinal). Separada da outbox porque o payload é binário, não um patch.
      if (!db.objectStoreNames.contains("midia_outbox")) {
        db.createObjectStore("midia_outbox", { keyPath: "localId", autoIncrement: true });
      }
      // Cache das mídias já confirmadas no servidor, pra listar mesmo offline.
      if (!db.objectStoreNames.contains("midias_cache")) {
        const s = db.createObjectStore("midias_cache", { keyPath: "id" });
        s.createIndex("servico_id", "servico_id", { unique: false });
      }
      // Cache genérico por tabela (agenda_visitas, listas_materiais,
      // materiais_padrao) — evita criar um object store novo pra cada tela.
      if (!db.objectStoreNames.contains("cache_generico")) {
        const s = db.createObjectStore("cache_generico", { keyPath: "_chave" });
        s.createIndex("tabela", "_tabela", { unique: false });
      }
      // Fila genérica de criação/edição feita offline (agenda, materiais) —
      // sempre um upsert numa tabela ao sincronizar, diferente da `outbox`
      // (que só faz update em serviço já existente).
      if (!db.objectStoreNames.contains("criacoes_outbox")) {
        db.createObjectStore("criacoes_outbox", { keyPath: "localId", autoIncrement: true });
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

// ---------- Fila de fotos/vídeos/áudios (fila de escrita binária) ----------
// "contexto" identifica onde a mídia pertence: "servico:123" (instalação) ou
// "visita:45" (item de agenda) — mesmo mecanismo pros dois, sem precisar de
// object stores/índices separados. Guardado no campo `servico_id` por
// simplicidade (nome antigo, mas aceita qualquer string de contexto).
export async function enfileirarMidiaLocal(contexto, file, tipo) {
  const item = {
    servico_id: contexto, tipo, file,
    nome_arquivo: file.name || `${tipo}_${Date.now()}`,
    criado_em: new Date().toISOString(),
  };
  return await tx("midia_outbox", "readwrite", (s) => s.add(item));
}

export async function lerMidiaOutbox(contexto) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const req = db.transaction("midia_outbox", "readonly").objectStore("midia_outbox").getAll();
    req.onsuccess = () => resolve((req.result || []).filter((m) => m.servico_id === contexto));
    req.onerror = () => reject(req.error);
  });
}

export async function removerDaMidiaOutbox(localId) {
  await tx("midia_outbox", "readwrite", (s) => s.delete(localId));
}

// ---------- Cache de mídias já confirmadas no servidor ----------
export async function salvarMidiasCache(contexto, lista) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const t = db.transaction("midias_cache", "readwrite");
    const store = t.objectStore("midias_cache");
    const idx = store.index("servico_id");
    const range = IDBKeyRange.only(contexto);
    const cursorReq = idx.openCursor(range);
    cursorReq.onsuccess = () => {
      const cursor = cursorReq.result;
      if (cursor) { cursor.delete(); cursor.continue(); }
      else { for (const item of lista) store.put({ ...item, servico_id: contexto }); }
    };
    t.oncomplete = () => resolve();
    t.onerror = () => reject(t.error);
  });
}

export async function lerMidiasCache(contexto) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const idx = db.transaction("midias_cache", "readonly").objectStore("midias_cache").index("servico_id");
    const req = idx.getAll(IDBKeyRange.only(contexto));
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

// ---------- Cache genérico por tabela (Agenda / Materiais) ----------
export async function salvarCacheTabela(tabela, lista) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const t = db.transaction("cache_generico", "readwrite");
    const store = t.objectStore("cache_generico");
    const idx = store.index("tabela");
    const cursorReq = idx.openCursor(IDBKeyRange.only(tabela));
    cursorReq.onsuccess = () => {
      const cursor = cursorReq.result;
      if (cursor) { cursor.delete(); cursor.continue(); }
      else { for (const item of lista) store.put({ ...item, _chave: `${tabela}:${item.id}`, _tabela: tabela }); }
    };
    t.oncomplete = () => resolve();
    t.onerror = () => reject(t.error);
  });
}

export async function lerCacheTabela(tabela) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const idx = db.transaction("cache_generico", "readonly").objectStore("cache_generico").index("tabela");
    const req = idx.getAll(IDBKeyRange.only(tabela));
    req.onsuccess = () => resolve((req.result || []).map(({ _chave, _tabela, ...resto }) => resto));
    req.onerror = () => reject(req.error);
  });
}

// Aplica uma edição direto no cache local (mesma ideia do aplicarPatchLocal
// dos serviços) — pra tela refletir na hora, mesmo antes de sincronizar.
export async function aplicarPatchCacheGenerico(tabela, id, patch) {
  await tx("cache_generico", "readwrite", (s) => {
    const chave = `${tabela}:${id}`;
    const req = s.get(chave);
    req.onsuccess = () => {
      const atual = req.result;
      if (atual) s.put({ ...atual, ...patch });
    };
  });
}

// ---------- Fila genérica de criação/edição (upsert ao sincronizar) ----------
export async function enfileirarCriacao(tabela, dados) {
  const item = { tabela, dados, criado_em: new Date().toISOString() };
  return await tx("criacoes_outbox", "readwrite", (s) => s.add(item));
}

export async function lerCriacoesOutbox(tabela) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const req = db.transaction("criacoes_outbox", "readonly").objectStore("criacoes_outbox").getAll();
    req.onsuccess = () => {
      const todos = req.result || [];
      resolve(tabela ? todos.filter((i) => i.tabela === tabela) : todos);
    };
    req.onerror = () => reject(req.error);
  });
}

export async function removerDaCriacoesOutbox(localId) {
  await tx("criacoes_outbox", "readwrite", (s) => s.delete(localId));
}

// Edita algo que ainda está na fila — criado offline, então sem id do servidor
// pra atualizar por lá. Sem isso, quem montasse uma lista sem sinal ficaria
// sem poder corrigir um item errado até o sinal voltar.
export async function atualizarCriacaoOutbox(localId, dados) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const store = db.transaction("criacoes_outbox", "readwrite").objectStore("criacoes_outbox");
    const req = store.get(localId);
    req.onsuccess = () => {
      const item = req.result;
      if (!item) return resolve(false);
      item.dados = { ...item.dados, ...dados };
      const put = store.put(item);
      put.onsuccess = () => resolve(true);
      put.onerror = () => reject(put.error);
    };
    req.onerror = () => reject(req.error);
  });
}
