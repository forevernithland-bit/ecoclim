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
      const { error } = await sb().from("fit_perfis").upsert({ usuario_id: user.id, dados: { perfil, plano, prefs }, atualizado_em: new Date().toISOString() });
      if (error) throw error;
      await kvSet("perfilSujo", false);
    }
    const fila = (await todos("outbox")).sort((a, b) => a.em - b.em);
    for (const item of fila) {
      const tabela = TABELA[item.store];
      if (item.op === "delete") {
        const { error } = await sb().from(tabela).delete().eq("id", item.registroId);
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
  return !!perfilRow;
}

// Foto que só existe na nuvem (refeição de outro aparelho): URL temporária.
export async function urlFotoRemota(caminho) {
  const { data } = await sb().storage.from(BUCKET_FOTOS).createSignedUrl(caminho, 3600);
  return data ? data.signedUrl : "";
}

export function iniciarSyncAutomatico() {
  window.addEventListener("online", () => sincronizar());
  setInterval(() => sincronizar(), 60000);
  sincronizar();
}
