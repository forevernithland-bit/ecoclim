// Tela inicial: resumo do dia, registro rápido e o que fazer agora.
import { esc, num, anel, saudacao, toast, dataBR, temaAtual, aplicarTema, abrirSheet } from "../ui.js";
import { E, metasAtuais, metricasDoDia, salvarMetrica, listar } from "../estado.js";
import { totaisDoDia, abrirNovaRefeicao } from "./comida.js";
import { proximoTreino } from "./treino.js";
import { proximoCheckin, completarInicial } from "./evolucao.js";
import { instalar, deveSugerirInstalar, dispensarSugestao, ehIOS } from "../instalar.js";
import { calcularRelatorio } from "./relatorio.js";
import { bonusDoDia } from "../esportes.js";
import { alertasMedicamento, htmlGuia } from "../medicamentos.js";
import { sessaoAtual, abrirSessao } from "../sessao.js";
import { analisarAlimentacao, sugerirFecharDia } from "../nutri-insights.js";
import { hojeISO } from "../db.js";

const DICAS = [
  "Proteína em todas as refeições deixa você saciado por mais tempo e protege os músculos.",
  "Dormir menos de 6 h aumenta a fome no dia seguinte — o sono também é dieta.",
  "Metade do prato com vegetais: volume grande, poucas calorias.",
  "Beba um copo d'água antes das refeições. Simples e ajuda na saciedade.",
  "Constância vence perfeição: 80% certo todos os dias bate 100% por uma semana.",
  "Registrar o que come, mesmo que imperfeito, já melhora os resultados (está nos estudos!).",
  "A balança oscila. Compare médias semanais e medidas, não o peso de um dia.",
  "Aumentar a carga aos poucos (progressão) é o que faz o músculo crescer.",
  "Caminhar depois das refeições ajuda a controlar o açúcar no sangue.",
  "Fim de semana conta! Planeje as refeições livres em vez de improvisar.",
];

const ehEscuro = () => temaAtual() === "dark" || (temaAtual() === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);

