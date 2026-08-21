import { getSupabase } from "./supabase-client.js";
import {
  enfileirarMidiaLocal, lerMidiaOutbox, removerDaMidiaOutbox,
  salvarMidiasCache, lerMidiasCache,
} from "./db.js";

const BUCKET = "instalacao-midias";

function tipoDoArquivo(file) {
  const t = file.type || "";
  if (t.startsWith("video")) return "video";
  if (t.startsWith("audio")) return "audio";
  return "foto";
}

// `ref` identifica onde a mídia pertence: { servico_id } (fotos/vídeos de
// uma instalação) ou { visita_id } (fotos/áudio de um item de agenda) —
// mesmo mecanismo pros dois contextos.
function contextoDe(ref) {
  return ref.servico_id ? `servico:${ref.servico_id}` : `visita:${ref.visita_id}`;
}

// Guarda o arquivo localmente (funciona mesmo sem sinal) e tenta subir na
// hora se já tiver internet. Se não tiver, fica na fila até o próximo sync.
export async function adicionarMidia(ref, file, instaladorVinculado) {
  const tipo = tipoDoArquivo(file);
  await enfileirarMidiaLocal(contextoDe(ref), file, tipo);
  await enviarMidiasPendentes(ref, instaladorVinculado);
}

// Sobe pro Storage tudo que está na fila local para este contexto, e insere
// a linha correspondente em servico_midias. Para no primeiro erro (assume
// falta de sinal) — o resto continua na fila pra próxima tentativa.
export async function enviarMidiasPendentes(ref, instaladorVinculado) {
  const contexto = contextoDe(ref);
  const pendentes = await lerMidiaOutbox(contexto);
  if (!pendentes.length) return { enviados: 0 };
  let supabase;
  try {
    supabase = getSupabase();
  } catch (e) {
    return { enviados: 0 };
  }
  let enviados = 0;
  for (const m of pendentes) {
    try {
      const extensao = (m.nome_arquivo.split(".").pop() || "bin").toLowerCase();
      const caminho = `${contexto.replace(":", "_")}/${Date.now()}_${Math.random().toString(36).slice(2, 8)}.${extensao}`;
      const { error: erroUpload } = await supabase.storage.from(BUCKET).upload(caminho, m.file, {
        contentType: m.file.type || undefined,
      });
      if (erroUpload) throw erroUpload;
      const registro = {
        tipo: m.tipo,
        storage_path: caminho,
        nome_arquivo: m.nome_arquivo,
        instalador: instaladorVinculado,
      };
      if (ref.servico_id) registro.servico_id = ref.servico_id;
      if (ref.visita_id) registro.visita_id = ref.visita_id;
      const { error: erroInsert } = await supabase.from("servico_midias").insert(registro);
      if (erroInsert) throw erroInsert;
      await removerDaMidiaOutbox(m.localId);
      enviados++;
    } catch (e) {
      break; // provável falta de sinal — mantém o resto na fila
    }
  }
  return { enviados };
}

// Busca no servidor as mídias já confirmadas deste contexto e atualiza o
// cache local (pra listar mesmo offline depois).
export async function puxarMidias(ref) {
  const contexto = contextoDe(ref);
  try {
    const supabase = getSupabase();
    let q = supabase.from("servico_midias").select("id, tipo, storage_path, nome_arquivo, criado_em");
    q = ref.servico_id ? q.eq("servico_id", ref.servico_id) : q.eq("visita_id", ref.visita_id);
    const { data, error } = await q.order("criado_em", { ascending: true });
    if (error) throw error;
    await salvarMidiasCache(contexto, data || []);
    return data || [];
  } catch (e) {
    return await lerMidiasCache(contexto);
  }
}

export function urlPublicaMidia(storagePath) {
  const supabase = getSupabase();
  const { data } = supabase.storage.from(BUCKET).getPublicUrl(storagePath);
  return data ? data.publicUrl : "";
}

export async function listarPendentesLocal(ref) {
  return await lerMidiaOutbox(contextoDe(ref));
}
