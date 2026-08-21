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

// Criada pelo próprio instalador — já entra como "vista" (ele não precisa
// de notificação sobre algo que ele mesmo cadastrou).
export async function criarVisita(visita) {
  await enfileirarCriacao(TABELA, { ...visita, visto_pelo_instalador: true, criado_por: "instalador" });
}

export async function atualizarStatusVisita(visita, novoStatus) {
  const dados = { ...visita, status: novoStatus };
  await enfileirarCriacao(TABELA, dados);
  if (visita.id) {
    await aplicarPatchCacheGenerico(TABELA, visita.id, { status: novoStatus });
  }
}

// Quantas tarefas o Breno cadastrou pra esse instalador que ele ainda não
// viu — alimenta o selinho de notificação na barra inferior. Se estiver
// offline, conta pelo cache local (pode ficar um pouco desatualizado, mas
// nunca quebra).
export async function contarNaoVistas(instaladorVinculado) {
  try {
    const supabase = getSupabase();
    const { count, error } = await supabase
      .from(TABELA)
      .select("id", { count: "exact", head: true })
      .eq("instalador", instaladorVinculado)
      .eq("visto_pelo_instalador", false);
    if (error) throw error;
    return count || 0;
  } catch (e) {
    const cache = await lerCacheTabela(TABELA);
    return cache.filter((v) => v.instalador === instaladorVinculado && v.visto_pelo_instalador === false).length;
  }
}

// Marca como vistas todas as tarefas pendentes de notificação desse
// instalador — chamado quando ele abre a aba Agenda. Se falhar (sem sinal),
// não tem problema: tenta de novo na próxima vez que abrir online.
export async function marcarTodasComoVistas(instaladorVinculado) {
  try {
    const supabase = getSupabase();
    await supabase.from(TABELA).update({ visto_pelo_instalador: true })
      .eq("instalador", instaladorVinculado).eq("visto_pelo_instalador", false);
  } catch (e) {
    // sem sinal — ok, tenta de novo depois
  }
}
