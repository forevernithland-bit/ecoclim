import { getSupabase } from "./supabase-client.js";

// Espelho do movimentacoes.py do ERP: os dois escrevem na mesma tabela, então
// o histórico mostra o que o Breno fez no admin e o que o instalador fez no
// app, na mesma linha do tempo.
const TABELA = "movimentacoes";

const ROTULOS = {
  criou: "criou",
  status: "mudou o status",
  comentario: "comentou",
  midia: "anexou mídia",
  editou: "editou",
  concluiu: "concluiu",
  confirmou: "confirmou presença",
  remarcar: "pediu para remarcar",
};

/** Registra a movimentação. Nunca lança: histórico é registro, não pode
 *  impedir o instalador de trabalhar (ainda mais offline, sem sinal). */
export async function registrar(tipo, referenciaId, acao, { usuario, de, para, detalhe } = {}) {
  try {
    const supabase = getSupabase();
    await supabase.from(TABELA).insert({
      tipo, referencia_id: referenciaId, usuario: usuario || null,
      acao, de: de || null, para: para || null, detalhe: detalhe || null,
    });
  } catch (e) {
    /* sem sinal: segue o jogo */
  }
}

export async function listar(tipo, referenciaId, limite = 30) {
  try {
    const supabase = getSupabase();
    const { data, error } = await supabase
      .from(TABELA).select("*")
      .eq("tipo", tipo).eq("referencia_id", referenciaId)
      .order("criado_em", { ascending: false }).limit(limite);
    if (error) throw error;
    return data || [];
  } catch (e) {
    return [];
  }
}

export function frase(m) {
  const quem = m.usuario || "Alguém";
  const acao = ROTULOS[m.acao] || m.acao || "mexeu";
  if (m.acao === "status" && m.para) {
    return `${quem} ${acao} para ${m.para}${m.de ? ` (era ${m.de})` : ""}`;
  }
  return m.detalhe ? `${quem} ${acao}: ${m.detalhe}` : `${quem} ${acao}`;
}

export function quando(m) {
  const d = new Date(m.criado_em);
  if (isNaN(d)) return "";
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}
