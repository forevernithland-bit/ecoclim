// Tela de treino: plano do ciclo atual, volume semanal por músculo
// ("avaliação do personal"), troca de exercícios, ajustes e início da sessão
// (a sessão em si — cronômetro, avisos, séries — fica em ../sessao.js).
import { esc, num, toast, abrirSheet, dataBR, carregando } from "../ui.js";
import {
  treinosDoCiclo, cicloAtual, diasParaTroca, nomeDivisao, cardio, REGRAS_TREINO, EQUIPAMENTOS, gerarPlano,
  DIAS_SEMANA, MINUTOS, PADRAO_DIAS, FOCOS, volumeSemanal, alternativas, htmlChipsFoco, alternarFoco, nomeFocos, listaFocos,
} from "../treino.js";
import { E, listar, salvarPlano, salvarPerfil } from "../estado.js";
import { hojeISO } from "../db.js";
import { iniciarSessao, sessaoAtual, abrirSessao } from "../sessao.js";
import { conversar, resumoPerfil } from "../ia.js";
import { abrirAdicionarExercicios } from "./adicionar-exercicio.js";
import { abrirRegistrarEsporte } from "./esporte.js";

export const cicloDoPlano = (pl) => cicloAtual(pl) + (pl.offset || 0);

export async function proximoTreino() {
  const pl = E.plano;
  const dias = treinosDoCiclo(pl, cicloDoPlano(pl));
  const logs = await listar("treinos");
  const doPlano = logs.filter((l) => !l.livre && l.diaIndice >= 0);
  const ult = doPlano[doPlano.length - 1];
  const idx = ult ? (ult.diaIndice + 1) % dias.length : 0;
  const feitoHoje = logs.some((l) => l.data === hojeISO());
  return { dia: dias[idx], dias, feitoHoje, logs };
}

let abaDia = null;
export const resetAbaTreino = () => { abaDia = null; };

