import { getSupabase } from "./supabase-client.js";
import {
  salvarServicos, lerOutbox, removerDaOutbox, lerServicos,
  lerCriacoesOutbox, removerDaCriacoesOutbox,
} from "./db.js";

// Colunas já garantidas no banco há tempo — se o select com as colunas novas
// (abaixo) falhar porque alguma ainda não existe (SQL pendente de rodar),
// caímos pra essa base em vez de deixar o app inteiro parecer offline.
const COLUNAS_BASE = [
  "id", "numero_orcamento", "nome_cliente", "telefone_cliente", "endereco_cliente",
  "status_projeto", "produtos_adquiridos", "servicos_adquiridos", "data_conclusao",
  "instalador", "custo_terceirizados",
  "observacao_instalador", "instalacao_concluida_instalador", "data_conclusao_instalador",
  "pago_instalador", "data_pagamento_instalador", "data_inicio_garantia",
].join(",");

// Colunas recém-criadas nesta sessão — dependem do SQL pendente. Ficam numa
// lista separada de propósito: uma coluna nova faltando não pode derrubar a
// sincronização das colunas antigas, que já funcionam em produção.
const COLUNAS_NOVAS = ["data_prevista_instalacao"];

const COLUNAS_SEGURAS = [COLUNAS_BASE, ...COLUNAS_NOVAS].join(",");

let ouvintes = [];
export function aoMudarStatusSync(fn) {
  ouvintes.push(fn);
}
function avisar(status) {
  for (const fn of ouvintes) fn(status);
}

// Baixa os serviços do instalador logado e atualiza o cache local.
// Nunca busca valor_venda_total / lucro_estimado / detalhamento_itens /
// dados_contrato — essas colunas simplesmente não entram na consulta.
export async function puxarServicos(instaladorVinculado) {
  const supabase = getSupabase();
  try {
    const { data, error } = await supabase
      .from("servicos_andamento")
      .select(COLUNAS_SEGURAS)
      .eq("instalador", instaladorVinculado)
      .order("id", { ascending: false });
    if (error) throw error;
    await salvarServicos(data || []);
    return { ok: true, online: true };
  } catch (e) {
    // Uma coluna nova (SQL ainda não rodado) não pode travar as colunas
    // antigas, que já funcionam em produção — tenta de novo só com a base.
    try {
      const { data, error } = await supabase
        .from("servicos_andamento")
        .select(COLUNAS_BASE)
        .eq("instalador", instaladorVinculado)
        .order("id", { ascending: false });
      if (error) throw error;
      await salvarServicos(data || []);
      return { ok: true, online: true };
    } catch (e2) {
      return { ok: false, online: false };
    }
  }
}

// Envia a fila de escrita pendente (comentário / conclusão feitos offline).
// Para no primeiro erro de rede — assume que ainda está offline e tenta de
// novo depois, sem descartar o que já está na fila.
export async function enviarPendencias() {
  const pendentes = await lerOutbox();
  let enviados = 0;
  let supabase;
  try {
    supabase = getSupabase();
  } catch (e) {
    return { enviados: 0, restantes: pendentes.length };
  }
  for (const item of pendentes) {
    try {
      const { error } = await supabase
        .from("servicos_andamento")
        .update(item.patch)
        .eq("id", item.servico_id);
      if (error) throw error;
      await removerDaOutbox(item.localId);
      enviados++;
    } catch (e) {
      break; // provavelmente offline — mantém o resto na fila pra próxima tentativa
    }
  }
  return { enviados, restantes: (await lerOutbox()).length };
}

// Envia as criações/edições pendentes de Agenda e Materiais (fila genérica,
// sempre um upsert). Mesma lógica de "para no primeiro erro" da outbox.
export async function enviarCriacoesPendentes() {
  const pendentes = await lerCriacoesOutbox();
  let supabase;
  try {
    supabase = getSupabase();
  } catch (e) {
    return { enviados: 0 };
  }
  let enviados = 0;
  for (const item of pendentes) {
    try {
      const { error } = await supabase.from(item.tabela).upsert(item.dados);
      if (error) throw error;
      await removerDaCriacoesOutbox(item.localId);
      enviados++;
    } catch (e) {
      break;
    }
  }
  return { enviados };
}

export async function sincronizarTudo(instaladorVinculado) {
  avisar("sincronizando");
  const push = await enviarPendencias();
  await enviarCriacoesPendentes();
  const pull = await puxarServicos(instaladorVinculado);
  const pendentes = (await lerOutbox()).length + (await lerCriacoesOutbox()).length;
  const status = pull.ok ? (pendentes > 0 ? "pendente" : "sincronizado") : "offline";
  avisar(status);
  return { status, pendentes };
}

export function iniciarSyncAutomatico(instaladorVinculado) {
  const tentar = () => sincronizarTudo(instaladorVinculado);
  window.addEventListener("online", tentar);
  setInterval(tentar, 30000); // rede pode voltar sem disparar o evento 'online' em alguns aparelhos
  tentar();
}

export async function statusAtual() {
  const pendentes = (await lerOutbox()).length + (await lerCriacoesOutbox()).length;
  return { online: navigator.onLine, pendentes };
}
