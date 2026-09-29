// Tela de treino: plano do ciclo atual, execução com registro de cargas,
// cronômetro de descanso e ajustes (dias, local, troca de exercícios).
import { esc, num, toast, abrirSheet, confirmar, dataBR } from "../ui.js";
import { treinosDoCiclo, cicloAtual, diasParaTroca, nomeDivisao, cardio, REGRAS_TREINO, EQUIPAMENTOS, gerarPlano, DIAS_SEMANA, MINUTOS, PADRAO_DIAS, FOCOS } from "../treino.js";
import { E, gravar, listar, salvarPlano, salvarPerfil } from "../estado.js";
import { hojeISO } from "../db.js";

export const cicloDoPlano = (pl) => cicloAtual(pl) + (pl.offset || 0);

export async function proximoTreino() {
  const pl = E.plano;
  const dias = treinosDoCiclo(pl, cicloDoPlano(pl));
  const logs = await listar("treinos");
  const ult = logs[logs.length - 1];
  const idx = ult ? (ult.diaIndice + 1) % dias.length : 0;
  const feitoHoje = logs.some((l) => l.data === hojeISO());
  return { dia: dias[idx], dias, feitoHoje, logs };
}

let abaDia = null;

export async function telaTreino(el, { rerender }) {
  const pl = E.plano;
  const ciclo = cicloDoPlano(pl);
  const { dia: prox, dias, logs } = await proximoTreino();
  if (abaDia == null || abaDia >= dias.length) abaDia = prox.indice;
  const d = dias[abaDia];
  const semana = logs.filter((l) => l.data >= inicioSemana()).length;
  const cardioInfo = cardio(E.perfil);

  el.innerHTML = `
    <div class="tela entra">
      <div class="card card--treino-topo">
        <div>
          <div class="card-tag">🏋️ ${esc(nomeDivisao(pl))}</div>
          <p class="nota">${(pl.diasSemana || PADRAO_DIAS[pl.dias]).map((x) => DIAS_SEMANA[x]).join(", ")} · ${pl.minutos || 60} min</p>
          ${pl.foco && pl.foco !== "nenhum" ? `<p class="nota"><b>${FOCOS[pl.foco].emoji} Prioridade: ${FOCOS[pl.foco].nome}</b></p>` : ""}
          <p class="nota">Ciclo ${ciclo + 1} · exercícios mudam em <b>${diasParaTroca(pl)} dias</b></p>
        </div>
        <div class="semana-bolinhas" aria-label="Treinos na semana">${Array.from({ length: pl.dias }, (_, i) => `<span class="${i < semana ? "on" : ""}"></span>`).join("")}<small>${semana}/${pl.dias} na semana</small></div>
      </div>

      <div class="abas-dia">
        ${dias.map((x) => `<button class="aba ${x.indice === abaDia ? "aba--on" : ""}" data-aba="${x.indice}">${x.letra}${x.indice === prox.indice ? '<i class="ponto"></i>' : ""}</button>`).join("")}
        <button class="aba aba--icone" id="ajustes" aria-label="Ajustar plano">⚙️</button>
      </div>

      <h2 class="titulo-dia">Treino ${d.letra} — ${esc(d.nome)}</h2>
      <p class="nota">⏱️ ~${d.minutos} min · ${d.exercicios.length} exercícios</p>
      ${d.indice === prox.indice ? `<p class="nota">👉 Este é o seu próximo treino.</p>` : ""}

      <div class="lista-ex">
        ${d.exercicios.map((x, k) => {
          const ultimo = ultimaCarga(logs, x.nome);
          const noBiset = x.biset || (k > 0 && d.exercicios[k - 1].biset);
          return `
          <details class="ex ${x.foco ? "ex--foco" : ""} ${noBiset ? "ex--biset" : ""}">
            <summary>
              <span class="ex-num">${k + 1}</span>
              <span class="ex-txt"><b>${esc(x.nome)}</b>${x.biset ? `<em class="selo-biset">🔗 bi-set com o próximo</em>` : ""}<small>${x.series} × ${x.reps} · ${x.biset ? "sem descanso → vá direto pro próximo" : `descanso ${x.descanso}`}${ultimo ? ` · última: ${esc(ultimo)}` : ""}</small></span>
            </summary>
            <div class="ex-corpo">
              <p class="nota">🎯 ${esc(x.grupo)}</p>
              <p>${esc(x.dica)}</p>
              <p class="nota">Pare com ~${x.rir} repetições "sobrando" (RIR ${x.rir}).</p>
              <a class="btn btn--sec btn--peq" href="${x.video}" target="_blank" rel="noopener">▶ Ver vídeo de execução</a>
            </div>
          </details>`;
        }).join("")}
      </div>

      <button class="btn btn--grande" id="iniciar">Iniciar treino ${d.letra} ▶</button>

      <div class="card">
        <div class="card-tag">🚶 Cardio e passos</div>
        <p>${esc(cardioInfo.texto)}</p>
      </div>

      <details class="card">
        <summary class="card-tag">📚 Regras de ouro do treino</summary>
        <ul class="regras">${REGRAS_TREINO.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
      </details>

      ${logs.length ? `
      <div class="card">
        <div class="card-tag">🗓️ Últimos treinos</div>
        ${logs.slice(-5).reverse().map((l) => `<div class="linha-hist"><span>${dataBR(l.data, { weekday: "short", day: "2-digit", month: "short" })}</span><b>${esc(l.nome)}</b><small>${num(l.volume)} kg · ${l.duracaoMin || "–"} min</small></div>`).join("")}
      </div>` : ""}
    </div>`;

  el.querySelectorAll("[data-aba]").forEach((b) => b.onclick = () => { abaDia = +b.dataset.aba; rerender(); });
  el.querySelector("#iniciar").onclick = () => executarTreino(d, ciclo, logs, rerender);
  el.querySelector("#ajustes").onclick = () => ajustesPlano(rerender);
}