export async function telaTreino(el, { rerender }) {
  const pl = E.plano;
  const ciclo = cicloDoPlano(pl);
  const { dia: prox, dias, logs } = await proximoTreino();
  if (abaDia == null || abaDia >= dias.length) abaDia = prox.indice;
  const d = dias[abaDia];
  const semana = logs.filter((l) => l.data >= inicioSemana()).length;
  const cardioInfo = cardio(E.perfil);
  const vol = volumeSemanal(dias, pl.foco);
  const sessao = await sessaoAtual();
  const emAndamento = sessao && sessao.diaIndice === d.indice;

  el.innerHTML = `
    <div class="tela entra">
      <div class="card card--treino-topo">
        <div>
          <div class="card-tag">🏋️ ${esc(nomeDivisao(pl))}</div>
          <p class="nota">${(pl.diasSemana || PADRAO_DIAS[pl.dias]).map((x) => DIAS_SEMANA[x]).join(", ")} · ${pl.minutos || 60} min</p>
          ${nomeFocos(pl.foco) ? `<p class="nota"><b>Prioridade: ${nomeFocos(pl.foco)}</b></p>` : ""}
          <p class="nota">Ciclo ${ciclo + 1} · exercícios mudam em <b>${diasParaTroca(pl)} dias</b></p>
        </div>
        <div class="semana-bolinhas" aria-label="Treinos na semana">${Array.from({ length: pl.dias }, (_, i) => `<span class="${i < semana ? "on" : ""}"></span>`).join("")}<small>${semana}/${pl.dias} na semana</small></div>
      </div>

      <div class="abas-dia">
        ${dias.map((x) => `<button class="aba ${x.indice === abaDia ? "aba--on" : ""}" data-aba="${x.indice}">${x.letra}${x.indice === prox.indice ? '<i class="ponto"></i>' : ""}</button>`).join("")}
        <button class="aba aba--icone" id="ajustes" aria-label="Ajustar plano">⚙️</button>
      </div>

      <h2 class="titulo-dia">Treino ${d.letra} — ${esc(d.nome)}</h2>
      <p class="nota">⏱️ ~${d.minutos} min · ${d.exercicios.length} exercícios${d.exercicios.some((x) => x.biset) ? " · 🔗 com supersets pra caber no tempo" : ""}</p>
      ${d.indice === prox.indice ? `<p class="nota">👉 Este é o seu próximo treino.</p>` : ""}

      <div class="lista-ex">
        ${d.exercicios.map((x, k) => {
          const ultimo = ultimaCarga(logs, x.nome);
          const noPar = x.biset || (k > 0 && d.exercicios[k - 1].biset);
          const selo = x.biset ? (x.parTipo === "braco" ? "🔗 bi-set com o próximo" : "🔗 superset com o próximo") : "";
          return `
          <details class="ex ${x.foco ? "ex--foco" : ""} ${noPar ? "ex--biset" : ""}">
            <summary>
              <span class="ex-num">${k + 1}</span>
              <span class="ex-txt"><b>${esc(x.nome)}</b>${selo ? `<em class="selo-biset">${selo}</em>` : ""}${x.adicionado ? `<em class="selo-add">✍️ adicionado por você</em>` : ""}<small>${x.series} × ${x.reps} · ${x.biset ? "sem descanso → vá direto pro próximo" : `descanso ${x.descanso}`}${ultimo ? ` · última: ${esc(ultimo)}` : ""}</small></span>
            </summary>
            <div class="ex-corpo">
              <p class="nota">🎯 ${esc(x.grupo)}</p>
              <p>${esc(x.dica)}</p>
              <p class="nota">Pare com ~${x.rir} repetições "sobrando" (RIR ${x.rir}).</p>
              ${x.biset ? `<p class="nota">🔗 ${x.parTipo === "braco" ? "Bi-set" : "Superset"}: faça 1 série deste e já emende 1 série do próximo; descanse depois do par. Como os músculos são diferentes, um descansa enquanto o outro trabalha — mesmo resultado em menos tempo.</p>` : ""}
              <div class="linha-botoes">
                <a class="btn btn--sec btn--peq" href="${x.video}" target="_blank" rel="noopener">▶ Vídeo</a>
                ${x.adicionado ? `<button class="btn btn--sec btn--peq" data-remover-add="${k}">✕ Tirar do treino</button>` : `<button class="btn btn--sec btn--peq" data-trocar="${k}">🔄 Trocar</button>`}
              </div>
            </div>
          </details>`;
        }).join("")}
      </div>

      <button class="btn btn--sec" id="add-plano">➕ Adicionar exercício ao Treino ${d.letra} (digitar)</button>

      <button class="btn btn--grande" id="iniciar">${emAndamento ? `Continuar treino ${d.letra} ▶ (em andamento)` : `Iniciar treino ${d.letra} ▶`}</button>
      <p class="nota centro">Ao iniciar, o cronômetro começa sozinho e te aviso quando der ${pl.minutos || 60} min.</p>
      <button class="btn btn--sec" id="livre">✍️ Treino livre — digitar os exercícios que vou fazer</button>
      <button class="btn btn--sec" id="esporte">🏅 Registrar outro esporte (natação, corrida, bike, jiu-jitsu…)</button>

      <div class="card">
        <div class="card-tag">📊 Volume semanal por músculo</div>
        <p class="nota">Séries por semana somando todos os treinos. Faixa ideal pra ganhar músculo: <b>10–20</b> (o grupo prioritário pode ir mais alto).</p>
        <div class="vol-lista">
          ${vol.map((v) => {
            const max = 24;
            return `<div class="vol-linha vol--${v.status}">
              <span class="vol-nome">${v.foco ? "⭐ " : ""}${esc(v.nome)}</span>
              <div class="vol-trilho"><div class="vol-faixa" style="left:${(v.alvo[0] / max) * 100}%;width:${((v.alvo[1] - v.alvo[0]) / max) * 100}%"></div><div class="vol-barra" style="width:${Math.min(100, (v.series / max) * 100)}%"></div></div>
              <b>${v.series}</b>
            </div>`;
          }).join("")}
        </div>
        <p class="nota">${vol.some((v) => v.status === "baixo")
          ? (vol.filter((v) => v.status === "baixo").every((v) => v.foco)
            ? `⚠️ ${vol.filter((v) => v.status === "baixo").map((v) => v.nome).join(", ")} (prioridade) abaixo do ideal: no tempo disponível, o app não tira volume dos outros músculos pra não desequilibrar o corpo. Com +10 min por treino ou +1 dia na semana, o foco chega no ideal.`
            : `⚠️ ${vol.filter((v) => v.status === "baixo").map((v) => v.nome).join(", ")} abaixo do ideal — com mais tempo por treino ou mais dias na semana isso sobe.`)
          : "✅ Todos os grupos dentro da faixa recomendada — foco sem desequilibrar o resto."}</p>
        <button class="btn btn--sec btn--peq" id="avaliar">🏋️ Pedir avaliação do Léo (personal IA)</button>
        <div id="avaliacao"></div>
      </div>

      <div class="card">
        <div class="card-tag">🚶 Cardio e passos</div>
        <p>${esc(cardioInfo.texto)}</p>
      </div>

      <details class="card">
        <summary class="card-tag">📚 Como o seu treino foi montado (ciência)</summary>
        <ul class="regras">${[...REGRAS_TREINO,
          "Volume é o que mais importa: 10–20 séries por músculo por semana, divididas em 2+ treinos.",
          "Treinar peito e costas juntos (antagonistas) em superset mantém o desempenho e economiza ~30% do tempo.",
          "Descanso de ~2 min nos exercícios pesados rende mais músculo que descansos curtos.",
          "Dividir por grupo (ABC) ou fazer corpo inteiro dá o mesmo resultado quando o volume é igual — o que muda é a frequência.",
        ].map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
      </details>

      ${logs.length ? `
      <div class="card">
        <div class="card-tag">🗓️ Últimos treinos</div>
        ${logs.slice(-6).reverse().map((l) => `<div class="linha-hist"><span>${dataBR(l.data, { weekday: "short", day: "2-digit", month: "short" })}</span><b>${l.tipo === "esporte" ? `${l.emoji || "🏅"} ` : ""}${esc(l.nome)}</b><small>${l.duracaoMin || "–"} min${l.kcal ? ` · ≈${num(l.kcal)} kcal` : ""}${l.intensidade ? ` · ${{ leve: "leve", moderado: "moderada", intenso: "intensa", muito: "muito intensa" }[l.intensidade] || ""}` : ""}${l.automatico ? " (auto)" : ""}</small></div>`).join("")}
      </div>` : ""}
    </div>`;

  el.querySelectorAll("[data-aba]").forEach((b) => b.onclick = () => { abaDia = +b.dataset.aba; rerender(); });
  el.querySelector("#iniciar").onclick = () => (emAndamento ? abrirSessao() : iniciarSessao(d, ciclo));
  el.querySelector("#ajustes").onclick = () => ajustesPlano(rerender);
  el.querySelectorAll("[data-trocar]").forEach((b) => b.onclick = () => trocarNoPlano(d.exercicios[+b.dataset.trocar], rerender));
  el.querySelector("#add-plano").onclick = () => abrirAdicionarExercicios({
    titulo: `➕ Adicionar ao Treino ${d.letra}`,
    botao: `Adicionar ao Treino ${d.letra}`,
    aoConfirmar: async (novos) => {
      const adicionados = { ...(E.plano.adicionados || {}) };
      adicionados[d.indice] = [...(adicionados[d.indice] || []), ...novos];
      await salvarPlano({ ...E.plano, adicionados });
      toast(`Adicionado ao Treino ${d.letra} — aparece em todo Treino ${d.letra} ✅`);
      rerender();
    },
  });
  el.querySelectorAll("[data-remover-add]").forEach((b) => b.onclick = async () => {
    const x = d.exercicios[+b.dataset.removerAdd];
    const adicionados = { ...(E.plano.adicionados || {}) };
    adicionados[d.indice] = (adicionados[d.indice] || []).filter((a) => a.nome !== x.nome);
    await salvarPlano({ ...E.plano, adicionados });
    toast("Tirado do treino"); rerender();
  });
  el.querySelector("#esporte").onclick = () => abrirRegistrarEsporte(rerender);
  el.querySelector("#livre").onclick = () => abrirAdicionarExercicios({
    titulo: "✍️ Treino livre",
    botao: "Começar treino livre ▶",
    aoConfirmar: async (novos) => {
      await iniciarSessao({ indice: -1, letra: "livre", nome: "Treino livre", exercicios: novos }, ciclo);
    },
  });
  el.querySelector("#avaliar").onclick = (ev) => avaliarComLeo(ev.target, el.querySelector("#avaliacao"), dias, vol);
}

