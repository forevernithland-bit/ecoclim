// Login (Supabase Auth de verdade — fotos do corpo são dado sensível, então
// aqui não repetimos o login "simples" do app do instalador) + sincronização.
//
// Modelo: cada registro local (refeição, check-in, treino, conversa) vira uma
// linha em fit_<store> com a coluna `dados` (jsonb) e as fotos no bucket
// privado fit-fotos/<id do usuário>/... . RLS garante que cada um só vê o seu.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { SUPABASE_URL, SUPABASE_ANON_KEY, BUCKET_FOTOS, SYNC_ATIVO } from "./config.js";
import { salvar, ler, todos, excluir, kvGet, kvSet } from "./db.js";

let _sb = null;
export function sb() {
  if (!_sb) _sb = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, { auth: { persistSession: true, storageKey: "fit-auth" } });
  return _sb;
}

// Quais campos de cada store são fotos (Blob) — vão pro Storage, não pro jsonb.
const CAMPOS_FOTO = { refeicoes: ["foto"], checkins: ["fotoFrente", "fotoLado"], treinos: [], chat: [], metricas: [], comparativos: [] };
const TABELA = { refeicoes: "fit_refeicoes", checkins: "fit_checkins", treinos: "fit_treinos", chat: "fit_chat", metricas: "fit_metricas", comparativos: "fit_comparativos" };

function traduzirErro(e) {
  const m = String((e && e.message) || e || "");
  if (/Invalid login/i.test(m)) return "Usuário ou senha incorretos.";
  if (/already registered|already exists/i.test(m)) return "Esse usuário já tem conta. Toque em 'Já tenho conta'.";
  if (/Password should be/i.test(m)) return "A senha precisa ter pelo menos 6 caracteres.";
  if (/Email not confirmed/i.test(m)) return "Confirme seu e-mail (veja a caixa de entrada) e tente de novo.";
  if (/fetch|network/i.test(m)) return "Sem conexão com a internet.";
  return m || "Algo deu errado.";
}

// Aceita "usuário" simples (ex.: teste) além de e-mail: vira teste@evolua.app.
export function paraEmail(login) {
  const l = String(login || "").trim().toLowerCase();
  return l.includes("@") ? l : `${l.replace(/[^a-z0-9._-]/g, "")}@evolua.app`;
}
// O Supabase exige senha com 6+ caracteres; o app acrescenta um complemento
// fixo pra permitir senhas curtas (ex.: "teste"). Contas antigas, criadas com
// a senha "pura", continuam entrando pelo plano B em entrar().
const COMPLEMENTO = "::evolua";
const senhaReal = (s) => `${s}${COMPLEMENTO}`;

export async function cadastrar(login, senha) {
  if (String(senha || "").length < 4) return { ok: false, erro: "A senha precisa ter pelo menos 4 caracteres." };
  const { data, error } = await sb().auth.signUp({ email: paraEmail(login), password: senhaReal(senha) });
  if (error) return { ok: false, erro: traduzirErro(error) };
  if (!data.session) return { ok: false, confirmar: true, erro: "Enviamos um link de confirmação para o seu e-mail. Confirme e depois entre." };
  return { ok: true, usuario: data.user };
}

export async function entrar(login, senha) {
  const email = paraEmail(login);
  let { data, error } = await sb().auth.signInWithPassword({ email, password: senhaReal(senha) });
  if (error && /Invalid login/i.test(error.message || "") && String(senha).length >= 6) {
    ({ data, error } = await sb().auth.signInWithPassword({ email, password: senha }));
  }
  if (error) return { ok: false, erro: traduzirErro(error) };
  return { ok: true, usuario: data.user };
}

export async function sair() {
  try { await sb().auth.signOut(); } catch (e) { /* offline: a sessão local some igual */ }
}

export async function usuarioAtual() {
  try {
    const { data } = await sb().auth.getSession();
    return data.session ? data.session.user : null;
  } catch (e) { return null; }
}

export async function token() {
  try {
    const { data } = await sb().auth.getSession();
    return data.session ? data.session.access_token : null;
  } catch (e) { return null; }
}

// ---------- Fila de envio ----------
export async function enfileirar(store, id, op = "upsert") {
  await salvar("outbox", { id: `${store}:${id}`, store, registroId: id, op, em: Date.now() });
  agendarSync();
}

let timer = null;
function agendarSync() {
  clearTimeout(timer);
  timer = setTimeout(() => sincronizar().catch(() => {}), 1200);
}

let rodando = false;
const ouvintes = new Set();
export const aoMudarSync = (fn) => ouvintes.add(fn);
const avisar = (s) => ouvintes.forEach((fn) => fn(s));

export async function pendentes() {
  return (await todos("outbox")).length;
}

async function subirFoto(uid, store, id, campo, blob) {
  const caminho = `${uid}/${store}/${id}-${campo}.jpg`;
  const { error } = await sb().storage.from(BUCKET_FOTOS).upload(caminho, blob, { upsert: true, contentType: "image/jpeg" });
  if (error) throw error;
  return caminho;
}