function inicioSemana() {
  const d = new Date();
  const dia = (d.getDay() + 6) % 7; // segunda = 0
  d.setDate(d.getDate() - dia);
  return hojeISO(d);
}

function ultimaCarga(logs, nome) {
  for (let i = logs.length - 1; i >= 0; i--) {
    const ex = logs[i].exercicios.find((e) => e.nome === nome);
    if (ex) {
      const feitas = ex.series.filter((s) => s.feito && (s.kg || s.reps));
      if (feitas.length) {
        const melhor = feitas.reduce((a, b) => ((+b.kg || 0) > (+a.kg || 0) ? b : a));
        return `${melhor.kg ? `${num(melhor.kg, 1)} kg × ` : ""}${melhor.reps || "?"}`;
      }
    }
  }
  return "";
}

function valoresAnteriores(logs, nome) {
  for (let i = logs.length - 1; i >= 0; i--) {
    const ex = logs[i].exercicios.find((e) => e.nome === nome);
    if (ex) return ex.series;
  }
  return [];
}

function executarTreino(d, ciclo, logs, aoTerminar) {
  const inicio = Date.now();
  const estado = d.exercicios.map((x) => {
    const ant = valoresAnteriores(logs, x.nome);
    return { nome: x.nome, series: Array.from({ length: x.series }, (_, i) => ({ kg: ant[i] ? ant[i].kg : "", reps: ant[i] ? ant[i].reps : "", feito: false })) };
  });
  const s = abrirSheet(`
    <div class="exec-topo"><h2>Treino ${d.letra}</h2><span id="cron" class="cron">00:00</span></div>
    ${d.exercicios.map((x, k) => `
      <div class="exec-ex">
        <div class="exec-nome"><b>${k + 1}. ${esc(x.nome)}</b><a href="${x.video}" target="_blank" rel="noopener" aria-label="Vídeo">▶</a></div>
        <small class="nota">${x.series} × ${x.reps} · ${x.biset ? "🔗 bi-set: sem descanso, vá pro próximo" : `descanso ${x.descanso}`} · RIR ${x.rir}</small>
        <div class="series">
          <div class="serie serie--cab"><span>Série</span><span>kg</span><span>reps</span><span>✓</span></div>
          ${estado[k].series.map((se, j) => `
            <div class="serie" data-ex="${k}" data-s="${j}">
              <span>${j + 1}</span>
              <input type="number" inputmode="decimal" step="0.5" class="campo campo--mini" data-campo="kg" value="${esc(se.kg)}" placeholder="–">
              <input type="number" inputmode="numeric" class="campo campo--mini" data-campo="reps" value="${esc(se.reps)}" placeholder="${esc(x.reps.split("–")[0])}">
              <button class="check" data-check aria-label="Série feita">✓</button>
            </div>`).join("")}
        </div>
      </div>`).join("")}
    <div id="descanso" class="descanso oculto"><span>Descanso</span><b id="desc-t">1:30</b><button id="pular">Pular</button></div>
    <button class="btn btn--grande" id="concluir">Concluir treino 🏁</button>`, { cheia: true });

  const cron = s.el.querySelector("#cron");
  const iv = setInterval(() => {
    const seg = Math.floor((Date.now() - inicio) / 1000);
    cron.textContent = `${String(Math.floor(seg / 60)).padStart(2, "0")}:${String(seg % 60).padStart(2, "0")}`;
  }, 1000);

  let ivDesc = null;
  const caixaDesc = s.el.querySelector("#descanso");
  const iniciarDescanso = (texto) => {
    let seg = texto.includes("min") ? parseFloat(texto) * 60 : parseInt(texto, 10) || 90;
    clearInterval(ivDesc);
    caixaDesc.classList.remove("oculto");
    const t = s.el.querySelector("#desc-t");
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
  s.el.querySelector("#pular").onclick = () => { clearInterval(ivDesc); caixaDesc.classList.add("oculto"); };

  s.el.querySelectorAll(".serie[data-ex]").forEach((row) => {
    const k = +row.dataset.ex, j = +row.dataset.s;
    row.querySelectorAll("input").forEach((inp) => inp.oninput = () => { estado[k].series[j][inp.dataset.campo] = inp.value; });
    row.querySelector("[data-check]").onclick = (ev) => {
      const se = estado[k].series[j];
      se.feito = !se.feito;
      if (se.feito && !se.reps) se.reps = d.exercicios[k].reps.split("–")[0];
      row.querySelector('[data-campo="reps"]').value = se.reps;
      ev.currentTarget.classList.toggle("check--on", se.feito);
      row.classList.toggle("serie--feita", se.feito);
      if (se.feito) {
        if (d.exercicios[k].biset) toast(`🔗 Bi-set: vá direto para ${d.exercicios[k + 1].nome}`);
        else iniciarDescanso(d.exercicios[k].descanso);
      }
    };
  });

  s.el.querySelector("#concluir").onclick = async () => {
    const feitas = estado.reduce((a, e) => a + e.series.filter((x) => x.feito).length, 0);
    if (!feitas && !(await confirmar("Nenhuma série marcada. Concluir mesmo assim?", { ok: "Concluir" }))) return;
    clearInterval(iv); clearInterval(ivDesc);
    const volume = estado.reduce((a, e) => a + e.series.filter((x) => x.feito).reduce((b, x) => b + (+x.kg || 0) * (+x.reps || 0), 0), 0);
    await gravar("treinos", {
      data: hojeISO(), ciclo, diaIndice: d.indice, letra: d.letra, nome: `Treino ${d.letra} — ${d.nome}`,
      exercicios: estado, volume: Math.round(volume), duracaoMin: Math.round((Date.now() - inicio) / 60000), series: feitas,
    });
    s.fechar();
    abaDia = null;
    toast("Treino concluído! 🔥 Registrado.");
    aoTerminar();
  };
}

function ajustesPlano(aoMudar) {
  const pl = E.plano;
  let semana = [...(pl.diasSemana || PADRAO_DIAS[pl.dias])];
  let min = pl.minutos || 60;
  const s = abrirSheet(`
    <h2>Ajustar treino</h2>
    <label class="rotulo">Dias de treino</label>
    <div class="semana-sel">${DIAS_SEMANA.map((d, k) => `<button class="sem-b ${semana.includes(k) ? "sem-b--on" : ""}" data-sem="${k}">${d}</button>`).join("")}</div>
    <label class="rotulo">Tempo por dia</label>
    <div class="dias-sel">${MINUTOS.map((m) => `<button class="dia-b dia-b--larg ${min === m ? "dia-b--on" : ""}" data-min="${m}">${m} min</button>`).join("")}</div>
    <label class="rotulo">Prioridade muscular</label>
    <div class="chips-quebra">${Object.entries(FOCOS).map(([k, f]) => `<button class="chip ${(pl.foco || "nenhum") === k ? "chip--on" : ""}" data-foco="${k}">${f.emoji} ${f.nome}</button>`).join("")}</div>
    <label class="rotulo">Local</label>
    <div class="opcoes">${Object.entries(EQUIPAMENTOS).map(([k, o]) => `<button class="opcao opcao--linha ${pl.equipamento === k ? "opcao--on" : ""}" data-eq="${k}"><span class="opcao-emoji">${o.emoji}</span><span><b>${o.rotulo}</b></span></button>`).join("")}</div>
    <label class="rotulo">Trocar exercícios a cada</label>
    <div class="dias-sel">${[4, 6, 8].map((w) => `<button class="dia-b dia-b--larg ${pl.semanasCiclo === w ? "dia-b--on" : ""}" data-sem="${w}">${w} sem</button>`).join("")}</div>
    <button class="btn btn--sec" id="variar">🔄 Variar exercícios agora</button>
    <button class="btn btn--grande" id="salvar">Salvar</button>`);
  let eq = pl.equipamento, sem = pl.semanasCiclo, foco = pl.foco || "nenhum";
  s.el.querySelectorAll("[data-sem]").forEach((b) => b.onclick = () => {
    const d = +b.dataset.sem;
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
  liga("foco", "chip--on", (v) => { foco = v; });
  liga("eq", "opcao--on", (v) => { eq = v; });
  liga("sem", "dia-b--on", (v) => { sem = +v; });
  s.el.querySelector("#variar").onclick = async () => {
    await salvarPlano({ ...pl, offset: (pl.offset || 0) + 1 });
    s.fechar(); toast("Exercícios variados ✅"); aoMudar();
  };
  s.el.querySelector("#salvar").onclick = async () => {
    if (!semana.length) return toast("Escolha pelo menos 1 dia.", "erro");
    const mudouBase = semana.length !== pl.dias || eq !== pl.equipamento || min !== (pl.minutos || 60) || semana.join() !== (pl.diasSemana || []).join();
    await salvarPerfil({ ...E.perfil, diasTreino: semana.length, diasSemana: semana, minutosTreino: min, equipamento: eq, focoMuscular: foco });
    const novo = mudouBase ? { ...gerarPlano(E.perfil, { semanasCiclo: sem }), offset: pl.offset || 0 } : { ...pl, semanasCiclo: sem, foco };
    await salvarPlano(novo);
    abaDia = null;
    s.fechar(); toast("Plano atualizado ✅"); aoMudar();
  };
}
