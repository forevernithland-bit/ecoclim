import { getSupabase } from "./supabase-client.js";
import { salvarCacheTabela, lerCacheTabela, enfileirarCriacao, lerCriacoesOutbox } from "./db.js";

const T_LISTAS = "listas_materiais";
const T_PADRAO = "materiais_padrao";
const T_MODELOS = "materiais_modelos";

// instaladorVinculado vazio (admin) = sem filtro, traz de todos os instaladores.
export async function puxarMinhasListas(instaladorVinculado) {
  try {
    const supabase = getSupabase();
    let query = supabase.from(T_LISTAS).select("*").order("atualizado_em", { ascending: false });
    if (instaladorVinculado) query = query.eq("instalador", instaladorVinculado);
    const { data, error } = await query;
    if (error) throw error;
    await salvarCacheTabela(T_LISTAS, data || []);
    return data || [];
  } catch (e) {
    return await lerCacheTabela(T_LISTAS);
  }
}

// Listas de materiais de UM cliente específico (tela de detalhe da
// instalação) — diferente de puxarMinhasListas, que traz TODAS as listas do
// instalador (avulsas ou não) pra tela geral de Materiais.
export async function puxarListaDoServico(servicoId) {
  const contexto = `${T_LISTAS}_servico_${servicoId}`;
  try {
    const supabase = getSupabase();
    const { data, error } = await supabase
      .from(T_LISTAS)
      .select("*")
      .eq("servico_id", servicoId)
      .order("atualizado_em", { ascending: false });
    if (error) throw error;
    await salvarCacheTabela(contexto, data || []);
    return data || [];
  } catch (e) {
    return await lerCacheTabela(contexto);
  }
}

export async function puxarMateriaisPadrao() {
  try {
    const supabase = getSupabase();
    const { data, error } = await supabase.from(T_PADRAO).select("*").order("categoria").order("ordem");
    if (error) throw error;
    await salvarCacheTabela(T_PADRAO, data || []);
    return data || [];
  } catch (e) {
    return await lerCacheTabela(T_PADRAO);
  }
}

// Listas "modelo" cadastradas pelo admin (ex: Acoplado, Tradicional) — o
// instalador escolhe uma pra já começar a lista do cliente preenchida, em
// vez de buscar item por item do zero.
export async function puxarModelosMateriais() {
  try {
    const supabase = getSupabase();
    const { data, error } = await supabase.from(T_MODELOS).select("*").order("nome");
    if (error) throw error;
    await salvarCacheTabela(T_MODELOS, data || []);
    return data || [];
  } catch (e) {
    return await lerCacheTabela(T_MODELOS);
  }
}

export async function salvarLista(lista) {
  const agora = new Date().toISOString();
  await enfileirarCriacao(T_LISTAS, { ...lista, atualizado_em: agora });
}

// Edição de uma lista já salva — direto online (não passa pela fila
// offline como a criação; editar é uma ação rara o bastante pra pedir
// conexão, e evita a complexidade de reconciliar edição+outbox).
export async function atualizarLista(id, patch) {
  const supabase = getSupabase();
  const agora = new Date().toISOString();
  const { error } = await supabase.from(T_LISTAS).update({ ...patch, atualizado_em: agora }).eq("id", id);
  if (error) throw error;
}

// Exclusão permanente — usada pelo admin pra limpar lista errada/duplicada.
export async function excluirLista(id) {
  const supabase = getSupabase();
  const { error } = await supabase.from(T_LISTAS).delete().eq("id", id);
  if (error) throw error;
}

// Listas criadas offline, ainda sem confirmação do servidor — pra não
// "sumir" da tela até a sincronização acontecer de verdade.
export async function listasPendentesNovas() {
  const pendentes = await lerCriacoesOutbox(T_LISTAS);
  return pendentes.filter((p) => !p.dados.id);
}

// Quando o instalador não acha o item no catálogo e digita à mão, isso fica
// registrado pro Breno ver e decidir se entra no catálogo padrão (fica
// disponível pra busca de todo mundo a partir daí). Não impede o instalador
// de continuar — a lista dele é salva do mesmo jeito, isso é só o aviso.
const T_SUGESTOES = "materiais_sugeridos";
export async function sugerirNovoMaterial({ item, instalador, clienteNome, servicoId }) {
  try {
    const supabase = getSupabase();
    await supabase.from(T_SUGESTOES).insert({
      item, instalador, cliente_nome: clienteNome || null, servico_id: servicoId || null,
      visto_pelo_admin: false,
    });
  } catch (e) {
    // Sem sinal agora — não é crítico, o Breno só vai descobrir esse item
    // um pouco mais tarde. Não trava o salvamento da lista por causa disso.
  }
}