export async function sincronizar() {
  if (!SYNC_ATIVO || rodando || !navigator.onLine) return;
  const user = await usuarioAtual();
  if (!user) return;
  rodando = true;
  avisar("sincronizando");
  try {
    // Perfil + plano: uma linha por usuário.
    if (await kvGet("perfilSujo")) {
      const perfil = await kvGet("perfil");
      const plano = await kvGet("plano");
      const prefs = await kvGet("prefs");
      const em = new Date().toISOString();
      const { error } = await sb().from("fit_perfis").upsert({ usuario_id: user.id, dados: { perfil, plano, prefs }, atualizado_em: em });
      if (error) throw error;
      await kvSet("perfilSujo", false);
      await kvSet("perfilRemotoEm", em);
    }
    const fila = (await todos("outbox")).sort((a, b) => a.em - b.em);
    for (const item of fila) {
      const tabela = TABELA[item.store];
      if (item.op === "delete") {
        const { error } = await sb().from(tabela).update({ dados: { excluido: true }, atualizado_em: new Date().toISOString() }).eq("id", item.registroId);
        if (error) throw error;
      } else {
        const reg = await ler(item.store, item.registroId);
        if (reg) {
          const dados = { ...reg };
          const fotos = {};
          for (const campo of CAMPOS_FOTO[item.store]) {
            if (reg[campo] instanceof Blob) {
              fotos[campo] = await subirFoto(user.id, item.store, reg.id, campo, reg[campo]);
            } else if (reg[`${campo}Path`]) {
              fotos[campo] = reg[`${campo}Path`];
            }
            delete dados[campo];
          }
          dados.fotos = fotos;
          const { error } = await sb().from(tabela).upsert({ id: reg.id, usuario_id: user.id, data: reg.data, dados, atualizado_em: new Date().toISOString() });
          if (error) throw error;
        }
      }
      await excluir("outbox", item.id);
    }
    avisar("ok");
  } catch (e) {
    console.warn("sync", e);
    avisar("erro");
  } finally {
    rodando = false;
  }
}

// Novo aparelho: baixa tudo do usuário. Fotos dos check-ins são baixadas
// (são poucas e precisam funcionar offline); as de refeição ficam só com o
// caminho e carregam sob demanda.
export async function puxarTudo() {
  const user = await usuarioAtual();
  if (!user) return false;
  const { data: perfilRow } = await sb().from("fit_perfis").select("dados").eq("usuario_id", user.id).maybeSingle();
  if (perfilRow && perfilRow.dados) {
    const { perfil, plano, prefs } = perfilRow.dados;
    if (perfil) await kvSet("perfil", perfil);
    if (plano) await kvSet("plano", plano);
    if (prefs) await kvSet("prefs", prefs);
  }
  for (const [store, tabela] of Object.entries(TABELA)) {
    const { data, error } = await sb().from(tabela).select("id,data,dados").eq("usuario_id", user.id).order("data", { ascending: true }).limit(5000);
    if (error || !data) continue;
    for (const row of data) {
      if (row.dados && row.dados.excluido) continue;
      const reg = { ...row.dados, id: row.id, data: row.data };
      const fotos = reg.fotos || {};
      delete reg.fotos;
      for (const [campo, caminho] of Object.entries(fotos)) {
        reg[`${campo}Path`] = caminho;
        if (store === "checkins") {
          const { data: blob } = await sb().storage.from(BUCKET_FOTOS).download(caminho);
          if (blob) reg[campo] = blob;
        }
      }
      await salvar(store, reg);
    }
  }
  // a partir daqui, puxarNovidades() só busca o que mudar
  const agora = new Date(Date.now()).toISOString();
  for (const store of Object.keys(TABELA)) await kvSet(`puxadoEm:${store}`, agora);
  await kvSet("perfilRemotoEm", agora);
  return !!perfilRow;
}

