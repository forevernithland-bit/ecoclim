import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { SUPABASE_URL, SUPABASE_ANON_KEY } from "./config.js";

// Sem sessão de Auth de verdade nesta fase (decidido: segurança fica pro
// final) — o app faz login conferindo usuário/senha direto na tabela
// usuarios_erp, igual o Streamlit já faz hoje. Este cliente só executa
// select/update simples, sempre filtrados pelo instalador logado.
//
// Criação sob demanda (não na importação do módulo): se o config.js ainda
// estiver com os valores de exemplo, o app continua abrindo normalmente
// (tela de login aparece) em vez de ficar em branco — o erro só acontece
// quando alguém realmente tentar entrar.
export const configuradoCorretamente =
  typeof SUPABASE_URL === "string" && SUPABASE_URL.startsWith("http") &&
  typeof SUPABASE_ANON_KEY === "string" && SUPABASE_ANON_KEY.length > 20;

let _client = null;
export function getSupabase() {
  if (!configuradoCorretamente) {
    throw new Error("Configuração do Supabase ausente — edite js/config.js.");
  }
  if (!_client) {
    _client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, { auth: { persistSession: false } });
  }
  return _client;
}
