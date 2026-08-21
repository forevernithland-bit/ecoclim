import { getSupabase } from "./supabase-client.js";
import { salvarCacheTabela, lerCacheTabela } from "./db.js";

const TABELA = "adiantamentos_instalador";

// Só leitura do lado do instalador — quem registra/edita adiantamento é
// sempre o Breno, pelo painel admin.
export async function puxarAdiantamentos(instaladorVinculado) {
  try {
    const supabase = getSupabase();
    const { data, error } = await supabase
      .from(TABELA)
      .select("*")
      .eq("instalador", instaladorVinculado)
      .order("data", { ascending: false });
    if (error) throw error;
    await salvarCacheTabela(TABELA, data || []);
    return data || [];
  } catch (e) {
    return await lerCacheTabela(TABELA);
  }
}

export function totalAdiantadoAberto(adiantamentos) {
  return adiantamentos
    .filter((a) => !a.pago)
    .reduce((acc, a) => acc + (Number(a.valor) || 0), 0);
}
