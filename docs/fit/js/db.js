// Banco local (IndexedDB). O app é "local primeiro": tudo é salvo aqui na hora
// (funciona sem sinal) e o sync.js manda pro Supabase quando houver internet.
const NOME = "fit-app";
const VERSAO = 1;
export const STORES = ["kv", "refeicoes", "checkins", "treinos", "chat", "metricas", "comparativos", "outbox"];

let _db = null;
function abrir() {
  if (_db) return Promise.resolve(_db);
  return new Promise((res, rej) => {
    const req = indexedDB.open(NOME, VERSAO);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("kv")) db.createObjectStore("kv");
      for (const s of ["refeicoes", "checkins", "treinos", "chat", "metricas", "comparativos"]) {
        if (!db.objectStoreNames.contains(s)) {
          const st = db.createObjectStore(s, { keyPath: "id" });
          st.createIndex("data", "data");
        }
      }
      if (!db.objectStoreNames.contains("outbox")) db.createObjectStore("outbox", { keyPath: "id" });
    };
    req.onsuccess = () => { _db = req.result; res(_db); };
    req.onerror = () => rej(req.error);
  });
}

function tx(store, modo, fn) {
  return abrir().then((db) => new Promise((res, rej) => {
    const t = db.transaction(store, modo);
    const st = t.objectStore(store);
    let resultado;
    Promise.resolve(fn(st)).then((r) => { resultado = r; });
    t.oncomplete = () => res(resultado);
    t.onerror = () => rej(t.error);
  }));
}

const pedir = (req) => new Promise((res, rej) => { req.onsuccess = () => res(req.result); req.onerror = () => rej(req.error); });

export const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`);

export async function kvGet(chave, padrao = null) {
  const v = await tx("kv", "readonly", (st) => pedir(st.get(chave)));
  return v === undefined ? padrao : v;
}
export const kvSet = (chave, valor) => tx("kv", "readwrite", (st) => pedir(st.put(valor, chave)));

export const salvar = (store, obj) => tx(store, "readwrite", (st) => pedir(st.put(obj)));
export const ler = (store, id) => tx(store, "readonly", (st) => pedir(st.get(id)));
export const excluir = (store, id) => tx(store, "readwrite", (st) => pedir(st.delete(id)));
export const todos = (store) => tx(store, "readonly", (st) => pedir(st.getAll()));

export async function porData(store, dataISO) {
  return tx(store, "readonly", (st) => pedir(st.index("data").getAll(IDBKeyRange.only(dataISO))));
}

export async function limparTudo() {
  const db = await abrir();
  await Promise.all(STORES.map((s) => new Promise((res) => {
    const t = db.transaction(s, "readwrite");
    t.objectStore(s).clear();
    t.oncomplete = res;
  })));
}

export function hojeISO(d = new Date()) {
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}
