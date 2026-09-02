-- Referência ao produto do fornecedor (Tambasa) por trás de cada item do
-- catálogo — código e descrição exatos de como aparece no orçamento/compra
-- deles. É a chave estável pra próxima importação reconhecer o item sem
-- precisar adivinhar de novo por nome (o nosso `item` nunca muda; o do
-- fornecedor é que serve de referência cruzada).
alter table materiais_padrao add column if not exists codigo_fornecedor text;
alter table materiais_padrao add column if not exists descricao_fornecedor text;
alter table materiais_padrao add column if not exists data_ultima_compra date;
