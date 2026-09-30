// Sessão de treino em andamento: cronômetro que continua mesmo fechando a
// tela/app (fica salvo no aparelho), aviso quando der o tempo planejado,
// conclusão automática se ninguém responder em 1 h, e edição dos exercícios
// (check, ± séries, trocar por um parecido).
import { esc, num, toast, abrirSheet, confirmar } from "./ui.js";
import { kvGet, kvSet, hojeISO } from "./db.js";
import { E, gravar, listar, salvarPlano } from "./estado.js";
import { alternativas, linkVideo, segundos, duracaoSessao } from "./treino.js";
import { gastoAtividade } from "./esportes.js";

const CHAVE = "sessaoTreino";
const UMA_HORA = 60 * 60 * 1000;
let sheetAberto = null;   // { fechar, el }
let aoMudarTela = () => {};

export const sessaoAtual = () => kvGet(CHAVE, null);
const salvarSessao = (s) => kvSet(CHAVE, s);
const hhmm = (ms) => { const d = new Date(ms); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
const relogio = (seg) => `${String(Math.floor(seg / 3600)).padStart(1, "0")}:${String(Math.floor((seg % 3600) / 60)).padStart(2, "0")}:${String(seg % 60).padStart(2, "0")}`.replace(/^0:/, "");

function valoresAnteriores(logs, nome) {
  for (let i = logs.length - 1; i >= 0; i--) {
    const ex = (logs[i].exercicios || []).find((e) => e.nome === nome);
    if (ex) return ex.series || [];
  }
  return [];
}

// Exercício do plano (ou digitado) → formato da sessão, com a carga da última vez
function exercicioDaSessao(x, logs) {
  const ant = valoresAnteriores(logs, x.nome);
  return {
    slot: x.slot, nome: x.nome, original: x.original || x.nome, grupo: x.grupo, dica: x.dica, video: x.video, reps: x.reps, rir: x.rir,
    descanso: x.descanso, biset: !!x.biset, parTipo: x.parTipo || null, foco: !!x.foco, concluido: false, tipo: x.tipo || "forca",
    series: Array.from({ length: x.series }, (_, i) => ({ kg: ant[i] ? ant[i].kg : (x.kgSugerido || ""), reps: ant[i] ? ant[i].reps : "", feito: false })),
  };
}

// ---------- Início ----------
export async function iniciarSessao(dia, ciclo) {
  const ativa = await sessaoAtual();
  if (ativa) {
    if (ativa.diaIndice === dia.indice) return abrirSessao();
    if (!(await confirmar(`Você tem o Treino ${ativa.letra} em andamento. Descartar e começar o Treino ${dia.letra}?`, { ok: "Começar o novo", perigo: true }))) return abrirSessao();
  }
  const logs = await listar("treinos");
  const minutos = E.plano.minutos || 60;
  const agora = Date.now();
  const s = {
    diaIndice: dia.indice, letra: dia.letra, nome: dia.nome, ciclo, inicio: agora, minutosPlano: minutos,
    avisoEm: agora + minutos * 60000, aguardando: false, perguntadoEm: null,
    livre: dia.indice < 0,
    exercicios: dia.exercicios.map((x) => exercicioDaSessao(x, logs)),
  };
  await salvarSessao(s);
  pedirPermissaoAviso();
  toast(`⏱️ Cronômetro iniciado — te aviso em ${minutos} min`);
  abrirSessao();
}

function pedirPermissaoAviso() {
  try {
    if ("Notification" in window && Notification.permission === "default") Notification.requestPermission().catch(() => {});
  } catch (e) { /* navegador sem suporte */ }
}

// ---------- Tela da sessão ----------
export async function abrirSessao() {
  const s = await sessaoAtual();
  if (!s) return;
  if (sheetAberto) sheetAberto.fechar();
  const minutosAgora = () => Math.floor((Date.now() - s.inicio) / 1000);
  const sh = abrirSheet(`
    <div class="exec-topo">
      <div><h2>${s.livre ? "✍️ Treino livre" : `Treino ${esc(s.letra)}`}</h2><small class="nota">${s.livre ? "exercícios digitados por você" : esc(s.nome)}</small></div>
      <div class="cron-caixa"><span id="cron" class="cron">0:00</span><small id="cron-meta">meta ${s.minutosPlano} min</small></div>
    </div>
    <div class="cron-trilho"><div id="cron-barra"></div></div>
    <div id="lista-sessao"></div>
    <button class="btn btn--sec" id="add-ex">➕ Adicionar exercício (digitar ou falar)</button>
    <div id="descanso" class="descanso oculto"><span>Descanso</span><b id="desc-t">1:30</b><button id="pular">Pular</button></div>
    <div class="linha-botoes">
      <button class="btn btn--sec" id="minimizar">Minimizar</button>
      <button class="btn" id="concluir">Concluir treino 🏁</button>
    </div>
    <p class="nota centro">O cronômetro continua mesmo se você fechar o app.</p>`, { cheia: true, aoFechar: () => { sheetAberto = null; clearInterval(iv); clearInterval(ivDesc); atualizarBarraSessao(); } });
  sheetAberto = sh;
  atualizarBarraSessao();

  const cron = sh.el.querySelector("#cron"), barra = sh.el.querySelector("#cron-barra");
  const tick = () => {
    const seg = minutosAgora();
    cron.textContent = relogio(seg);
    const pct = Math.min(100, (seg / (s.minutosPlano * 60)) * 100);
    barra.style.width = `${pct}%`;
    barra.classList.toggle("cron-passou", seg > s.minutosPlano * 60);
  };
  tick();
  const iv = setInterval(tick, 1000);

  let ivDesc = null;
  const caixaDesc = sh.el.querySelector("#descanso");
  const iniciarDescanso = (texto) => {
    let seg = segundos(texto) || 90;
    clearInterval(ivDesc);
    caixaDesc.classList.remove("oculto");
    const t = sh.el.querySelector("#desc-t");
    const pinta = () => { t.textContent = `${Math.floor(seg / 60)}:${String(seg % 60).padStart(2, "0")}`; };
    pinta();
    ivDesc = setInterval(() => {
      seg--; pinta();
      if (seg <= 0) {
        clearInterval(ivDesc); caixaDesc.classList.add("oculto");
        if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
        toast("Bora pra próxima série! 💪");
      }
    }, 1000);
  };
  sh.el.querySelector("#pular").onclick = () => { clearInterval(ivDesc); caixaDesc.classList.add("oculto"); };

  const salvar = () => salvarSessao(s);
  const pintaLista = () => {
    sh.el.querySelector("#lista-sessao").innerHTML = s.exercicios.map((x, k) => {
      const emPar = x.biset || (k > 0 && s.exercicios[k - 1].biset);
      const rotuloPar = x.biset ? (x.parTipo === "braco" ? "🔗 bi-set com o próximo" : "🔗 superset com o próximo") : "";
      return `
      <div class="exec-ex ${x.concluido ? "exec-ex--ok" : ""} ${emPar ? "exec-ex--par" : ""}" data-ex="${k}">
        <div class="exec-nome">
          <button class="check-ex ${x.concluido ? "check-ex--on" : ""}" data-acao="concluir" aria-label="Exercício concluído">✓</button>
          <div class="exec-nome-txt"><b>${k + 1}. ${esc(x.nome)}</b>${rotuloPar ? `<em class="selo-biset">${rotuloPar}</em>` : ""}
            <small class="nota">${x.series.length} × ${esc(x.reps)} · ${x.biset ? "sem descanso → vá pro próximo" : `descanso ${esc(x.descanso)}`} · RIR ${esc(x.rir)}</small></div>
          <a href="${x.video}" target="_blank" rel="noopener" class="exec-video" aria-label="Vídeo">▶</a>
        </div>
        ${x.concluido ? "" : `
        <div class="exec-ferr">
          <div class="porcao"><button data-acao="menos" aria-label="Menos uma série">−</button><span>${x.series.length} séries</span><button data-acao="mais" aria-label="Mais uma série">+</button></div>
          <button class="link link--fraco" data-acao="trocar">🔄 Trocar exercício</button>
        </div>
        <div class="series">
          <div class="serie serie--cab"><span>Série</span><span>kg</span><span>reps</span><span>✓</span></div>
          ${x.series.map((se, j) => `
            <div class="serie ${se.feito ? "serie--feita" : ""}" data-s="${j}">
              <span>${j + 1}</span>
              <input type="number" inputmode="decimal" step="0.5" class="campo campo--mini" data-campo="kg" value="${esc(se.kg)}" placeholder="–">
              <input type="number" inputmode="numeric" class="campo campo--mini" data-campo="reps" value="${esc(se.reps)}" placeholder="${esc(String(x.reps).split("–")[0])}">
              <button class="check ${se.feito ? "check--on" : ""}" data-check aria-label="Série feita">✓</button>
            </div>`).join("")}
        </div>`}
      </div>`;
    }).join("");

    sh.el.querySelectorAll(".exec-ex").forEach((box) => {
      const k = +box.dataset.ex, x = s.exercicios[k];
      box.querySelectorAll("[data-acao]").forEach((b) => b.onclick = async () => {
        const acao = b.dataset.acao;
        if (acao === "concluir") {
          x.concluido = !x.concluido;
          if (x.concluido) x.series.forEach((se) => { se.feito = true; if (!se.reps) se.reps = String(x.reps).split("–")[0]; });
          if (x.concluido && s.exercicios.every((e) => e.concluido)) toast("Todos os exercícios feitos! Toque em Concluir treino 🏁");
        }
        if (acao === "menos" && x.series.length > 1) x.series.pop();
        if (acao === "mais" && x.series.length < 8) { const u = x.series[x.series.length - 1] || {}; x.series.push({ kg: u.kg || "", reps: "", feito: false }); }
        if (acao === "trocar") return trocarNaSessao(x, () => { salvar(); pintaLista(); });
        await salvar(); pintaLista();
      });
      box.querySelectorAll(".serie[data-s]").forEach((row) => {
        const j = +row.dataset.s, se = x.series[j];
        row.querySelectorAll("input").forEach((inp) => inp.oninput = () => { se[inp.dataset.campo] = inp.value; salvar(); });
        row.querySelector("[data-check]").onclick = async (ev) => {
          se.feito = !se.feito;
          if (se.feito && !se.reps) { se.reps = String(x.reps).split("–")[0]; row.querySelector('[data-campo="reps"]').value = se.reps; }
          ev.currentTarget.classList.toggle("check--on", se.feito);
          row.classList.toggle("serie--feita", se.feito);
          if (x.series.every((q) => q.feito)) { x.concluido = true; await salvar(); pintaLista(); }
          else await salvar();
          if (se.feito) {
            if (x.biset && s.exercicios[k + 1]) toast(`🔗 Vá direto para ${s.exercicios[k + 1].nome}`);
            else iniciarDescanso(x.descanso);
          }
        };
      });
    });
  };
  pintaLista();

  sh.el.querySelector("#add-ex").onclick = async () => {
    const { abrirAdicionarExercicios } = await import("./telas/adicionar-exercicio.js");
    abrirAdicionarExercicios({
      titulo: "➕ Adicionar ao treino de hoje",
      botao: "Adicionar ao treino",
      aoConfirmar: async (novos) => {
        for (const x of novos) s.exercicios.push(exercicioDaSessao(x, []));
        await salvar(); pintaLista();
        toast(`${novos.length} exercício(s) adicionado(s) ✅`);
      },
    });
  };
  sh.el.querySelector("#minimizar").onclick = () => sh.fechar();
  sh.el.querySelector("#concluir").onclick = () => concluirComHorario();
}

// Troca durante o treino: só hoje, ou também no plano (até o próximo ciclo)
function trocarNaSessao(x, depois) {
  const alts = alternativas(x.slot, E.plano.equipamento, x.nome);
  const sh = abrirSheet(`
    <h2>🔄 Trocar "${esc(x.nome)}"</h2>
    <p class="sub">Opções que trabalham o mesmo músculo (${esc(x.grupo)}):</p>
    <div class="lista-troca">${alts.map((a, i) => `<button class="troca-op" data-i="${i}"><b>${esc(a.nome)}</b><small>${a.equipamento === "academia" ? "academia" : a.equipamento === "casa" ? "halteres em casa" : "peso do corpo"}</small></button>`).join("")}</div>
    <label class="linha-check"><input type="checkbox" id="no-plano"> Usar essa troca também nos próximos treinos</label>`);
  sh.el.querySelectorAll("[data-i]").forEach((b) => b.onclick = async () => {
    const a = alts[+b.dataset.i];
    const noPlano = sh.el.querySelector("#no-plano").checked;
    if (noPlano) {
      const trocas = { ...(E.plano.trocas || {}), [x.original || x.nome]: a.nome };
      await salvarPlano({ ...E.plano, trocas });
    }
    x.nome = a.nome; x.video = linkVideo(a.nome);
    sh.fechar();
    toast(noPlano ? "Trocado — e salvo no seu plano ✅" : "Trocado só neste treino ✅");
    depois();
  });
}

// ---------- Conclusão ----------
async function concluirComHorario() {
  const s = await sessaoAtual();
  if (!s) return;
  const feitas = s.exercicios.reduce((a, e) => a + e.series.filter((x) => x.feito).length, 0);
  const sh = abrirSheet(`
    <h2>🏁 Concluir treino ${esc(s.letra)}</h2>
    <p class="nota">Começou às <b>${hhmm(s.inicio)}</b> · ${feitas} séries marcadas</p>
    <label class="rotulo">Como foi a intensidade do treino?</label>
    <div class="int-sel">${[["leve", "🙂", "Leve"], ["moderado", "😅", "Moderado"], ["intenso", "🥵", "Intenso"], ["muito", "💀", "No limite"]].map(([k, e, n]) => `<button type="button" class="int-b" data-int="${k}"><span>${e}</span>${n}</button>`).join("")}</div>
    <label class="rotulo">Terminou que horas?</label>
    <input type="time" class="campo" id="fim" value="${hhmm(Date.now())}">
    <p class="nota" id="dur"></p>
    <button class="btn btn--grande" id="ok">Salvar treino ✅</button>
    <button class="link link--fraco" id="descartar">Descartar este treino</button>`);
  const inp = sh.el.querySelector("#fim"), dur = sh.el.querySelector("#dur");
  const fimMs = () => {
    const [h, m] = inp.value.split(":").map(Number);
    const d = new Date(s.inicio); d.setHours(h, m, 0, 0);
    if (d.getTime() < s.inicio) d.setDate(d.getDate() + 1);
    return Math.min(d.getTime(), Date.now() + 60000);
  };
  let intensidade = null;
  sh.el.querySelectorAll("[data-int]").forEach((b) => b.onclick = () => { intensidade = b.dataset.int; sh.el.querySelectorAll("[data-int]").forEach((x) => x.classList.toggle("int-b--on", x === b)); });
  const mostra = () => { dur.textContent = `Duração: ${Math.max(1, Math.round((fimMs() - s.inicio) / 60000))} min`; };
  inp.oninput = mostra; mostra();
  sh.el.querySelector("#ok").onclick = async () => {
    if (!intensidade) return toast("Diga como foi a intensidade 🙂", "erro");
    await finalizar(s, fimMs(), false, intensidade);
    sh.fechar();
    if (sheetAberto) sheetAberto.fechar();
    toast("Treino concluído! 🔥 Registrado.");
    aoMudarTela();
  };
  sh.el.querySelector("#descartar").onclick = async () => {
    if (!(await confirmar("Descartar este treino? Nada será salvo.", { ok: "Descartar", perigo: true }))) return;
    await kvSet(CHAVE, null);
    sh.fechar(); if (sheetAberto) sheetAberto.fechar();
    atualizarBarraSessao(); aoMudarTela();
  };
}

// cardio digitado no treino ("20 min de esteira") → esporte equivalente pro cálculo
function esporteDoCardio(nome) {
  const n = nome.toLowerCase();
  const mapa = [["corr", "corrida"], ["esteira", "caminhada"], ["caminh", "caminhada"], ["spinning", "spinning"], ["ergom", "spinning"], ["bike", "spinning"], ["bicicl", "bike"], ["elípt", "eliptico"], ["elipt", "eliptico"], ["nata", "natacao"], ["corda", "corda"], ["zumba", "danca"], ["dan", "danca"], ["remo", "remo"], ["hiit", "crossfit"], ["funcional", "crossfit"], ["lut", "luta"], ["boxe", "luta"], ["futebol", "futebol"], ["escada", "crossfit"]];
  for (const [k, id] of mapa) if (n.includes(k)) return id;
  return "outro";
}

async function finalizar(s, fim, automatico, intensidade = "moderado") {
  const peso = (E.perfil && E.perfil.peso) || 75;
  const kcalCardio = s.exercicios.filter((e) => e.tipo === "cardio").reduce((a, e) => {
    const min = parseInt(String(e.reps), 10) || 20;
    return a + gastoAtividade({ id: esporteDoCardio(e.nome), minutos: min, intensidade: intensidade === "muito" ? "intenso" : intensidade, peso }).liquida;
  }, 0);
  const volume = s.exercicios.reduce((a, e) => a + e.series.filter((x) => x.feito).reduce((b, x) => b + (+x.kg || 0) * (+x.reps || 0), 0), 0);
  const series = s.exercicios.reduce((a, e) => a + e.series.filter((x) => x.feito).length, 0);
  await gravar("treinos", {
    data: hojeISO(new Date(s.inicio)),
    ciclo: s.ciclo, diaIndice: s.diaIndice, letra: s.letra, nome: s.livre ? "Treino livre" : `Treino ${s.letra} — ${s.nome}`, livre: !!s.livre,
    exercicios: s.exercicios.map((e) => ({ nome: e.nome, series: e.series, concluido: e.concluido })),
    volume: Math.round(volume), series, inicio: s.inicio, fim, duracaoMin: Math.max(1, Math.round((fim - s.inicio) / 60000)), automatico,
    intensidade: automatico ? null : intensidade, kcalCardio,
  });
  await kvSet(CHAVE, null);
  atualizarBarraSessao();
}

// ---------- Aviso de tempo + conclusão automática ----------
async function avisarSistema(titulo, corpo) {
  try {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    const reg = await navigator.serviceWorker.getRegistration();
    if (reg) reg.showNotification(titulo, { body: corpo, icon: "./icons/icon-192.png", tag: "treino", renotify: true, data: { url: "./index.html" } });
  } catch (e) { /* sem notificação: o aviso aparece ao abrir o app */ }
}

let perguntando = false;
export async function verificarSessao() {
  const s = await sessaoAtual();
  if (!s) return;
  if (perguntando && !document.querySelector(".pergunta-treino")) perguntando = false;
  const agora = Date.now();
  // Ninguém respondeu em 1 h → conclui com o horário padrão (início + tempo planejado)
  if (s.aguardando && s.perguntadoEm && agora - s.perguntadoEm >= UMA_HORA) {
    await finalizar(s, s.inicio + s.minutosPlano * 60000, true);
    if (sheetAberto) sheetAberto.fechar();
    toast(`Treino ${s.letra} concluído automaticamente (${s.minutosPlano} min) ✅`);
    aoMudarTela();
    return;
  }
  if (!s.aguardando && agora >= s.avisoEm && !perguntando) {
    s.aguardando = true; s.perguntadoEm = agora;
    await salvarSessao(s);
    const min = Math.round((agora - s.inicio) / 60000);
    if (document.visibilityState !== "visible") avisarSistema("⏰ Deu o tempo do seu treino", `Já são ${min} min de Treino ${s.letra}. Ainda está treinando? Toque para responder.`);
    perguntar(s, min);
  } else if (s.aguardando && document.visibilityState === "visible" && !perguntando) {
    perguntar(s, Math.round((agora - s.inicio) / 60000));
  }
}

function perguntar(s, min) {
  if (document.visibilityState !== "visible") return;
  perguntando = true;
  const sh = abrirSheet(`
    <div class="pergunta-treino">
      <div class="onb-hero">⏰</div>
      <h2>Deu seu tempo de treino!</h2>
      <p class="sub">Você está há <b>${min} min</b> no Treino ${esc(s.letra)} (meta: ${s.minutosPlano} min). Ainda está treinando?</p>
      <button class="btn btn--grande" id="sim">💪 Sim, ainda estou treinando</button>
      <button class="btn btn--sec" id="nao">🏁 Terminei — registrar</button>
      <p class="nota">Se não responder em 1 hora, o treino é concluído sozinho com ${s.minutosPlano} min.</p>
    </div>`, { aoFechar: () => { perguntando = false; } });
  sh.el.querySelector("#sim").onclick = async () => {
    const atual = await sessaoAtual();
    if (atual) { atual.aguardando = false; atual.perguntadoEm = null; atual.avisoEm = Date.now() + 15 * 60000; await salvarSessao(atual); }
    sh.fechar();
    toast("Beleza! Te pergunto de novo em 15 min.");
  };
  sh.el.querySelector("#nao").onclick = () => { sh.fechar(); concluirComHorario(); };
}

// ---------- Barra "treino em andamento" (aparece em todas as telas) ----------
let ivBarra = null;
export async function atualizarBarraSessao() {
  const s = await sessaoAtual();
  let barra = document.getElementById("barra-sessao");
  document.body.classList.toggle("tem-sessao", !!(s && !sheetAberto));
  if (!s || sheetAberto) { if (barra) barra.remove(); clearInterval(ivBarra); return; }
  if (!barra) {
    barra = document.createElement("button");
    barra.id = "barra-sessao";
    barra.className = "barra-sessao";
    barra.onclick = () => abrirSessao();
    document.body.appendChild(barra);
  }
  const pinta = () => {
    const seg = Math.floor((Date.now() - s.inicio) / 1000);
    barra.innerHTML = `<span class="barra-pulso"></span><b>${s.livre ? "Treino livre" : `Treino ${esc(s.letra)}`} em andamento</b><span class="barra-tempo">${relogio(seg)}</span><span class="barra-abrir">Abrir ›</span>`;
  };
  pinta();
  clearInterval(ivBarra);
  ivBarra = setInterval(pinta, 1000);
}

export function iniciarVerificadorSessao(aoMudar) {
  aoMudarTela = aoMudar || (() => {});
  verificarSessao();
  atualizarBarraSessao();
  setInterval(verificarSessao, 20000);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") verificarSessao(); });
}

export { duracaoSessao };
