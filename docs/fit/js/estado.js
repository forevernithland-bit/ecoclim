// Estado global do app (perfil, plano, preferências) + gravação de registros
// que já cuida da fila de sincronização.
import { kvGet, kvSet, salvar, excluir, todos, uid, hojeISO } from "./db.js";
import { enfileirar } from "./nuvem.js";
import { metas, gorduraEstimada } from "./ciencia.js";

export const E = {
  perfil: null,
  plano: null,
  prefs: { intervaloCheckin: 30, semanasCiclo: 6, metaPassos: null, lembretes: true },
  modoLocal: false, // "testar sem conta": nada vai pra nuvem
};

export async function carregarEstado() {
  E.perfil = await kvGet("perfil");
  E.plano = await kvGet("plano");
  E.prefs = { ...E.prefs, ...(await kvGet("prefs", {})) };
  E.modoLocal = await kvGet("modoLocal", false);
}

async function marcarSujo() {
  await kvSet("perfilSujo", true);
  if (!E.modoLocal) import("./nuvem.js").then((m) => m.sincronizar());
}

export async function salvarPerfil(p) {
  // % de gordura sempre recalculado a partir das medidas mais recentes
  p.gordura = gorduraEstimada(p, p.medidas);
  E.perfil = p;
  await kvSet("perfil", p);
  await marcarSujo();
}

export async function salvarPlano(pl) {
  E.plano = pl;
  await kvSet("plano", pl);
  await marcarSujo();
}

export async function salvarPrefs(pr) {
  E.prefs = { ...E.prefs, ...pr };
  await kvSet("prefs", E.prefs);
  await marcarSujo();
}

export function metasAtuais() {
  return E.perfil ? metas(E.perfil) : null;
}

export async function gravar(store, reg) {
  if (!reg.id) reg.id = uid();
  if (!reg.data) reg.data = hojeISO();
  reg.atualizadoEm = Date.now();
  await salvar(store, reg);
  if (!E.modoLocal) await enfileirar(store, reg.id);
  return reg;
}

export async function apagar(store, id) {
  await excluir(store, id);
  if (!E.modoLocal) await enfileirar(store, id, "delete");
}

export async function listar(store, { ordem = "asc" } = {}) {
  const l = await todos(store);
  l.sort((a, b) => (a.data + (a.hora || "") + (a.atualizadoEm || 0)).localeCompare(b.data + (b.hora || "") + (b.atualizadoEm || 0)));
  return ordem === "desc" ? l.reverse() : l;
}

// Métricas do dia: um registro por data (id = "m-AAAA-MM-DD"), campos soltos.
export async function metricasDoDia(data = hojeISO()) {
  const l = await todos("metricas");
  return l.find((m) => m.data === data) || { id: `m-${data}`, data };
}

export async function salvarMetrica(data, campos) {
  const atual = await metricasDoDia(data);
  const novo = { ...atual, ...campos };
  // peso digitado no dia também atualiza o perfil (base dos cálculos)
  if (campos.peso && data === hojeISO() && E.perfil) {
    await salvarPerfil({ ...E.perfil, peso: Number(campos.peso) });
  }
  return gravar("metricas", novo);
}
