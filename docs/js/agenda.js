import { getSupabase } from "./supabase-client.js";
import { salvarCacheTabela, lerCacheTabela, enfileirarCriacao, aplicarPatchCacheGenerico, lerCriacoesOutbox } from "./db.js";

const TABELA = "agenda_visitas";

export async function puxarVisitas(instaladorVinculado) {
  try {
    const supabase = getSupabase();
    const { data, error } = await supabase
      .from(TABELA)
      .select("*")
      .eq("instalador", instaladorVinculado)
      .order("data_hora", { ascending: true });
    if (error) throw error;
    await salvarCacheTabela(TABELA, data || []);
    return data || [];
  } catch (e) {
    return await lerCacheTabela(TABELA);
  }
}

// Visitas criadas offline, ainda sem id real do servidor.
export async function visitasPendentesNovas() {
  const pendentes = await lerCriacoesOutbox(TABELA);
  return pendentes.filter((p) => !p.dados.id);
}

export async function criarVisita(visita) {
  await enfileirarCriacao(TABELA, visita);
}

export async function atualizarStatusVisita(visita, novoStatus) {
  const dados = { ...visita, status: novoStatus };
  await enfileirarCriacao(TABELA, dados);
  if (visita.id) {
    await aplicarPatchCacheGenerico(TABELA, visita.id, { status: novoStatus });
  }
}