function inicioSemana() {
  const d = new Date();
  const dia = (d.getDay() + 6) % 7; // segunda = 0
  d.setDate(d.getDate() - dia);
  return hojeISO(d);
}

function ultimaCarga(logs, nome) {
  for (let i = logs.length - 1; i >= 0; i--) {
    const ex = (logs[i].exercicios || []).find((e) => e.nome === nome);
    if (ex) {
      const feitas = (ex.series || []).filter((s) => s.feito && (s.kg || s.reps));
      if (feitas.length) {
        const melhor = feitas.reduce((a, b) => ((+b.kg || 0) > (+a.kg || 0) ? b : a));
        return `${melhor.kg ? `${num(melhor.kg, 1)} kg × ` : ""}${melhor.reps || "?"}`;
      }
    }
  }
  return "";
}

// Troca definitiva (vale até o próximo ciclo, quando os exercícios mudam)
function trocarNoPlano(x, aoMudar) {
  const alts = alternativas(x.slot, E.plano.equipamento, x.nome);
  const sh = abrirSheet(`
    <h2>🔄 Trocar "${esc(x.nome)}"</h2>
    <p class="sub">Opções que trabalham o mesmo músculo (${esc(x.grupo)}). A troca vale até o próximo ciclo.</p>
    <div class="lista-troca">${alts.map((a, i) => `<button class="troca-op" data-i="${i}"><b>${esc(a.nome)}</b><small>${a.equipamento === "academia" ? "academia" : a.equipamento === "casa" ? "halteres em casa" : "peso do corpo"}</small></button>`).join("")}</div>
    ${E.plano.trocas && E.plano.trocas[x.original] ? `<button class="link" id="desfazer">Voltar para o original (${esc(x.original)})</button>` : ""}`);
  sh.el.querySelectorAll("[data-i]").forEach((b) => b.onclick = async () => {
    const a = alts[+b.dataset.i];
    await salvarPlano({ ...E.plano, trocas: { ...(E.plano.trocas || {}), [x.original]: a.nome } });
    sh.fechar(); toast("Exercício trocado ✅"); aoMudar();
  });
  const desf = sh.el.querySelector("#desfazer");
  if (desf) desf.onclick = async () => {
    const trocas = { ...(E.plano.trocas || {}) }; delete trocas[x.original];
    await salvarPlano({ ...E.plano, trocas });
    sh.fechar(); aoMudar();
  };
}

