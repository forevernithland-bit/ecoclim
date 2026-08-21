// Não é uma tabela nova — só agrupa por mês os serviços que já estão no
// cache local (mesma fonte da tela "Minhas Instalações").
export function agruparPorMes(servicos) {
  const grupos = {};
  for (const s of servicos) {
    const valor = Number(s.custo_terceirizados) || 0;
    if (valor <= 0) continue;
    const dataBase = s.data_conclusao || s.data_conclusao_instalador;
    if (!dataBase) continue;
    const chaveMes = String(dataBase).slice(0, 7); // "YYYY-MM"
    if (!grupos[chaveMes]) grupos[chaveMes] = { mes: chaveMes, aReceber: 0, recebido: 0, itens: [] };
    if (s.pago_instalador) grupos[chaveMes].recebido += valor;
    else grupos[chaveMes].aReceber += valor;
    grupos[chaveMes].itens.push(s);
  }
  return Object.values(grupos).sort((a, b) => b.mes.localeCompare(a.mes));
}

const NOMES_MES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];

export function formatarMes(chaveMes) {
  const [ano, mes] = chaveMes.split("-");
  const idx = parseInt(mes, 10) - 1;
  return `${NOMES_MES[idx] || mes} de ${ano}`;
}