// ---------- Receber o que outros aparelhos enviaram ----------
// Busca, em cada tabela, as linhas alteradas desde a última vez (com 10 min
// de folga pra relógios diferentes entre celular e computador). Registro com
// alteração local ainda na fila não é sobrescrito. Na 1ª vez (sem carimbo),
// compara tudo e remove daqui o que já não existe na nuvem.
let puxando = false;
const FOLGA = 10 * 60 * 1000;
export async function puxarNovidades() {
  if (!SYNC_ATIVO || puxando || !navigator.onLine) return false;
  const user = await usuarioAtual();
  if (!user) return false;
  puxando = true;
  let mudou = false;
  try {
    // Perfil/plano: vale o mais novo (se aqui não tem alteração esperando envio)
    if (!(await kvGet("perfilSujo"))) {
      const { data: row } = await sb().from("fit_perfis").select("dados,atualizado_em").eq("usuario_id", user.id).maybeSingle();
      const local = await kvGet("perfilRemotoEm", null);
      if (row && row.dados && (!local || Date.parse(row.atualizado_em) > Date.parse(local))) {
        const { perfil, plano, prefs } = row.dados;
        if (perfil) await kvSet("perfil", perfil);
        if (plano) await kvSet("plano", plano);
        if (prefs) await kvSet("prefs", prefs);
        await kvSet("perfilRemotoEm", row.atualizado_em);
        mudou = true;
      }
    }
    for (const [store, tabela] of Object.entries(TABELA)) {
      const pend = new Set((await todos("outbox")).filter((o) => o.store === store).map((o) => o.registroId));
      const desde = await kvGet(`puxadoEm:${store}`, null);
      const linhas = [];
      for (let de = 0; de < 20000; de += 1000) {
        let q = sb().from(tabela).select("id,data,dados,atualizado_em").eq("usuario_id", user.id);
        if (desde) q = q.gt("atualizado_em", new Date(Date.parse(desde) - FOLGA).toISOString());
        const { data, error } = await q.order("atualizado_em", { ascending: true }).range(de, de + 999);
        if (error) throw error;
        linhas.push(...data);
        if (data.length < 1000) break;
      }
      let maior = desde;
      const naNuvem = new Set();
      for (const row of linhas) {
        if (!maior || Date.parse(row.atualizado_em) > Date.parse(maior)) maior = row.atualizado_em;
        if (pend.has(row.id)) continue;
        const local = await ler(store, row.id);
        if (row.dados && row.dados.excluido) {
          if (local) { await excluir(store, row.id); mudou = true; }
          continue;
        }
        naNuvem.add(row.id);
        const reg = { ...row.dados, id: row.id, data: row.data };
        const fotos = reg.fotos || {};
        delete reg.fotos;
        for (const [campo, caminho] of Object.entries(fotos)) {
          reg[`${campo}Path`] = caminho;
          if (local && local[campo] instanceof Blob) reg[campo] = local[campo];
          else if (store === "checkins") {
            const { data: blob } = await sb().storage.from(BUCKET_FOTOS).download(caminho);
            if (blob) reg[campo] = blob;
          }
        }
        if (!local || (reg.atualizadoEm || 0) > (local.atualizadoEm || 0) || (!reg.atualizadoEm && JSON.stringify({ ...local, ...reg }) !== JSON.stringify(local))) {
          await salvar(store, { ...(local || {}), ...reg });
          mudou = true;
        }
      }
      if (!desde) {
        // 1ª comparação completa: o que só existe aqui (e não está na fila) foi apagado em outro aparelho
        for (const r of await todos(store)) {
          if (!naNuvem.has(r.id) && !pend.has(r.id)) { await excluir(store, r.id); mudou = true; }
        }
      }
      if (maior) await kvSet(`puxadoEm:${store}`, maior);
      else if (!desde) await kvSet(`puxadoEm:${store}`, new Date().toISOString());
    }
  } catch (e) {
    console.warn("puxar", e);
  } finally {
    puxando = false;
  }
  if (mudou) avisar("atualizado");
  return mudou;
}

// Envia o que é daqui e depois recebe o que veio de outros aparelhos.
export async function sincronizarTudo() {
  await sincronizar();
  if (!(await pendentes())) await puxarNovidades();
}

// Foto que só existe na nuvem (refeição de outro aparelho): URL temporária.
export async function urlFotoRemota(caminho) {
  const { data } = await sb().storage.from(BUCKET_FOTOS).createSignedUrl(caminho, 3600);
  return data ? data.signedUrl : "";
}

// ---------- Base de alimentos compartilhada (fit_alimentos) ----------
// Baixa a tabela inteira (algumas centenas de linhas) no máx. a cada 12 h e
// guarda no aparelho — é ela que evita chamar a IA para alimentos conhecidos.
export async function baixarAlimentos({ forcar = false } = {}) {
  try {
    const atual = await kvGet("alimentosDB", null);
    if (!forcar && atual && Date.now() - (atual.em || 0) < 12 * 3600 * 1000) return;
    const lista = [];
    for (let de = 0; de < 5000; de += 1000) {
      const { data, error } = await sb().from("fit_alimentos").select("nome,chaves,kcal,p,c,g,porcao,unidade,fonte").range(de, de + 999);
      if (error) return; // tabela ainda não criada: segue com a base embarcada
      lista.push(...data.map((x) => ({ ...x, kcal: +x.kcal, p: +x.p, c: +x.c, g: +x.g, porcao: +x.porcao })));
      if (data.length < 1000) break;
    }
    const { atualizarBaseDoBanco } = await import("./alimentos.js");
    await atualizarBaseDoBanco(lista);
  } catch (e) { /* offline */ }
}

// A IA descobriu um alimento novo → vira base pra todo mundo (só insere; a
// base TACO não pode ser alterada pelo app — regra no Supabase).
export async function salvarAlimentoNoBanco(item) {
  try {
    if (!(await usuarioAtual())) return;
    await sb().from("fit_alimentos").insert({
      nome: item.nome, chaves: item.chaves, kcal: item.kcal, p: item.p, c: item.c, g: item.g,
      porcao: item.porcao, unidade: item.unidade, fonte: "ia",
    });
  } catch (e) { /* já existe ou offline: tudo bem */ }
}

export function iniciarSyncAutomatico() {
  window.addEventListener("online", () => sincronizarTudo());
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") sincronizarTudo(); });
  setInterval(() => sincronizarTudo(), 60000);
  baixarAlimentos();
}
