import { getSupabase } from "./supabase-client.js";
import { API_BASE } from "./config.js";

// Backend que gera o PDF idêntico ao ERP e faz a mesma detecção automática
// de capa/serviço — nunca duplicamos essa lógica aqui em JS, pra qualquer
// mudança no orcamento_personalizado.py (ERP desktop) valer automaticamente
// pro celular também. Ver HANDOFF/memória do projeto.

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

// ---------- Financeiro do admin (visão da empresa toda, todos os instaladores) ----------
// Mesma regra do ERP (tela_servicos.py::deve_ir_para_finalizados): finalizado
// = status Concluído PIX/CARTÃO; "Em Andamento" é o resto dos status ativos.
// Nada de Rascunho/Rascunho Rápido/Orçamento aqui — só serviço de verdade.
const STATUS_EM_ANDAMENTO = ["Em Andamento", "Aguardando Pagamento", "Aguardando Peças"];
const STATUS_FINALIZADOS = ["Concluído PIX", "Concluído CARTÃO"];

// Instalações de TODOS os instaladores — usado pela tela "Instalações" do
// admin (que normalmente lê do cache offline de UM instalador só, e o admin
// não é vinculado a nenhum). Mesmos campos que a tela já sabe renderizar.
export async function puxarTodosOsServicos() {
  const supabase = getSupabase();
  const { data, error } = await supabase
    .from("servicos_andamento")
    .select("id, nome_cliente, bairro_cliente, telefone_cliente, endereco_cliente, produtos_adquiridos, servicos_adquiridos, status_projeto, instalacao_concluida_instalador, data_conclusao_instalador, data_conclusao, data_prevista_instalacao, instalador")
    .in("status_projeto", [...STATUS_EM_ANDAMENTO, ...STATUS_FINALIZADOS])
    .order("id", { ascending: false });
  if (error) throw error;
  return data || [];
}

// Edição/exclusão direta (admin) de um serviço/instalação.
export async function atualizarServico(id, patch) {
  const supabase = getSupabase();
  const { error } = await supabase.from("servicos_andamento").update(patch).eq("id", id);
  if (error) throw error;
}

export async function excluirServico(id) {
  const supabase = getSupabase();
  const { error } = await supabase.from("servicos_andamento").delete().eq("id", id);
  if (error) throw error;
}

export async function puxarServicosEmpresa() {
  const supabase = getSupabase();
  const { data, error } = await supabase
    .from("servicos_andamento")
    .select("id, nome_cliente, status_projeto, valor_venda_total, lucro_estimado, instalador, data_conclusao")
    .in("status_projeto", [...STATUS_EM_ANDAMENTO, ...STATUS_FINALIZADOS])
    .order("id", { ascending: false });
  if (error) throw error;
  const linhas = data || [];
  return {
    emAndamento: linhas.filter((s) => STATUS_EM_ANDAMENTO.includes(s.status_projeto)),
    finalizados: linhas.filter((s) => STATUS_FINALIZADOS.includes(s.status_projeto)),
  };
}

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
