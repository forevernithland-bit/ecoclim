// Não são tabelas novas — só reorganiza os serviços que já estão no cache
// local (mesma fonte da tela "Minhas Instalações") em: recebido no mês (pela
// data em que o Breno marcou como pago) x a receber no mês (pela data de
// conclusão, se já pronto, ou pela data prevista de instalação, se ainda em
// andamento). Cada serviço cai em EXATAMENTE um balde por mês — nunca conta
// duas vezes.
const STATUS_FINALIZADOS_ADMIN = ["Concluído PIX", "Concluído CARTÃO"];

function estaConcluidoParaFinanceiro(s) {
  return Boolean(s.instalacao_concluida_instalador) || STATUS_FINALIZADOS_ADMIN.includes(s.status_projeto);
}

export function agruparPorMes(servicos) {
  const grupos = {};
  const garantirGrupo = (chave) => {
    if (!grupos[chave]) grupos[chave] = { mes: chave, aReceber: 0, recebido: 0, itensReceber: [], itensRecebido: [] };
    return grupos[chave];
  };

  for (const s of servicos) {
    const valor = Number(s.custo_terceirizados) || 0;
    if (valor <= 0) continue;

    if (s.pago_instalador) {
      const dataPagamento = s.data_pagamento_instalador;
      if (!dataPagamento) continue;
      const g = garantirGrupo(String(dataPagamento).slice(0, 7));
      g.recebido += valor;
      g.itensRecebido.push(s);
    } else {
      const dataRef = estaConcluidoParaFinanceiro(s)
        ? (s.data_conclusao_instalador || s.data_conclusao)
        : s.data_prevista_instalacao;
      if (!dataRef) continue; // sem previsão ainda — não dá pra encaixar num mês
      const g = garantirGrupo(String(dataRef).slice(0, 7));
      g.aReceber += valor;
      g.itensReceber.push(s);
    }
  }
  return Object.values(grupos).sort((a, b) => b.mes.localeCompare(a.mes));
}

// Os dois "quadrantes" da tela de Financeiro — cada um é uma lista
// filtrada e clicável (soma + clientes), separada por status do serviço:

// Quadrante 1: já instalado (concluído), ainda não pago ao instalador —
// entra aqui não importa se tem data de conclusão registrada ou não.
export function servicosFinalizadosAReceber(servicos) {
  return servicos.filter((s) => {
    const valor = Number(s.custo_terceirizados) || 0;
    return valor > 0 && !s.pago_instalador && estaConcluidoParaFinanceiro(s);
  });
}

// Quadrante 2: ainda em andamento (não concluído), sem nenhuma Data
// Prevista de Instalação preenchida ainda — por isso não aparece em
// nenhum mês específico lá embaixo. É o lembrete pro instalador preencher
// a data em cada um desses clientes.
export function servicosEmAndamentoSemData(servicos) {
  return servicos.filter((s) => {
    const valor = Number(s.custo_terceirizados) || 0;
    return valor > 0 && !s.pago_instalador && !estaConcluidoParaFinanceiro(s) && !s.data_prevista_instalacao;
  });
}

// Total geral a receber (soma de tudo que ainda não foi pago: os dois
// quadrantes acima + em andamento já com data prevista, que aparece
// agrupado por mês lá embaixo) — usado só no resumo do topo da tela, pra
// bater com a soma de tudo.
export function totalGeralAReceber(servicos) {
  return servicos
    .filter((s) => !s.pago_instalador && (Number(s.custo_terceirizados) || 0) > 0)
    .reduce((acc, s) => acc + Number(s.custo_terceirizados), 0);
}

const NOMES_MES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];

export function formatarMes(chaveMes) {
  const [ano, mes] = chaveMes.split("-");
  const idx = parseInt(mes, 10) - 1;
  return `${NOMES_MES[idx] || mes} de ${ano}`;
}
