-- Lista de recebimentos de um serviço/cliente — forma de pagamento, valor,
-- data e observação de cada um (pode haver vários: entrada + parcela final,
-- parte PIX + parte cartão, etc). Substitui o antigo campo único "taxa de
-- cartão pra venda inteira", que cobrava taxa sobre dinheiro que às vezes
-- nem passava no cartão, e não deixava registro de quanto já tinha entrado
-- como entrada.
alter table servicos_andamento add column if not exists pagamentos_recebidos jsonb;