async function avaliarComLeo(botao, caixa, dias, vol) {
  if (E.modoLocal) return toast("A avaliação do Léo precisa de uma conta.", "erro");
  botao.disabled = true;
  caixa.innerHTML = carregando("O Léo está analisando seu treino…");
  try {
    const plano = dias.map((d) => `Treino ${d.letra} (${d.nome}, ~${d.minutos} min): ` + d.exercicios.map((x) => `${x.nome} ${x.series}x${x.reps}${x.biset ? " [superset c/ próximo]" : ""}`).join("; ")).join("\n");
    const pergunta = `Avalie meu plano de treino como personal, com base na ciência mais atual (volume semanal, frequência, ordem, descanso, supersets). Diga o que está bom e sugira no máximo 3 ajustes, se fizer sentido pro meu objetivo e meu tempo.\n\n${plano}\n\nVolume semanal: ${vol.map((v) => `${v.nome} ${v.series}`).join(", ")}`;
    const r = await conversar({ agente: "coach", historico: [{ papel: "user", texto: pergunta }], contexto: { perfil: resumoPerfil(E.perfil), plano: { dias: E.plano.dias, minutos: E.plano.minutos, foco: E.plano.foco, equipamento: E.plano.equipamento } } });
    caixa.innerHTML = `<div class="dica-ia">🏋️ <span>${esc(r.resposta).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>")}</span></div>`;
  } catch (e) {
    caixa.innerHTML = `<p class="erro-txt">${esc(e.message)}</p>`;
    botao.disabled = false;
  }
}

