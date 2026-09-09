-- Divisão de mão de obra entre instaladores diferentes no mesmo serviço
-- (ex.: R$1200 pro Valdimar, R$450 pro Sérgio) — pedido do Breno (2026-09-09).
-- Lista de {instalador, valor, pago, data_pagamento}. Serviço sem essa
-- coluna preenchida continua funcionando exatamente como antes — o sistema
-- monta essa lista sozinho a partir de instalador/custo_terceirizados/
-- pago_instalador/data_pagamento_instalador (ver utils.pagamentos_instaladores_do_servico).
ALTER TABLE servicos_andamento
  ADD COLUMN IF NOT EXISTS pagamentos_instaladores jsonb DEFAULT '[]'::jsonb;
