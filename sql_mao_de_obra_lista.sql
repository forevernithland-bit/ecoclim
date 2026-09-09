-- Mão de obra de instalação opcional por lista de materiais avulsa —
-- pedido do Breno (2026-09-05). Some junto do total de venda mostrado na
-- tela e no PDF pro cliente, sem mexer nos itens de material em si.
ALTER TABLE listas_materiais
  ADD COLUMN IF NOT EXISTS mao_de_obra numeric DEFAULT 0;