export async function telaHoje(el, ctx) {
  const m = { ...metasAtuais() };
  const t = await totaisDoDia();
  const atividade = bonusDoDia(await listar("treinos"));
  if (atividade.bonus) { m.kcal += atividade.bonus; m.carb += Math.round(atividade.bonus / 4); }
  const met = await metricasDoDia();
  const { dia: prox, feitoHoje } = await proximoTreino();
  const hojeTreina = !E.plano.diasSemana || E.plano.diasSemana.includes(new Date().getDay());
  const sessao = await sessaoAtual();
  const fechar = sugerirFecharDia(E.perfil, { kcal: m.kcal - t.kcal, prot: m.prot - t.proteina });
  const analise = await analisarAlimentacao(E.perfil, metasAtuais());
  const alertasMed = E.perfil.medicamento ? await alertasMedicamento(E.perfil, m) : [];
  const insight = analise.insights.find((x) => x.nivel !== "bom") || analise.insights[0];
  const ck = await proximoCheckin();
  const cks = await listar("checkins");
  const [relDia, relSemana] = await Promise.all([calcularRelatorio("dia"), calcularRelatorio("semana")]);
  const ini = cks.find((c) => c.tipo === "inicial") || cks[0];
  const faltaMedidas = ini && !(ini.medidas && ini.medidas.cintura && ini.medidas.pescoco && (E.perfil.sexo !== "F" || ini.medidas.quadril));
  const faltaFotos = ini && !(ini.fotoFrente || ini.fotoLado);
  const inicio = cks[0];
  const aguaL = +met.agua || 0;
  const pctProt = Math.min(100, Math.round((t.proteina / m.prot) * 100));
  const dica = DICAS[Math.floor(Date.now() / 864e5) % DICAS.length];
  const diasJornada = inicio ? Math.max(0, Math.round((new Date(`${hojeISO()}T12:00`) - new Date(`${inicio.data}T12:00`)) / 864e5)) : 0;
  const deltaPeso = inicio && met.peso ? +(met.peso - inicio.peso).toFixed(1) : inicio ? +(E.perfil.peso - inicio.peso).toFixed(1) : 0;

  el.innerHTML = `
    <div class="tela entra">
      <header class="hoje-topo">
        <div>
          <small>${dataBR(hojeISO(), { weekday: "long", day: "2-digit", month: "long" })}</small>
          <h1>${saudacao()}, ${esc(E.perfil.nome)}!</h1>
        </div>
        <div class="topo-acoes">
          <button class="icone-btn" id="tema" aria-label="Trocar tema claro/escuro">${ehEscuro() ? "☀️" : "🌙"}</button>
          <button class="avatar" id="perfil" aria-label="Perfil">${esc(E.perfil.nome.slice(0, 1).toUpperCase())}</button>
        </div>
      </header>

      ${inicio ? `
      <button class="jornada" data-ir="evolucao">
        <div><small>Dia ${diasJornada + 1} da jornada</small><b>${deltaPeso === 0 ? "Começando forte 💪" : `${deltaPeso > 0 ? "+" : ""}${num(deltaPeso, 1)} kg desde o início`}</b></div>
        <span>Ver evolução ›</span>
      </button>` : ""}

      ${faltaMedidas || faltaFotos ? `
      <button class="card card--link card--alerta" id="completar">
        <div class="card-tag">${faltaMedidas && faltaFotos ? "📏📸 Faltam suas medidas e fotos de \"antes\"" : faltaMedidas ? "📏 Faltam suas medidas de \"antes\"" : "📸 Faltam suas fotos de \"antes\""}</div>
        <span>Sem elas não dá pra comparar sua evolução depois${faltaMedidas ? " e o % de gordura fica só estimado" : ""}. Leva 3 minutos — <b>toque para completar</b>.</span>
      </button>` : ""}

      ${deveSugerirInstalar() ? `
      <div class="card card--instalar">
        <div class="inst-icone"><img src="./icons/icon-192.png" alt=""></div>
        <div class="inst-txt"><b>Instale o Evolua no celular</b><small>Abre como app, funciona sem internet e se atualiza sozinho.</small></div>
        <div class="inst-acoes"><button class="btn btn--peq" id="inst-sim">${ehIOS() ? "Como instalar" : "Instalar"}</button><button class="link link--fraco" id="inst-nao">Agora não</button></div>
      </div>` : ""}

      <div class="card card--anel card--hero">
        ${anel(t.kcal, m.kcal, { rotulo: num(Math.max(0, m.kcal - t.kcal)), sub: t.kcal > m.kcal ? `${num(t.kcal - m.kcal)} acima` : "kcal restantes", tam: 150 })}
        <div class="hero-lado">
          <div class="hero-kcal">
            <div class="hero-num"><small>Comido</small><b>${num(t.kcal)}</b></div>
            <div class="hero-num"><small>Meta${atividade.bonus ? " 🏅" : ""}</small><b>${num(m.kcal)}</b>${atividade.bonus ? `<span class="meta-bonus">+${num(atividade.bonus)} pela atividade</span>` : ""}</div>
          </div>
          ${[["Proteína", t.proteina, m.prot, "m-p"], ["Carboidrato", t.carboidrato, m.carb, "m-c"], ["Gordura", t.gordura, m.gord, "m-g"]].map(([nome, v, meta, cls]) => `
          <div class="hero-macro">
            <div class="hero-macro-topo"><small>${nome}</small><b>${num(v)}<span>/${num(meta)} g</span></b></div>
            <div class="mini-trilho"><div class="${cls}" style="width:${Math.min(100, meta ? Math.round((v / meta) * 100) : 0)}%"></div></div>
          </div>`).join("")}
        </div>
      </div>

      <div class="acoes-rapidas">
        <button class="acao" data-add="foto"><span>📸</span>Foto do prato</button>
        <button class="acao" data-add="voz"><span>🎙️</span>Falar</button>
        <button class="acao" data-add="texto"><span>✍️</span>Digitar</button>
      </div>

      <button class="card card--link card--relatorio" id="relatorio">
        <div class="rel-mini">
          <div class="rel-mini-num rel-nota--${relDia.nota >= 80 ? "bom" : relDia.nota >= 60 ? "medio" : "ruim"}"><b>${relDia.nota}%</b><small>hoje</small></div>
          ${relSemana.registrados ? `<div class="rel-mini-num rel-nota--${relSemana.nota >= 80 ? "bom" : relSemana.nota >= 60 ? "medio" : "ruim"}"><b>${relSemana.nota}%</b><small>semana</small></div>` : `<div class="rel-mini-num"><b>–</b><small>semana</small></div>`}
        </div>
        <div class="rel-mini-txt">
          <div class="card-tag">📊 Relatório de aderência</div>
          <span>${relSemana.assim ? `Nesse ritmo, em 3 meses: <b>~${num(relSemana.assim[3].peso, 1)} kg</b> e <b>${num(relSemana.assim[3].gordura, 1)}%</b> de gordura` : "Registre suas refeições pra ver sua projeção"} ›</span>
        </div>
      </button>

      <div class="grade-2">
        <div class="card card--agua">
          <div class="card-tag">💧 Água</div>
          <div class="agua-num"><b>${num(aguaL, 2)}</b> / ${num(m.agua, 1)} L</div>
          <div class="agua-copos">${Array.from({ length: 8 }, (_, i) => `<i class="${aguaL >= ((i + 1) * m.agua) / 8 ? "on" : ""}"></i>`).join("")}</div>
          <div class="linha-botoes"><button class="btn btn--peq btn--sec" data-agua="-0.25">−</button><button class="btn btn--peq" data-agua="0.25">+ copo</button></div>
        </div>
        <div class="card card--peso">
          <div class="card-tag">⚖️ Peso de hoje</div>
          <div class="campo-unid campo-unid--mini"><input id="peso-hoje" class="campo" type="number" inputmode="decimal" step="0.1" value="${esc(met.peso ?? "")}" placeholder="${num(E.perfil.peso, 1)}"><span>kg</span></div>
          <div class="campo-unid campo-unid--mini"><input id="passos-hoje" class="campo" type="number" inputmode="numeric" step="100" value="${esc(met.passos ?? "")}" placeholder="passos"><span>👟</span></div>
          <button class="btn btn--peq" id="salvar-met">Salvar</button>
        </div>
      </div>

      <button class="card card--treino card--link" data-ir="treino">
        <div class="card-tag">${sessao ? "⏱️ Treino em andamento — toque pra abrir" : feitoHoje ? "✅ Treino de hoje feito!" : hojeTreina ? "🏋️ Hoje é dia de treino!" : "😴 Hoje é descanso — próximo treino"}</div>
        <b>Treino ${prox.letra} — ${esc(prox.nome)}</b>
        <span class="nota">~${prox.minutos} min · ${prox.exercicios.length} exercícios · ${prox.exercicios.slice(0, 3).map((x) => esc(x.nome)).join(", ")}…</span>
      </button>

      <button class="card card--link ${ck.dias <= 0 ? "card--alerta" : ""}" data-ir="evolucao">
        <div class="card-tag">📸 Check-in de evolução</div>
        <span>${ck.dias <= 0 ? "<b>Liberado hoje!</b> Tire as fotos e compare com o início." : `Próximo em <b>${ck.dias} dias</b> — aí você vê o antes × depois.`}</span>
      </button>

      ${m.medicamento ? `
      <button class="card card--link card--med ${alertasMed.some((x) => x.nivel === "alerta") ? "card--med-alerta" : ""}" id="med">
        <div class="card-tag">💉 Seu tratamento · ${esc(m.medicamento.nome)}</div>
        ${t.kcal > 0 && t.kcal < m.pisoKcal && new Date().getHours() >= 17 ? `<p><b>Hoje você comeu ${num(t.kcal)} kcal — o piso seguro é ${num(m.pisoKcal)}.</b> Faltam ${num(m.pisoKcal - t.kcal)} kcal, priorize proteína.</p>` : ""}
        ${alertasMed.slice(0, 2).map((x) => `<p class="nota">${esc(x.texto)}</p>`).join("") || `<p class="nota">Proteína em toda refeição (~${m.protRefeicao} g), nunca abaixo de ${num(m.pisoKcal)} kcal, água e treino de força. <u>Ver o guia ›</u></p>`}
      </button>` : ""}

      ${t.kcal > 0 && !fechar.fechado && fechar.opcoes.length ? `
      <button class="card card--link card--fechar-mini" id="fechar-dia">
        <div class="card-tag">🍽️ Faltam ${num(fechar.restante.kcal)} kcal e ${num(fechar.restante.prot)} g de proteína</div>
        <span>Sugestão ${fechar.momento}: <b>${esc(fechar.opcoes[0].itens.join(" + "))}</b> ›</span>
      </button>` : ""}

      ${insight ? `
      <button class="dica-dia dica-dia--nina" id="insight"><span>${insight.emoji}</span><p><b>A Nina percebeu:</b> ${esc(insight.titulo)}. <u>Ver por quê ›</u></p></button>` : `
      <div class="dica-dia"><span>💡</span><p>${esc(dica)}</p></div>`}

      <div class="grade-2">
        <button class="card card--link card--agente" data-agente="nutri"><span class="agente-av">🥗</span><b>Nina</b><small>Nutricionista</small></button>
        <button class="card card--link card--agente" data-agente="coach"><span class="agente-av">🏋️</span><b>Léo</b><small>Personal</small></button>
      </div>
      <p class="assinatura">Evolua · desenvolvido por <b>Breno Lima</b></p>
    </div>`;

  el.querySelectorAll("[data-add]").forEach((b) => b.onclick = () => abrirNovaRefeicao(b.dataset.add, { aoSalvar: ctx.rerender }));
  el.querySelectorAll("[data-ir]").forEach((b) => b.onclick = () => (sessao && b.dataset.ir === "treino" ? abrirSessao() : ctx.ir(b.dataset.ir)));
  el.querySelectorAll("[data-agente]").forEach((b) => b.onclick = () => ctx.ir("coach", { agente: b.dataset.agente }));
  el.querySelector("#perfil").onclick = () => ctx.ir("perfil");
  const bmed = el.querySelector("#med");
  if (bmed) bmed.onclick = () => {
    const sh = abrirSheet(`${htmlGuia(E.perfil, m)}
    ${alertasMed.length ? `<h3>Pra você agora</h3>${alertasMed.map((x) => `<p class="nota">• ${esc(x.texto)}</p>`).join("")}` : ""}
    <button class="btn btn--sec" id="med-perfil">Editar remédio / fase / efeitos</button>`, { cheia: true });
    sh.el.querySelector("#med-perfil").onclick = () => { sh.fechar(); ctx.ir("perfil"); };
  };
  const bf = el.querySelector("#fechar-dia");
  if (bf) bf.onclick = () => ctx.ir("comida");
  const bi = el.querySelector("#insight");
  if (bi) bi.onclick = () => ctx.ir("comida");
  el.querySelector("#relatorio").onclick = () => ctx.ir("relatorio", { periodo: "dia" });
  el.querySelector("#tema").onclick = (ev) => {
    aplicarTema(ehEscuro() ? "light" : "dark");
    ev.currentTarget.textContent = ehEscuro() ? "☀️" : "🌙";
  };
  const instSim = el.querySelector("#inst-sim");
  if (instSim) {
    instSim.onclick = instalar;
    el.querySelector("#inst-nao").onclick = () => { dispensarSugestao(); el.querySelector(".card--instalar").remove(); };
  }
  const comp = el.querySelector("#completar");
  if (comp) comp.onclick = () => completarInicial(ctx.rerender);
  el.querySelectorAll("[data-agua]").forEach((b) => b.onclick = async () => {
    const novo = Math.max(0, +(aguaL + +b.dataset.agua).toFixed(2));
    await salvarMetrica(hojeISO(), { agua: novo });
    if (novo >= m.agua && aguaL < m.agua) toast("Meta de água batida! 💧");
    ctx.rerender();
  });
  el.querySelector("#salvar-met").onclick = async () => {
    const p = el.querySelector("#peso-hoje").value, ps = el.querySelector("#passos-hoje").value;
    await salvarMetrica(hojeISO(), { ...(p ? { peso: +String(p).replace(",", ".") } : {}), ...(ps ? { passos: +ps } : {}) });
    toast("Salvo ✅");
    ctx.rerender();
  };
}
