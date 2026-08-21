import { getSupabase } from "./supabase-client.js";
import { salvarCacheTabela, lerCacheTabela, enfileirarCriacao, lerCriacoesOutbox } from "./db.js";

const T_LISTAS = "listas_materiais";
const T_PADRAO = "materiais_padrao";

export async function puxarMinhasListas(instaladorVinculado) {
  try {
    const supabase = getSupabase();
    const { data, error } = await supabase
      .from(T_LISTAS)
      .select("*")
      .eq("instalador", instaladorVinculado)
      .order("atualizado_em", { ascending: false });
    if (error) throw error;
    await salvarCacheTabela(T_LISTAS, data || []);
    return data || [];
  } catch (e) {
    return await lerCacheTabela(T_LISTAS);
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

export async function salvarLista(lista) {
  const agora = new Date().toISOString();
  await enfileirarCriacao(T_LISTAS, { ...lista, atualizado_em: agora });
}

// Listas criadas offline, ainda sem confirmação do servidor — pra não
// "sumir" da tela até a sincronização acontecer de verdade.
export async function listasPendentesNovas() {
  const pendentes = await lerCriacoesOutbox(T_LISTAS);
  return pendentes.filter((p) => !p.dados.id);
}

// Grava um item novo no padrão compartilhado desta categoria — visível pra
// todos os instaladores a partir da próxima sincronização deles.
export async function adicionarItemAoPadrao(categoria, item, unidade) {
  await enfileirarCriacao(T_PADRAO, { categoria, item, unidade: unidade || "un", ordem: 999 });
}
