-- Data exata do aporte, além do mês/conta que já existiam — pedido porque
-- pode haver mais de um aporte na mesma conta no mesmo mês (ex.: dois
-- recebimentos da Maggi), e só "AGOSTO" repetido nas duas linhas não deixa
-- claro qual foi qual. Opcional: linhas antigas continuam sem essa data.
alter table fin_aportes_itens add column if not exists data date;
