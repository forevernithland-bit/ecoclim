// Chamadas à IA (backend /fit/* na VPS). Cada função tem um "plano B" local
// para o app nunca travar quando estiver sem internet.
import { API_BASE } from "./config.js";
import { token } from "./nuvem.js";
import { blobParaBase64, comprimirImagem } from "./midia.js";
import { estimarLocal } from "./alimentos.js";

async function chamar(rota, corpo, { timeout = 90000 } = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeout);
  try {
    const tk = await token();
    if (!tk) throw new Error("Entre com sua conta para usar a IA.");
    const resp = await fetch(`${API_BASE}/fit${rota}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(tk ? { Authorization: `Bearer ${tk}` } : {}) },
      body: JSON.stringify(corpo),
      signal: ctrl.signal,
    });
    if (!resp.ok) {
      let msg = `Erro ${resp.status}`;
      try { msg = (await resp.json()).detail || msg; } catch (e) { /* corpo não-JSON */ }
      throw new Error(msg);
    }
    return await resp.json();
  } finally {
    clearTimeout(t);
  }
}

// Fotos vão menores pra IA (1024 px): mais rápido e mais barato, sem perder
// o que importa pra identificar comida ou físico.
async function paraIA(blob) {
  if (!blob) return null;
  const menor = await comprimirImagem(blob, 1024, 0.8);
  return blobParaBase64(menor);
}

export async function analisarRefeicao({ texto, foto, perfil }) {
  try {
    const r = await chamar("/ia/refeicao", {
      texto: texto || "",
      imagem_b64: await paraIA(foto),
      contexto: perfil ? { objetivo: perfil.objetivo, sexo: perfil.sexo, peso: perfil.peso, nao_gosta: perfil.naoGosta || [], tipo_alimentacao: perfil.dietas || ["tudo"], alergias: perfil.alergias || "" } : null,
    });
    return { ...r, fonte: "ia" };
  } catch (e) {
    if (texto) {
      const local = estimarLocal(texto);
      if (local.itens.length) return { ...local, fonte: "local", aviso: "IA indisponível agora — usei a tabela de alimentos. Confira os valores." };
    }
    throw new Error(foto && !texto
      ? "Não consegui analisar a foto agora (sem conexão com a IA). Descreva o prato por texto ou voz que eu calculo pela tabela."
      : "Não reconheci os alimentos. Tente algo como: '2 ovos, 1 pão francês e café com leite'.");
  }
}

export async function analisarFisico({ perfil, frente, lado, fisicoAlvo, estimativaCiencia }) {
  return chamar("/ia/fisico", {
    perfil: resumoPerfil(perfil),
    fisico_alvo: fisicoAlvo,
    estimativa_ciencia: estimativaCiencia,
    foto_frente_b64: await paraIA(frente),
    foto_lado_b64: await paraIA(lado),
  }, { timeout: 150000 });
}

export async function compararEvolucao({ perfil, antes, depois }) {
  return chamar("/ia/comparar", {
    perfil: resumoPerfil(perfil),
    antes: { data: antes.data, peso: antes.peso, medidas: antes.medidas, gordura: antes.gordura },
    depois: { data: depois.data, peso: depois.peso, medidas: depois.medidas, gordura: depois.gordura },
    antes_frente_b64: await paraIA(antes.fotoFrente),
    depois_frente_b64: await paraIA(depois.fotoFrente),
    antes_lado_b64: await paraIA(antes.fotoLado),
    depois_lado_b64: await paraIA(depois.fotoLado),
  }, { timeout: 150000 });
}

export async function conversar({ agente, historico, contexto }) {
  return chamar("/ia/chat", { agente, mensagens: historico.slice(-20), contexto }, { timeout: 120000 });
}

export function resumoPerfil(p) {
  if (!p) return null;
  return {
    nome: p.nome, idade: p.idade, sexo: p.sexo, altura: p.altura, peso: p.peso,
    objetivo: p.objetivo, nivel: p.nivel, dias_treino: p.diasTreino, equipamento: p.equipamento,
    gordura_estimada: p.gordura, medidas: p.medidas, peso_meta: p.pesoMeta, restricoes: p.restricoes || "",
    nao_gosta: p.naoGosta || [], tipo_alimentacao: p.dietas || ["tudo"], alergias: p.alergias || "",
    gostos_ja_perguntados: !!p.gostosPerguntados,
  };
}
