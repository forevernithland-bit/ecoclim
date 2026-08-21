import { getSupabase } from "./supabase-client.js";
import {
  enfileirarMidiaLocal, lerMidiaOutbox, removerDaMidiaOutbox,
  salvarMidiasCache, lerMidiasCache,
} from "./db.js";

const BUCKET = "instalacao-midias";

function tipoDoArquivo(file) {
  return (file.type || "").startsWith("video") ? "video" : "foto";
}

// Guarda o arquivo localmente (funciona mesmo sem sinal) e tenta subir na
// hora se já tiver internet. Se não tiver, fica na fila até o próximo sync.
export async function adicionarMidia(servicoId, file, instaladorVinculado) {
  const tipo = tipoDoArquivo(file);
  await enfileirarMidiaLocal(servicoId, file, tipo);
  await enviarMidiasPendentes(servicoId, instaladorVinculado);
}

// Sobe pro Storage tudo que está na fila local para este serviço, e insere
// a linha correspondente em servico_midias. Para no primeiro erro (assume
// falta de sinal) — o resto continua na fila pra próxima tentativa.
export async function enviarMidiasPendentes(servicoId, instaladorVinculado) {
  const pendentes = await lerMidiaOutbox(servicoId);
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
      const caminho = `${servicoId}/${Date.now()}_${Math.random().toString(36).slice(2, 8)}.${extensao}`;
      const { error: erroUpload } = await supabase.storage.from(BUCKET).upload(caminho, m.file, {
        contentType: m.file.type || undefined,
      });
      if (erroUpload) throw erroUpload;
      const { error: erroInsert } = await supabase.from("servico_midias").insert({
        servico_id: servicoId,
        tipo: m.tipo,
        storage_path: caminho,
        nome_arquivo: m.nome_arquivo,
        instalador: instaladorVinculado,
      });
      if (erroInsert) throw erroInsert;
      await removerDaMidiaOutbox(m.localId);
      enviados++;
    } catch (e) {
      break; // provável falta de sinal — mantém o resto na fila
    }
  }
  return { enviados };
}

// Busca no servidor as mídias já confirmadas deste serviço e atualiza o
// cache local (pra listar mesmo offline depois).
export async function puxarMidias(servicoId) {
  try {
    const supabase = getSupabase();
    const { data, error } = await supabase
      .from("servico_midias")
      .select("id, tipo, storage_path, nome_arquivo, criado_em")
      .eq("servico_id", servicoId)
      .order("criado_em", { ascending: true });
    if (error) throw error;
    await salvarMidiasCache(servicoId, data || []);
    return data || [];
  } catch (e) {
    return await lerMidiasCache(servicoId);
  }
}

export function urlPublicaMidia(storagePath) {
  const supabase = getSupabase();
  const { data } = supabase.storage.from(BUCKET).getPublicUrl(storagePath);
  return data ? data.publicUrl : "";
}

export { lerMidiaOutbox as listarPendentesLocal };
