// Lembretes pessoais do Breno — a mesma tabela `lembretes` que o Claude e o
// cron da VPS usam. Só o perfil Admin enxerga esta aba. Admin edita sempre
// online (sem a fila offline dos instaladores), então aqui é chamada direta
// ao Supabase, sem passar por db.js.
import { getSupabase } from "./supabase-client.js";

const TABELA = "lembretes";

/** Aberto por padrão; `incluirFeitos` traz também os concluídos (p/ aba "Feitos"). */
export async function puxarLembretes({ incluirFeitos = false } = {}) {
  const supabase = getSupabase();
  let q = supabase.from(TABELA).select("*");
  if (!incluirFeitos) q = q.eq("feito", false);
  q = q
    .order("feito", { ascending: true })
    .order("lembrar_em", { ascending: true, nullsFirst: false });
  const { data, error } = await q;
  if (error) throw error;
  return data || [];
}

export async function criarLembrete({ texto, lembrar_em = null, repetir = null, prioridade = 0 }) {
  const supabase = getSupabase();
  const linha = { texto: String(texto || "").trim(), origem: "app" };
  if (!linha.texto) throw new Error("Texto vazio.");
  if (lembrar_em) linha.lembrar_em = lembrar_em;
  if (repetir) linha.repetir = repetir;
  if (prioridade) linha.prioridade = prioridade;
  const { data, error } = await supabase.from(TABELA).insert(linha).select().single();
  if (error) throw error;
  return data;
}

/** Marca feito/não-feito. Recorrente concluído aqui já agenda a próxima
 *  ocorrência — mesma regra da skill do Claude e do cron. */
export async function marcarFeito(lem, feito) {
  const supabase = getSupabase();
  const agora = new Date().toISOString();
  const patch = feito
    ? { feito: true, feito_em: agora, atualizado_em: agora }
    : { feito: false, feito_em: null, avisado_em: null, atualizado_em: agora };
  const { error } = await supabase.from(TABELA).update(patch).eq("id", lem.id);
  if (error) throw error;

  if (feito && lem.repetir && lem.lembrar_em) {
    const prox = proximaOcorrencia(new Date(lem.lembrar_em), lem.repetir);
    if (prox) {
      await supabase.from(TABELA).insert({
        texto: lem.texto,
        lembrar_em: prox.toISOString(),
        repetir: lem.repetir,
        prioridade: lem.prioridade || 0,
        origem: "app",
      });
    }
  }
}

export async function adiarLembrete(id, lembrar_em) {
  const supabase = getSupabase();
  const { error } = await supabase.from(TABELA).update({
    lembrar_em,
    avisado_em: null,
    feito: false,
    atualizado_em: new Date().toISOString(),
  }).eq("id", id);
  if (error) throw error;
}

export async function excluirLembrete(id) {
  const supabase = getSupabase();
  const { error } = await supabase.from(TABELA).delete().eq("id", id);
  if (error) throw error;
}

/** Próxima data de um recorrente. `uteis` pula sábado e domingo. */
export function proximaOcorrencia(dt, repetir) {
  const d = new Date(dt);
  const r = String(repetir || "").toLowerCase();
  if (r.startsWith("diar")) { d.setDate(d.getDate() + 1); return d; }
  if (r.startsWith("seman")) { d.setDate(d.getDate() + 7); return d; }
  if (r === "uteis" || r === "úteis" || r === "util") {
    do { d.setDate(d.getDate() + 1); } while (d.getDay() === 0 || d.getDay() === 6);
    return d;
  }
  return null;
}
