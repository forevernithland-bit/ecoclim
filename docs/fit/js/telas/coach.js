// Conversa com os especialistas (IA): Nutri e Personal. Cada um recebe o
// contexto do usuário (perfil, metas, o que comeu hoje, últimos treinos,
// última evolução) para responder de forma personalizada.
import { esc, toast } from "../ui.js";
import { conversar, resumoPerfil } from "../ia.js";
import { E, gravar, listar, metasAtuais, salvarPerfil } from "../estado.js";
import { juntar, remover } from "../gostos.js";
import { totaisDoDia } from "./comida.js";
import { hojeISO } from "../db.js";

export const AGENTES = {
  nutri: {
    nome: "Nina", papel: "Nutricionista", emoji: "🥗",
    ola: "Oi! Sou a Nina, sua nutricionista. Posso montar cardápios, sugerir trocas, explicar rótulos ou dizer o que comer agora pra bater sua meta. Em que posso ajudar?",
    sugestoes: ["Monte um cardápio de 1 dia pra mim", "O que eu janto hoje pra bater a proteína?", "Não gosto de alguns alimentos", "Posso comer doce e ainda emagrecer?", "Lanches práticos pra levar pro trabalho"],
  },
  coach: {
    nome: "Léo", papel: "Personal trainer", emoji: "🏋️",
    ola: "E aí! Sou o Léo, seu personal. Posso ajustar seu treino, explicar um exercício, substituir algo por dor ou falta de aparelho, ou te ajudar a quebrar um platô. Manda!",
    sugestoes: ["Não tenho aparelho X hoje, o que faço?", "Como sei se estou progredindo?", "Sinto dor no joelho no agachamento", "Parei de perder peso, e agora?"],
  },
};

let agenteAtual = "nutri";

async function contexto() {
  const t = await totaisDoDia();
  const treinos = (await listar("treinos")).slice(-3).map((l) => ({ data: l.data, nome: l.nome, series: l.series, volume: l.volume }));
  const metricas = (await listar("metricas")).slice(-7).map((m) => ({ data: m.data, peso: m.peso, passos: m.passos, sono: m.sono, energia: m.energia }));
  const comps = (await listar("comparativos")).slice(-1).map((c) => ({ de: c.antesData, ate: c.depoisData, difs: c.difs, ia: c.ia ? c.ia.resumo : null }));
  return {
    hoje: hojeISO(),
    perfil: resumoPerfil(E.perfil),
    metas: metasAtuais(),
    comido_hoje: { kcal: t.kcal, proteina: t.proteina, carboidrato: t.carboidrato, gordura: t.gordura, refeicoes: t.refs.map((r) => `${r.tipo}: ${r.titulo || r.itens.map((i) => i.nome).join(", ")} (${r.kcal} kcal)`) },
    ultimos_treinos: treinos,
    metricas_7_dias: metricas,
    ultima_comparacao: comps[0] || null,
    plano_treino: E.plano ? { dias: E.plano.dias, equipamento: E.plano.equipamento } : null,
  };
}

export function abrirAgente(ag) { agenteAtual = ag; }

