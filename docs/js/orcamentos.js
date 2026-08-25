import { getSupabase } from "./supabase-client.js";

// Backend que gera o PDF idêntico ao ERP e faz a mesma detecção automática
// de capa/serviço — nunca duplicamos essa lógica aqui em JS, pra qualquer
// mudança no orcamento_personalizado.py (ERP desktop) valer automaticamente
// pro celular também. Ver HANDOFF/memória do projeto.
const API_BASE = "https://api.ecoclim.com.br";

async function chamarApi(caminho, corpo) {
  const resp = await fetch(`${API_BASE}${caminho}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
  if (!resp.ok) {
    const detalhe = await resp.text().catch(() => "");
    throw new Error(`Erro ${resp.status} no servidor: ${detalhe.slice(0, 200)}`);
  }
  return resp.json();
}

export async function buscarSugestao(itens) {
  return chamarApi("/orcamento-personalizado/sugestao", { itens });
}

export async function gerarPdfOrcamento(payload) {
  return chamarApi("/orcamento-personalizado/gerar-pdf", payload);
}

export async function calcularCustos(payload) {
  return chamarApi("/orcamento-personalizado/calculo-custos", payload);
}

// ---------- Catálogos (direto do Supabase — mesma base do ERP) ----------
async function carregarCatalogo(tabela) {
  const supabase = getSupabase();
  const { data, error } = await supabase.from(tabela).select("*").order("item");
  if (error) throw error;
  return (data || []).map((r) => ({
    item: r.item || "",
    descricao: r.descricao || "",
    custo: Number(r.custo) || 0,
    venda: Number(r.venda) || 0,
  }));
}

export const puxarCatalogoProdutos = () => carregarCatalogo("catalogo_produtos");
export const puxarCatalogoServicos = () => carregarCatalogo("catalogo_servicos");
export const puxarCatalogoOutros = () => carregarCatalogo("catalogo_outros");

// ---------- Rascunhos / orçamentos salvos (tabela servicos_andamento) ----------
export async function puxarRascunhos() {
  const supabase = getSupabase();
  const { data, error } = await supabase
    .from("servicos_andamento")
    .select("id, nome_cliente, valor_venda_total")
    .eq("status_projeto", "Rascunho")
    .order("id", { ascending: false });
  if (error) throw error;
  return data || [];
}

export async function carregarRascunho(id) {
  const supabase = getSupabase();
  const { data, error } = await supabase.from("servicos_andamento").select("*").eq("id", id).maybeSingle();
  if (error) throw error;
  return data;
}

export async function excluirRascunho(id) {
  const supabase = getSupabase();
  const { error } = await supabase.from("servicos_andamento").delete().eq("id", id);
  if (error) throw error;
}

// status: "Rascunho" ou "Orçamento Enviado". rascunhoId: passa pra
// atualizar um existente, ou null pra criar um novo registro.
export async function salvarOrcamento({ status, rascunhoId, numeroOrcamento, dados }) {
  const supabase = getSupabase();
  const payload = {
    nome_cliente: dados.nomeCliente,
    telefone_cliente: dados.telefone,
    endereco_cliente: dados.endereco,
    produtos_adquiridos: dados.itens.map((it) => `${it.quantidade}x ${it.nome}`).join(", "),
    servicos_adquiridos: dados.descricaoServico,
    valor_venda_total: dados.totalInvestimento,
    status_projeto: status,
    detalhamento_itens: dados.itens.map((it) => ({
      Item: it.nome, Qtd: it.quantidade, "Venda Un.": it.venda_unitario,
      "Custo Un.": it.custo_unitario, "Descrição": it.descricao || "",
    })),
    data_conclusao: new Date().toISOString().slice(0, 10),
    dados_contrato: status === "Rascunho" ? {
      val_servico: dados.valorServico, txt_outros: dados.descricaoOutros,
      val_outros: dados.valorOutros, obs_pdf: dados.observacoes,
    } : {},
  };
  if (rascunhoId) {
    if (status !== "Rascunho") payload.numero_orcamento = numeroOrcamento;
    const { error } = await supabase.from("servicos_andamento").update(payload).eq("id", rascunhoId);
    if (error) throw error;
    return rascunhoId;
  }
  payload.numero_orcamento = numeroOrcamento;
  const { data, error } = await supabase.from("servicos_andamento").insert(payload).select("id").single();
  if (error) throw error;
  return data.id;
}