function ajustesPlano(aoMudar) {
  const pl = E.plano;
  let semana = [...(pl.diasSemana || PADRAO_DIAS[pl.dias])];
  let min = pl.minutos || 60;
  const s = abrirSheet(`
    <h2>Ajustar treino</h2>
    <label class="rotulo">Dias de treino</label>
    <div class="semana-sel">${DIAS_SEMANA.map((d, k) => `<button class="sem-b ${semana.includes(k) ? "sem-b--on" : ""}" data-diasem="${k}">${d}</button>`).join("")}</div>
    <label class="rotulo">Tempo por dia</label>
    <div class="dias-sel">${MINUTOS.map((m) => `<button class="dia-b dia-b--larg ${min === m ? "dia-b--on" : ""}" data-min="${m}">${m} min</button>`).join("")}</div>
    <label class="rotulo">Prioridade muscular (até 2)</label>
    <div class="chips-quebra" id="chips-foco">${htmlChipsFoco(pl.foco)}</div>
    <p class="nota">O foco ganha volume extra sem tirar o mínimo dos outros músculos.</p>
    <label class="rotulo">Local</label>
    <div class="opcoes">${Object.entries(EQUIPAMENTOS).map(([k, o]) => `<button class="opcao opcao--linha ${pl.equipamento === k ? "opcao--on" : ""}" data-eq="${k}"><span class="opcao-emoji">${o.emoji}</span><span><b>${o.rotulo}</b></span></button>`).join("")}</div>
    <label class="rotulo">Trocar exercícios a cada</label>
    <div class="dias-sel">${[4, 6, 8].map((w) => `<button class="dia-b dia-b--larg ${pl.semanasCiclo === w ? "dia-b--on" : ""}" data-ciclo="${w}">${w} sem</button>`).join("")}</div>
    <button class="btn btn--sec" id="variar">🔄 Variar exercícios agora</button>
    <button class="btn btn--grande" id="salvar">Salvar</button>`);
  let eq = pl.equipamento, sem = pl.semanasCiclo, foco = listaFocos(pl.foco);
  s.el.querySelectorAll("[data-diasem]").forEach((b) => b.onclick = () => {
    const d = +b.dataset.diasem;
    const novo = semana.includes(d) ? semana.filter((x) => x !== d) : [...semana, d].sort();
    if (novo.length > 6) return toast("No máximo 6 dias por semana.", "erro");
    semana = novo;
    b.classList.toggle("sem-b--on", semana.includes(d));
  });
  const liga = (attr, cls, set) => s.el.querySelectorAll(`[data-${attr}]`).forEach((b) => b.onclick = () => {
    set(b.dataset[attr]);
    s.el.querySelectorAll(`[data-${attr}]`).forEach((x) => x.classList.toggle(cls, x === b));
  });
  liga("min", "dia-b--on", (v) => { min = +v; });
  const ligaFoco = () => s.el.querySelectorAll("[data-foco]").forEach((b) => b.onclick = () => {
    const r = alternarFoco(foco, b.dataset.foco);
    if (r.erro) return toast(r.erro, "erro");
    foco = r.lista;
    s.el.querySelector("#chips-foco").innerHTML = htmlChipsFoco(foco);
    ligaFoco();
  });
  ligaFoco();
  liga("eq", "opcao--on", (v) => { eq = v; });
  liga("ciclo", "dia-b--on", (v) => { sem = +v; });
  s.el.querySelector("#variar").onclick = async () => {
    await salvarPlano({ ...pl, offset: (pl.offset || 0) + 1, trocas: {} });
    s.fechar(); toast("Exercícios variados ✅"); aoMudar();
  };
  s.el.querySelector("#salvar").onclick = async () => {
    if (!semana.length) return toast("Escolha pelo menos 1 dia.", "erro");
    await salvarPerfil({ ...E.perfil, diasTreino: semana.length, diasSemana: semana, minutosTreino: min, equipamento: eq, focoMuscular: foco });
    const novo = { ...gerarPlano(E.perfil, { inicio: pl.inicio, semanasCiclo: sem }), offset: pl.offset || 0, trocas: eq === pl.equipamento ? (pl.trocas || {}) : {} };
    await salvarPlano(novo);
    abaDia = null;
    s.fechar(); toast("Plano atualizado ✅"); aoMudar();
  };
}
