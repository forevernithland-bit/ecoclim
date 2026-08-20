import { getSupabase } from "./supabase-client.js";
import { salvarSessao, lerSessao, limparSessao, limparServicos } from "./db.js";

// Login simples (mesma lógica do Streamlit hoje: usuário/senha direto na
// tabela usuarios_erp). Precisa de internet na PRIMEIRA vez; depois disso a
// sessão fica salva localmente e o app abre offline sem pedir senha de novo
// (só quando o instalador tocar em "Sair").
export async function login(usuario, senha) {
  const usuarioTratado = String(usuario || "").trim().toLowerCase();
  if (!usuarioTratado || !senha) {
    return { ok: false, erro: "Preencha usuário e senha." };
  }

  let res;
  try {
    const supabase = getSupabase();
    res = await supabase
      .from("usuarios_erp")
      .select("*")
      .eq("usuario", usuarioTratado)
      .maybeSingle();
  } catch (e) {
    if (String(e.message || "").includes("Configuração do Supabase")) {
      return { ok: false, erro: "App ainda não configurado (js/config.js). Fale com o Breno." };
    }
    return { ok: false, erro: "Sem conexão. Conecte-se à internet para o primeiro acesso." };
  }

  if (res.error) {
    // supabase-js não lança exceção quando a rede falha (fetch indisponível,
    // sem sinal) — ele resolve normalmente com um erro dentro de `res` e
    // status 0 (nenhuma resposta HTTP chegou). Sem essa checagem, o app
    // mostrava "Usuário ou senha incorretos" mesmo estando só sem internet,
    // contradizendo a própria dica da tela ("precisa de internet só na
    // primeira vez").
    if (res.status === 0) {
      return { ok: false, erro: "Sem conexão. Conecte-se à internet para o primeiro acesso." };
    }
    return { ok: false, erro: "Usuário ou senha incorretos." };
  }
  if (!res.data) {
    return { ok: false, erro: "Usuário ou senha incorretos." };
  }
  const dados = res.data;
  if (dados.senha !== senha || dados.ativo === false) {
    return { ok: false, erro: "Usuário ou senha incorretos." };
  }
  if (dados.perfil !== "Instalador") {
    return { ok: false, erro: "Este acesso é exclusivo para instaladores." };
  }
  const instaladorVinculado = String(dados.instalador_vinculado || "").trim();
  if (!instaladorVinculado) {
    return { ok: false, erro: "Este usuário ainda não está vinculado a um instalador. Fale com o Breno." };
  }

  const sessao = {
    usuario: usuarioTratado,
    nomeCompleto: dados.nome_completo || usuarioTratado,
    instaladorVinculado,
  };
  await salvarSessao(sessao);
  return { ok: true, sessao };
}

export async function sessaoAtual() {
  return await lerSessao();
}

// Aparelho pode ser compartilhado entre instaladores — além de encerrar a
// sessão, apaga o cache local de serviços (nome/telefone/endereço/valor do
// instalador anterior) pra não vazar pro próximo que logar neste mesmo
// aparelho. A outbox (edições ainda não sincronizadas) é preservada de
// propósito: nada digitado offline é perdido, e ela é enviada normalmente
// assim que qualquer sessão (mesma ou outro instalador) sincronizar de novo.
export async function logout() {
  await limparSessao();
  await limparServicos();
}
