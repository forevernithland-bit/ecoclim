// Tela inicial: resumo do dia, registro rápido e o que fazer agora.
import { esc, num, anel, saudacao, toast, dataBR, temaAtual, aplicarTema } from "../ui.js";
import { E, metasAtuais, metricasDoDia, salvarMetrica, listar } from "../estado.js";
import { totaisDoDia, abrirNovaRefeicao } from "./comida.js";
import { proximoTreino } from "./treino.js";
import { proximoCheckin, completarInicial } from "./evolucao.js";
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
  const m = metasAtuais();
  const t = await totaisDoDia();
  const met = await metricasDoDia();
  const { dia: prox, feitoHoje } = await proximoTreino();
  const hojeTreina = !E.plano.diasSemana || E.plano.diasSemana.includes(new Date().getDay());
  const ck = await proximoCheckin();
  const cks = await listar("checkins");
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

      <div class="card card--anel card--hero">
        ${anel(t.kcal, m.kcal, { rotulo: num(Math.max(0, m.kcal - t.kcal)), sub: t.kcal > m.kcal ? `${num(t.kcal - m.kcal)} acima` : "kcal restantes", tam: 150 })}
        <div class="hero-lado">
          <div class="hero-num"><small>Comido</small><b>${num(t.kcal)}</b></div>
          <div class="hero-num"><small>Meta</small><b>${num(m.kcal)}</b></div>
          <div class="hero-num"><small>Proteína</small><b>${num(t.proteina)}/${m.prot} g</b><div class="mini-trilho"><div style="width:${pctProt}%"></div></div></div>
        </div>
      </div>

      <div class="acoes-rapidas">
        <button class="acao" data-add="foto"><span>📸</span>Foto do prato</button>
        <button class="acao" data-add="voz"><span>🎙️</span>Falar</button>
        <button class="acao" data-add="texto"><span>✍️</span>Digitar</button>
      </div>

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
        <div class="card-tag">${feitoHoje ? "✅ Treino de hoje feito!" : hojeTreina ? "🏋️ Hoje é dia de treino!" : "😴 Hoje é descanso — próximo treino"}</div>
        <b>Treino ${prox.letra} — ${esc(prox.nome)}</b>
        <span class="nota">~${prox.minutos} min · ${prox.exercicios.length} exercícios · ${prox.exercicios.slice(0, 3).map((x) => esc(x.nome)).join(", ")}…</span>
      </button>

      <button class="card card--link ${ck.dias <= 0 ? "card--alerta" : ""}" data-ir="evolucao">
        <div class="card-tag">📸 Check-in de evolução</div>
        <span>${ck.dias <= 0 ? "<b>Liberado hoje!</b> Tire as fotos e compare com o início." : `Próximo em <b>${ck.dias} dias</b> — aí você vê o antes × depois.`}</span>
      </button>

      <div class="dica-dia"><span>💡</span><p>${esc(dica)}</p></div>

      <div class="grade-2">
        <button class="card card--link card--agente" data-agente="nutri"><span class="agente-av">🥗</span><b>Nina</b><small>Nutricionista</small></button>
        <button class="card card--link card--agente" data-agente="coach"><span class="agente-av">🏋️</span><b>Léo</b><small>Personal</small></button>
      </div>
      <p class="assinatura">Evolua · desenvolvido por <b>Breno Lima</b></p>
    </div>`;

  el.querySelectorAll("[data-add]").forEach((b) => b.onclick = () => abrirNovaRefeicao(b.dataset.add, { aoSalvar: ctx.rerender }));
  el.querySelectorAll("[data-ir]").forEach((b) => b.onclick = () => ctx.ir(b.dataset.ir));
  el.querySelectorAll("[data-agente]").forEach((b) => b.onclick = () => ctx.ir("coach", { agente: b.dataset.agente }));
  el.querySelector("#perfil").onclick = () => ctx.ir("perfil");
  el.querySelector("#tema").onclick = (ev) => {
    aplicarTema(ehEscuro() ? "light" : "dark");
    ev.currentTarget.textContent = ehEscuro() ? "☀️" : "🌙";
  };
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