export async function telaCoach(el, { rerender }) {
  const ag = AGENTES[agenteAtual];
  const msgs = (await listar("chat")).filter((m) => m.agente === agenteAtual);
  el.innerHTML = `
    <div class="tela tela--chat">
      <div class="seg">
        ${Object.entries(AGENTES).map(([k, a]) => `<button class="seg-b ${k === agenteAtual ? "seg-b--on" : ""}" data-ag="${k}">${a.emoji} ${a.nome} · ${a.papel}</button>`).join("")}
      </div>
      <div class="chat" id="chat">
        <div class="msg msg--ia"><span class="msg-av">${ag.emoji}</span><div>${esc(ag.ola)}</div></div>
        ${msgs.map((m) => bolha(m)).join("")}
      </div>
      <div class="chips-rolar" id="sugs">${ag.sugestoes.map((s) => `<button class="chip" data-sug="${esc(s)}">${esc(s)}</button>`).join("")}</div>
      <form class="chat-in" id="form">
        <textarea id="txt" rows="1" class="campo" placeholder="Pergunte para ${ag.nome}…"></textarea>
        <button class="chat-enviar" aria-label="Enviar">➤</button>
      </form>
    </div>`;

  const chat = el.querySelector("#chat");
  const rolar = () => { chat.scrollTop = chat.scrollHeight; window.scrollTo(0, document.body.scrollHeight); };
  rolar();
  el.querySelectorAll("[data-ag]").forEach((b) => b.onclick = () => { agenteAtual = b.dataset.ag; rerender(); });
  const txt = el.querySelector("#txt");
  txt.oninput = () => { txt.style.height = "auto"; txt.style.height = `${Math.min(120, txt.scrollHeight)}px`; };
  el.querySelectorAll("[data-sug]").forEach((b) => b.onclick = () => { txt.value = b.dataset.sug; enviar(); });
  txt.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(); } };
  el.querySelector("#form").onsubmit = (e) => { e.preventDefault(); enviar(); };

  let ocupado = false;
  async function enviar() {
    const texto = txt.value.trim();
    if (!texto || ocupado) return;
    if (E.modoLocal) return toast("Os especialistas de IA precisam de uma conta (Perfil → Entrar).", "erro");
    ocupado = true;
    txt.value = ""; txt.style.height = "auto";
    const minha = await gravar("chat", { agente: agenteAtual, papel: "user", texto });
    chat.insertAdjacentHTML("beforeend", bolha(minha));
    chat.insertAdjacentHTML("beforeend", `<div class="msg msg--ia" id="digitando"><span class="msg-av">${ag.emoji}</span><div class="digitando"><i></i><i></i><i></i></div></div>`);
    el.querySelector("#sugs").classList.add("oculto");
    rolar();
    try {
      const hist = [...msgs, minha].map((m) => ({ papel: m.papel, texto: m.texto }));
      const r = await conversar({ agente: agenteAtual, historico: hist, contexto: await contexto() });
      // A Nina detecta "não gosto de X" / "agora gosto de Y" e atualiza o perfil.
      const add = r.adicionar_nao_gosta || [], rem = r.remover_nao_gosta || [];
      let anotacao = "";
      if (add.length || rem.length) {
        await salvarPerfil({ ...E.perfil, naoGosta: remover(juntar(E.perfil.naoGosta, add), rem), gostosPerguntados: true });
        anotacao = [add.length ? `não gosta de ${add.join(", ")}` : "", rem.length ? `voltou a comer ${rem.join(", ")}` : ""].filter(Boolean).join(" · ");
        toast("📝 Preferência salva no seu perfil");
      }
      const resp = await gravar("chat", { agente: agenteAtual, papel: "assistant", texto: r.resposta, anotacao });
      msgs.push(minha, resp);
      el.querySelector("#digitando").outerHTML = bolha(resp);
    } catch (e) {
      el.querySelector("#digitando").outerHTML = `<div class="msg msg--erro">Não consegui responder agora (${esc(e.message)}). Tente de novo em instantes.</div>`;
    }
    ocupado = false;
    rolar();
  }
}

// Markdown mínimo (negrito, listas, quebras) — a IA responde em texto simples.
function formatar(t) {
  return esc(t)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/^[-•] (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
    .replace(/\n{2,}/g, "<br><br>").replace(/\n/g, "<br>");
}

function bolha(m) {
  const ag = AGENTES[m.agente];
  return m.papel === "user"
    ? `<div class="msg msg--eu"><div>${esc(m.texto)}</div></div>`
    : `<div class="msg msg--ia"><span class="msg-av">${ag.emoji}</span><div>${formatar(m.texto)}${m.anotacao ? `<small class="msg-anot">📝 Anotei no seu perfil: ${esc(m.anotacao)}</small>` : ""}</div></div>`;
}
