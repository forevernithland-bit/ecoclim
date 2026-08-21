import { getSupabase } from "./supabase-client.js";
import { salvarCacheTabela, lerCacheTabela } from "./db.js";

const TABELA = "adiantamentos_instalador";
const TABELA_BAIXAS = "adiantamento_baixas";

// Só leitura do lado do instalador — quem registra/edita adiantamento e dá
// baixa (total ou parcial) é sempre o Breno, pelo painel admin. Aqui só
// mostra o saldo já calculado (valor menos o que já foi baixado) e o
// histórico de baixas de cada um, pra acompanhamento.
export async function puxarAdiantamentos(instaladorVinculado) {
  let adiantamentos;
  try {
    const supabase = getSupabase();
    const { data, error } = await supabase
      .from(TABELA)
      .select("*")
      .eq("instalador", instaladorVinculado)
      .order("data", { ascending: false });
    if (error) throw error;
    adiantamentos = data || [];
    await salvarCacheTabela(TABELA, adiantamentos);
  } catch (e) {
    adiantamentos = await lerCacheTabela(TABELA);
  }
  if (!adiantamentos.length) return adiantamentos;

  let baixas;
  try {
    const supabase = getSupabase();
    const ids = adiantamentos.map((a) => a.id);
    const { data, error } = await supabase
      .from(TABELA_BAIXAS)
      .select("*")
      .in("adiantamento_id", ids)
      .order("data", { ascending: true });
    if (error) throw error;
    baixas = data || [];
    await salvarCacheTabela(TABELA_BAIXAS, baixas);
  } catch (e) {
    const idsSet = new Set(adiantamentos.map((a) => a.id));
    baixas = (await lerCacheTabela(TABELA_BAIXAS)).filter((b) => idsSet.has(b.adiantamento_id));
  }

  for (const a of adiantamentos) {
    a._baixas = baixas.filter((b) => b.adiantamento_id === a.id);
    a._baixado = a._baixas.reduce((acc, b) => acc + (Number(b.valor) || 0), 0);
    a._saldo = Math.max((Number(a.valor) || 0) - a._baixado, 0);
  }
  return adiantamentos;
}

export function totalAdiantadoAberto(adiantamentos) {
  return adiantamentos.reduce((acc, a) => acc + (Number(a._saldo) || 0), 0);
}
