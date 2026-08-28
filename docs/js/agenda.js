import { getSupabase } from "./supabase-client.js";
import { salvarCacheTabela, lerCacheTabela, enfileirarCriacao, aplicarPatchCacheGenerico, lerCriacoesOutbox } from "./db.js";

const TABELA = "agenda_visitas";

// instaladorVinculado vazio (admin) = sem filtro, traz de todos os instaladores.
export async function puxarVisitas(instaladorVinculado) {
  try {
    const supabase = getSupabase();
    let query = supabase.from(TABELA).select("*").order("data_hora", { ascending: true });
    if (instaladorVinculado) query = query.eq("instalador", instaladorVinculado);
    const { data, error } = await query;
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

// Edição/exclusão direta (admin) — online, sem passar pela fila offline
// (diferente do fluxo do instalador em campo, o admin edita/apaga já
// conectado, então não precisa da complexidade da outbox aqui).
export async function atualizarVisitaAdmin(id, patch) {
  const supabase = getSupabase();
  const { error } = await supabase.from(TABELA).update(patch).eq("id", id);
  if (error) throw error;
}

export async function excluirVisita(id) {
  const supabase = getSupabase();
  const { error } = await supabase.from(TABELA).delete().eq("id", id);
  if (error) throw error;
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

// Instalador respondendo uma tarefa: comentário + valor sugerido pro
// orçamento/manutenção. Isso liga o "visto_pelo_admin=false", que acende a
// notificação do lado do Breno no painel — o mesmo mecanismo, na direção
// contrária.
export async function salvarRespostaInstalador(visita, comentario, valorSugerido) {
  const dados = {
    ...visita,
    comentario_instalador: comentario,
    visto_pelo_admin: false,
  };
  if (valorSugerido !== null && valorSugerido !== undefined && valorSugerido !== "") {
    dados.valor_sugerido = valorSugerido;
  }
  await enfileirarCriacao(TABELA, dados);
  if (visita.id) {
    await aplicarPatchCacheGenerico(TABELA, visita.id, {
      comentario_instalador: comentario,
      valor_sugerido: dados.valor_sugerido ?? visita.valor_sugerido,
    });
  }
}

/** Confirmação da véspera: "OK" (vou) ou "Remarcar" (não vou dar conta).
 *  Direto online, sem passar pela fila offline — é uma resposta que o Breno
 *  precisa ver agora, não quando o sinal voltar. */
export async function atualizarConfirmacaoVisita(id, resposta, motivo) {
  const supabase = getSupabase();
  const { error } = await supabase.from(TABELA).update({
    confirmacao: resposta,
    confirmacao_em: new Date().toISOString(),
    confirmacao_motivo: motivo || null,
  }).eq("id", id);
  if (error) throw error;
}
